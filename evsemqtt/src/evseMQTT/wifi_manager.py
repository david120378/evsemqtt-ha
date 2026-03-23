import asyncio
import os
import socket
import struct

# Discovery broadcast packet: header 06 01, length 25, keyType 0,
# serial all-FF, password all-FF, cmd 0x0001 (LOGIN_BEACON), tail 0F 02.
# Checksum = sum(all bytes before checksum) % 0xFFFF:
#   6+1+0+25+0 + 14×0xFF + 0+1 = 3603 = 0x0E13
# Sending this causes the wallbox to resume its login-beacon broadcasts.
def _build_wakeup_packet():
    body = bytearray([
        0x06, 0x01,                                          # header
        0x00, 0x19,                                          # length = 25
        0x00,                                                # keyType
        0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF,     # serial (broadcast)
        0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF,                  # password (broadcast)
        0x00, 0x01,                                          # cmd = LOGIN_BEACON
    ])
    checksum = sum(body) % 0xFFFF
    body.extend(struct.pack(">H", checksum))
    body.extend([0x0F, 0x02])                                # tail
    return bytes(body)

_WAKEUP_PACKET = _build_wakeup_packet()

# File used to persist the wallbox IP across add-on restarts.
_IP_CACHE_FILE = "/data/last_wallbox_ip.txt"


class _UDPProtocol(asyncio.DatagramProtocol):
    """Low-level asyncio UDP callback handler — bridges datagrams into WiFiManager."""

    def __init__(self, manager):
        self._mgr = manager

    def connection_made(self, transport):
        self._mgr.transport = transport
        sock = transport.get_extra_info("socket")
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        except Exception as e:
            self._mgr.logger.warning(f"Could not enable UDP broadcast: {e}")
        self._mgr.logger.info(f"UDP socket bound on port {self._mgr.port}")

    def datagram_received(self, data, addr):
        asyncio.ensure_future(self._mgr._on_datagram(data, addr))

    def error_received(self, exc):
        self._mgr.logger.error(f"UDP error: {exc}")

    def connection_lost(self, exc):
        self._mgr.logger.warning("UDP socket closed")
        self._mgr.connected = False


