import asyncio
import sys
from typing import Callable, Coroutine

import structlog
from pynput.keyboard import GlobalHotKeys, HotKey

log = structlog.get_logger(__name__)

# Import the fn key handler for Mac
if sys.platform == "darwin":
    from smart_dictation.mac_fn_key import async_fn_key_handler


class StopTask(RuntimeError):
    pass


class AsyncHotKey(HotKey):
    def __init__(
        self,
        keys,
        async_call: Callable[[asyncio.Event], Coroutine],
    ):
        super().__init__(keys, self.__on_activate)
        self._on_activate_single_call = async_call
        self._activated = False
        self._released_event = asyncio.Event()
        self._pressed_event = asyncio.Event()
        self._pressed_event.clear()
        self._released_event.set()
        self._loop = asyncio.get_event_loop()

    def __on_activate(self):
        if not self._activated:
            self._activated = True
            self._loop.call_soon_threadsafe(
                lambda: (self._pressed_event.set(), self._released_event.clear())
            )

    def __on_deactivate(self):
        if self._activated:
            self._activated = False
            self._loop.call_soon_threadsafe(
                lambda: (self._pressed_event.clear(), self._released_event.set())
            )

    def press(self, key):
        super().press(key)

    def release(self, key):
        super().release(key)
        if self._state != self._keys and self._activated:  # type: ignore
            self.__on_deactivate()

    async def in_main_loop(self):
        while True:
            try:
                await self._pressed_event.wait()
                self._released_event.clear()
                await self._on_activate_single_call(self._released_event)
            except StopTask as e:
                log.info("Cancelled: %s", str(e))


class AsyncGlobalHotKeys(GlobalHotKeys):
    def __init__(
        self,
        hotkeys: dict[str, Callable[[asyncio.Event], Coroutine]],
        *args,
        **kwargs,
    ):
        super().__init__({}, *args, **kwargs)
        self._loop = asyncio.get_event_loop()
        self._hotkeys = [
            AsyncHotKey([self.canonical(key) for key in HotKey.parse(key)], value)
            for key, value in hotkeys.items()
        ]

    async def run_forever(self):
        """Start the global hotkeys listener asynchronously."""
        with self:
            await asyncio.gather(*[h.in_main_loop() for h in self._hotkeys])


class AsyncFnHotKey:
    """A hotkey that uses the fn key on Mac."""
    def __init__(self, async_call: Callable[[asyncio.Event], Coroutine]):
        self._on_activate_single_call = async_call
        self._activated = False
        self._released_event = asyncio.Event()
        self._pressed_event = asyncio.Event()
        self._pressed_event.clear()
        self._released_event.set()
        self._loop = asyncio.get_event_loop()

    async def start(self):
        """Start listening for fn key events."""
        await async_fn_key_handler.start()

    async def in_main_loop(self):
        """Main loop for handling fn key events."""
        while True:
            try:
                # Wait for fn key press
                await async_fn_key_handler.wait_for_press()
                self._pressed_event.set()
                self._released_event.clear()
                log.info("Fn key pressed, starting callback")

                # Start a task for the callback
                callback_task = asyncio.create_task(self._on_activate_single_call(self._released_event))

                # Wait for fn key release
                await async_fn_key_handler.wait_for_release()
                log.info("Fn key released, setting released event")

                # Set the released event to signal the callback to stop
                self._pressed_event.clear()
                self._released_event.set()

                # Wait for the callback to complete
                await callback_task
            except StopTask as e:
                log.info("Cancelled: %s", str(e))


async def listen_for_hotkeys(hotkeys: dict[str, Callable[[asyncio.Event], Coroutine]]):
    """Listen for hotkeys asynchronously.

    Special case: if the hotkey is "<fn>", use the Mac fn key handler.
    """
    tasks = []

    # Handle regular hotkeys
    regular_hotkeys = {k: v for k, v in hotkeys.items() if k != "<fn>"}
    if regular_hotkeys:
        global_hotkeys = AsyncGlobalHotKeys(regular_hotkeys)
        tasks.append(global_hotkeys.run_forever())

    # Handle fn key if on Mac and requested
    if sys.platform == "darwin" and "<fn>" in hotkeys:
        fn_hotkey = AsyncFnHotKey(hotkeys["<fn>"])
        await fn_hotkey.start()
        tasks.append(fn_hotkey.in_main_loop())

    if tasks:
        await asyncio.gather(*tasks)
