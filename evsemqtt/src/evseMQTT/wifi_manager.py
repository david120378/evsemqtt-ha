import asyncio


class WiFiManager:
    """TCP-based connection manager for EVSE wallboxes reachable over WiFi.

    Mirrors the interface of BLEManager so that the rest of the codebase
    (Commands, EventHandlers, Manager) can use either transport transparently.
    """

    def __init__(self, host, port, event_handler, logger):
        self.host = host
        self.port = port
        self.event_handler = event_handler
        self.logger = logger

        self.queue = asyncio.Queue(5)
        self.reader = None
        self.writer = None
        self.connected = False

        self.last_message_time = None
        self.message_timeout = 35  # seconds — same as BLEManager
        self.max_retries = 5

        # Set by Manager after instantiation, same pattern as BLEManager
        self.manager = None

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    async def connect(self):
        for attempt in range(self.max_retries):
            self.logger.info(
                f"Connecting to {self.host}:{self.port}, attempt {attempt + 1}"
            )
            try:
                self.reader, self.writer = await asyncio.wait_for(
                    asyncio.open_connection(self.host, self.port), timeout=15.0
                )
                self.connected = True
                self.last_message_time = asyncio.get_event_loop().time()
                self.logger.info(f"Connected to {self.host}:{self.port}")
                self._schedule_reconnect_check()
                return True
            except Exception as e:
                self.logger.error(f"Attempt {attempt + 1} failed: {e}")
                await asyncio.sleep(2)

        if self.manager:
            await self.manager.exit_with_error(
                f"Failed to connect to {self.host}:{self.port} after {self.max_retries} attempts"
            )
        return False

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
        self.logger.info(f"Disconnected from {self.host}:{self.port}")

    # ------------------------------------------------------------------
    # Read loop — equivalent to BLE notification callbacks
    # ------------------------------------------------------------------

    async def read_loop(self):
        """Continuously read data from the TCP socket and forward to EventHandlers."""
        while True:
            if not self.connected or self.reader is None:
                self.logger.warning(
                    "WiFi: not connected, attempting reconnect..."
                )
                await self.connect()
                await asyncio.sleep(1)
                continue

            try:
                data = await self.reader.read(4096)
                if not data:
                    self.logger.warning(
                        "WiFi: connection closed by device"
                    )
                    self.connected = False
                    continue

                self.last_message_time = asyncio.get_event_loop().time()
                await self.event_handler.receive_notification(
                    f"{self.host}:{self.port}", bytearray(data)
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
        """Drain the outbound queue and write each message to the TCP socket.

        Accepts (and ignores) positional args so it can be called with the
        same signature used by BLEManager.message_consumer(address, uuid).
        """
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
