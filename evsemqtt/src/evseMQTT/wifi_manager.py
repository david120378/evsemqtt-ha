import asyncio
import socket


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

    The wallbox sends UDP broadcast datagrams to port 7248 (default).  We bind
    a UDP socket on that port, receive the broadcasts, and reply unicast to the
    wallbox's IP/port — which is auto-discovered from the first incoming packet.
    No IP address configuration required.

    Mirrors the interface of BLEManager so that Commands, EventHandlers and
    Manager can use either transport transparently.
    """

    def __init__(self, port, event_handler, logger):
        self.port = port
        self.event_handler = event_handler
        self.logger = logger

        self.transport = None          # asyncio.DatagramTransport, set by _UDPProtocol
        self.evse_addr = None          # (ip, port) of wallbox, discovered on first packet
        self.queue = asyncio.Queue(5)  # outbound message queue (same as BLEManager)
        self.connected = False

        self.last_message_time = None
        self.message_timeout = 35      # seconds — triggers restart_run if exceeded

        # Set by Manager after instantiation, same pattern as BLEManager
        self.manager = None

    # ------------------------------------------------------------------
    # Startup / shutdown
    # ------------------------------------------------------------------

    async def serve(self):
        """Bind the UDP socket and listen indefinitely for wallbox datagrams."""
        loop = asyncio.get_event_loop()
        await loop.create_datagram_endpoint(
            lambda: _UDPProtocol(self),
            local_addr=("0.0.0.0", self.port),
        )
        self.logger.info(
            f"WiFi (UDP) mode: listening on port {self.port} — "
            "waiting for wallbox broadcast ..."
        )
        # Keep coroutine alive; actual work happens in datagram_received callbacks.
        while True:
            await asyncio.sleep(3600)

    async def disconnect(self):
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
            self.logger.info(f"Wallbox discovered at {addr[0]}:{addr[1]}")
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
    # Reconnect watchdog — mirrors BLEManager behaviour
    # ------------------------------------------------------------------

    def _schedule_reconnect_check(self):
        asyncio.get_event_loop().call_later(
            self.message_timeout, self._check_reconnect
        )

    def _check_reconnect(self):
        if (
            self.last_message_time is not None
            and asyncio.get_event_loop().time() - self.last_message_time
            > self.message_timeout
        ):
            self.logger.warning(
                f"No UDP datagram received in the last {self.message_timeout} s. "
                "Requesting manager restart."
            )
            asyncio.create_task(self.manager.restart_run())
        else:
            self._schedule_reconnect_check()
