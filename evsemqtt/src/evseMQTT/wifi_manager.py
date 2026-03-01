import asyncio


class WiFiManager:
    """TCP-based connection manager for EVSE wallboxes reachable over WiFi.

    Supports two modes:
    - Client mode (server_mode=False): connects to the wallbox directly.
    - Server mode (server_mode=True): listens for an incoming connection from
      the wallbox. Use this when the wallbox connects outbound to a cloud server
      and you want to intercept that connection locally.

    Mirrors the interface of BLEManager so that the rest of the codebase
    (Commands, EventHandlers, Manager) can use either transport transparently.
    """

    def __init__(self, host, port, event_handler, logger, server_mode=False):
        self.host = host
        self.port = port
        self.server_mode = server_mode
        self.event_handler = event_handler
        self.logger = logger

        self.queue = asyncio.Queue(5)
        self.reader = None
        self.writer = None
        self.connected = False
        self._server = None  # asyncio.Server handle (server mode only)

        self.last_message_time = None
        self.message_timeout = 35  # seconds — same as BLEManager
        self.max_retries = 5

        # Set by Manager after instantiation, same pattern as BLEManager
        self.manager = None

    # ------------------------------------------------------------------
    # Connection management — client mode
    # ------------------------------------------------------------------

    async def connect(self):
        """Connect to the wallbox (client mode)."""
        for attempt in range(self.max_retries):
            self.logger.info(
                f"Connecting to {self.host}:{self.port}, attempt {attempt + 1}"
            )
            try:
                self.reader, self.writer = await asyncio.wait_for(
                    asyncio.open_connection(self.host, self.port), timeout=15.0
                )
                self._on_connected(f"{self.host}:{self.port}")
                return True
            except Exception as e:
                self.logger.error(f"Attempt {attempt + 1} failed: {e}")
                await asyncio.sleep(2)

        if self.manager:
            await self.manager.exit_with_error(
                f"Failed to connect to {self.host}:{self.port} after {self.max_retries} attempts"
            )
        return False

    # ------------------------------------------------------------------
    # Connection management — server mode
    # ------------------------------------------------------------------

    async def serve(self):
        """Start a TCP server and wait for the wallbox to connect (server mode)."""
        self.logger.info(
            f"WiFi server mode: listening on port {self.port} for wallbox connection ..."
        )
        self._server = await asyncio.start_server(
            self._handle_client, "0.0.0.0", self.port
        )
        async with self._server:
            await self._server.serve_forever()

    async def _handle_client(self, reader, writer):
        """Called by asyncio when the wallbox connects to our server."""
        peer = writer.get_extra_info("peername")
        self.logger.info(f"Wallbox connected from {peer}")
        self.reader = reader
        self.writer = writer
        self._on_connected(str(peer))
        await self.read_loop()

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _on_connected(self, label):
        self.connected = True
        self.last_message_time = asyncio.get_event_loop().time()
        self.logger.info(f"WiFi connected: {label}")
        self._schedule_reconnect_check()

    async def disconnect(self):
        self.connected = False
        if self.writer:
            try:
                self.writer.close()
                await self.writer.wait_closed()
            except Exception:
                pass
            self.writer = None
            self.reader = None
        if self._server:
            self._server.close()
        self.logger.info("WiFi disconnected")

    # ------------------------------------------------------------------
    # Read loop — equivalent to BLE notification callbacks
    # ------------------------------------------------------------------

    async def read_loop(self):
        """Continuously read data from the TCP socket and forward to EventHandlers."""
        while True:
            if not self.connected or self.reader is None:
                if self.server_mode:
                    # In server mode we wait for the next inbound connection
                    self.logger.warning("WiFi server: waiting for wallbox to reconnect ...")
                    await asyncio.sleep(5)
                    continue
                else:
                    self.logger.warning("WiFi: not connected, attempting reconnect ...")
                    await self.connect()
                    await asyncio.sleep(1)
                    continue

            try:
                data = await self.reader.read(4096)
                if not data:
                    self.logger.warning("WiFi: connection closed by device")
                    self.connected = False
                    continue

                self.last_message_time = asyncio.get_event_loop().time()
                await self.event_handler.receive_notification(
                    "wifi", bytearray(data)
                )

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"WiFi read error: {e}")
                self.connected = False

    # ------------------------------------------------------------------
    # Write queue — equivalent to BLEManager.message_consumer / producer
    # ------------------------------------------------------------------

    async def message_consumer(self, *args, **kwargs):
        """Drain the outbound queue and write each message to the TCP socket."""
        while True:
            if not self.connected or self.writer is None:
                await asyncio.sleep(1)
                continue

            message = await self.queue.get()
            try:
                self.writer.write(message)
                await self.writer.drain()
                self.logger.debug(f"WiFi wrote {len(message)} bytes")
            except Exception as e:
                self.logger.error(f"WiFi write error: {e}")
                self.connected = False
            finally:
                self.queue.task_done()

    async def message_producer(self, message):
        await self.queue.put(message)

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
                f"No message received in the last {self.message_timeout} s. "
                "Requesting manager restart."
            )
            asyncio.create_task(self.manager.restart_run())
        else:
            self._schedule_reconnect_check()