class WiFiManager:
    """UDP-based connection manager for EVSE wallboxes reachable over WiFi.

    The wallbox sends UDP broadcast datagrams to port 28376.  We bind a UDP
    socket on that port, receive the broadcasts, and reply unicast to the
    wallbox's IP/port — which is auto-discovered from the first incoming packet.

    If a static IP is provided via wifi_ip, or a cached IP is available from a
    previous session, wakeup packets are sent directly to that IP in addition to
    the broadcast address — significantly improving reconnect reliability when
    the wallbox has stopped broadcasting.

    If no datagram is received for message_timeout seconds, wakeup packets are
    sent and then retried every reconnect_interval seconds until the wallbox
    responds — without needing a full process restart.

    Mirrors the interface of BLEManager so that Commands, EventHandlers and
    Manager can use either transport transparently.
    """

    def __init__(self, port, event_handler, logger, wifi_ip=None):
        self.port = port
        self.event_handler = event_handler
        self.logger = logger
        self.wifi_ip = wifi_ip             # optional static IP from add-on config

        self.transport = None              # asyncio.DatagramTransport, set by _UDPProtocol
        self.evse_addr = None             # (ip, port) of wallbox, discovered on first packet
        self.queue = asyncio.Queue(5)     # outbound message queue (same as BLEManager)
        self.connected = False

        self.last_message_time = None
        self.message_timeout = 35         # seconds without a datagram before wakeup is sent
        self.reconnect_interval = 10      # seconds between retries while disconnected

        self._reconnect_handle = None     # cancellable asyncio handle for the watchdog

        # Remember the wallbox source port (ephemeral, e.g. 36419) so wakeup
        # packets can be directed there in addition to self.port.
        self.last_known_port = None

        # Load the last known wallbox IP from disk so we can target it directly
        # on the very first wakeup attempt after an add-on restart.
        self.last_known_ip = self._load_cached_ip()
        if self.last_known_ip:
            self.logger.info(f"Loaded cached wallbox IP: {self.last_known_ip}")

        # Set by Manager after instantiation, same pattern as BLEManager
        self.manager = None

    # ------------------------------------------------------------------
    # IP cache helpers
    # ------------------------------------------------------------------

    def _load_cached_ip(self):
        """Return the last known wallbox IP from disk, or None."""
        try:
            with open(_IP_CACHE_FILE, "r") as f:
                ip = f.read().strip()
                if ip:
                    return ip
        except (FileNotFoundError, IOError):
            pass
        return None

    def _save_cached_ip(self, ip):
        """Persist the wallbox IP to disk for use after add-on restarts."""
        try:
            with open(_IP_CACHE_FILE, "w") as f:
                f.write(ip)
            self.logger.debug(f"Cached wallbox IP: {ip}")
        except IOError as e:
            self.logger.warning(f"Could not save wallbox IP to cache: {e}")

    # ------------------------------------------------------------------
    # Startup / shutdown
    # ------------------------------------------------------------------

    async def serve(self):
        """Bind the UDP socket and listen indefinitely for wallbox datagrams."""
        # Re-create the queue here, inside the running event loop, so that it is
        # guaranteed to be bound to *this* loop.  Creating it in __init__ (outside
        # any async context) can bind it to a stale/different loop on Python 3.10+.
        self.queue = asyncio.Queue(5)
        loop = asyncio.get_event_loop()
        await loop.create_datagram_endpoint(
            lambda: _UDPProtocol(self),
            local_addr=("0.0.0.0", self.port),
        )
        self.logger.info(
            f"WiFi (UDP) mode: listening on port {self.port} — "
            "waiting for wallbox broadcast ..."
        )
        # Start the watchdog immediately so a wakeup is sent if the wallbox is
        # already silent at startup (e.g. after an HA restart).
        self.last_message_time = asyncio.get_event_loop().time()
        self._schedule_reconnect_check()
        # Keep coroutine alive; actual work happens in datagram_received callbacks.
        while True:
            await asyncio.sleep(3600)

    async def disconnect(self):
        self._cancel_reconnect()
        self.connected = False
        if self.transport:
            self.transport.close()
            self.transport = None
        self.evse_addr = None
        self.logger.info("WiFi (UDP) disconnected")

    # ------------------------------------------------------------------
    # Incoming datagrams
    # ------------------------------------------------------------------

    async def _on_datagram(self, data, addr):
        self.last_message_time = asyncio.get_event_loop().time()

        if not self.connected:
            self.evse_addr = addr
            self.connected = True
            # Remember source port so wakeup can target it directly.
            self.last_known_port = addr[1]
            # Persist the IP so future restarts can send a targeted wakeup immediately.
            if addr[0] != self.last_known_ip:
                self.last_known_ip = addr[0]
                self._save_cached_ip(addr[0])
            self.logger.info(f"Wallbox discovered at {addr[0]}:{addr[1]}")
            # Reset the watchdog to a full message_timeout from now.
            self._schedule_reconnect_check()

        await self.event_handler.receive_notification("wifi", bytearray(data))

    # ------------------------------------------------------------------
    # Outgoing datagrams  (write queue — same interface as BLEManager)
    # ------------------------------------------------------------------

    async def message_producer(self, message):
        await self.queue.put(message)

    async def message_consumer(self, *args, **kwargs):
        """Drain the outbound queue and send each message to the wallbox."""
        while True:
            if not self.transport or not self.evse_addr:
                await asyncio.sleep(0.1)
                continue

            message = await self.queue.get()
            try:
                self.transport.sendto(message, self.evse_addr)
                self.logger.debug(f"UDP sent {len(message)} bytes to {self.evse_addr}")
            except Exception as e:
                self.logger.error(f"UDP send error: {e}")
            finally:
                self.queue.task_done()

    # ------------------------------------------------------------------
    # Reconnect watchdog
    # ------------------------------------------------------------------

    def _cancel_reconnect(self):
        """Cancel any pending watchdog or retry callback."""
        if self._reconnect_handle is not None:
            self._reconnect_handle.cancel()
            self._reconnect_handle = None

    def _schedule_reconnect_check(self):
        """Schedule the next watchdog check at the normal message_timeout interval."""
        self._cancel_reconnect()
        self._reconnect_handle = asyncio.get_event_loop().call_later(
            self.message_timeout, self._check_reconnect
        )

    def _schedule_retry(self):
        """Schedule the next wakeup retry at the faster reconnect_interval."""
        self._cancel_reconnect()
        self._reconnect_handle = asyncio.get_event_loop().call_later(
            self.reconnect_interval, self._check_reconnect
        )

    def _send_wakeup(self):
        """Send wakeup packets to the broadcast address and, if known, directly to the wallbox.

        Two destination ports are tried for each target address:
          - self.port (28376): the port our addon listens on; the wallbox may also
            accept commands there.
          - last_known_port: the ephemeral source port the wallbox used in its last
            session (e.g. 36419); this is the port it was bound to and may still be
            listening on.
        """
        if not self.transport:
            return

        ports_to_try = {self.port}
        if self.last_known_port and self.last_known_port != self.port:
            ports_to_try.add(self.last_known_port)

        target_ip = self.wifi_ip or self.last_known_ip

        for port in sorted(ports_to_try):
            # 1. Broadcast — catches the wallbox even if its IP has changed.
            try:
                self.transport.sendto(_WAKEUP_PACKET, ("255.255.255.255", port))
                self.logger.info(f"Wakeup broadcast sent to 255.255.255.255:{port}")
            except Exception as e:
                self.logger.error(f"Wakeup broadcast to port {port} failed: {e}")

            # 2. Direct unicast to the configured or last known IP — more reliable
            #    when the wallbox has stopped broadcasting but is still reachable.
            if target_ip:
                try:
                    self.transport.sendto(_WAKEUP_PACKET, (target_ip, port))
                    self.logger.info(f"Wakeup sent directly to {target_ip}:{port}")
                except Exception as e:
                    self.logger.error(f"Direct wakeup to {target_ip}:{port} failed: {e}")

    def _check_reconnect(self):
        self._reconnect_handle = None

        if self.last_message_time is None:
            self._schedule_reconnect_check()
            return

        elapsed = asyncio.get_event_loop().time() - self.last_message_time

        if elapsed >= self.message_timeout:
            # First time detecting a timeout: log + reset connection state.
            if self.connected:
                self.logger.warning(
                    f"No UDP datagram received in {self.message_timeout} s — "
                    "resetting session and sending wakeup"
                )
                self.connected = False
                self.evse_addr = None
                # Reset device state so the full login flow runs again on reconnect.
                if self.manager:
                    self.manager.device.initialization_state = False
                    self.manager.device.logged_in = False
            else:
                self.logger.info(
                    f"Still no UDP datagram after {elapsed:.0f} s — retrying wakeup"
                )

            self._send_wakeup()
            # Retry frequently until the wallbox responds.
            self._schedule_retry()
        else:
            # Recent data received — back to normal watchdog interval.
            self._schedule_reconnect_check()
