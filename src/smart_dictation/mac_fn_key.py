"""
Mac-specific module for handling the fn key properly.
This module uses PyObjC to directly interact with macOS APIs for reliable fn key detection.
"""
import sys
import asyncio
import threading
import time
import structlog
from typing import Callable, Optional

log = structlog.get_logger(__name__)

if sys.platform == 'darwin':
    import objc
    from AppKit import NSEvent
    from Quartz import CGEventSourceKeyState, kCGEventSourceStateHIDSystemState

    # Function key constants
    FN_KEY_CODE = 63  # This is the virtual key code for the fn key on Mac

    class MacFnKeyHandler:
        """
        Handler for Mac fn key detection using direct polling.
        This class provides a way to detect fn key presses and releases on macOS.
        """
        def __init__(self):
            self._fn_pressed = False
            self._callback = None
            self._loop = None
            self._running = False
            self._thread = None
            self._poll_interval = 0.01  # 10ms polling interval

        def is_fn_pressed(self) -> bool:
            """Returns whether the fn key is currently pressed."""
            # Direct check of fn key state using CGEventSourceKeyState
            try:
                # Check if the fn key is pressed using the system event source
                return CGEventSourceKeyState(kCGEventSourceStateHIDSystemState, FN_KEY_CODE)
            except Exception as e:
                log.error("Error checking fn key state: %s", e)
                return False

        def start(self, callback: Callable[[bool], None], loop: asyncio.AbstractEventLoop) -> None:
            """
            Start monitoring fn key events by polling.
            
            Args:
                callback: Function to call when fn key state changes. Takes a boolean indicating if pressed.
                loop: The asyncio event loop to use for callbacks.
            """
            if self._running:
                return
                
            self._callback = callback
            self._loop = loop
            self._running = True
            
            # Start polling in a separate thread
            self._thread = threading.Thread(target=self._polling_thread, daemon=True)
            self._thread.start()
            
            log.info("Mac fn key handler started (polling mode)")

        def stop(self) -> None:
            """Stop monitoring fn key events."""
            if not self._running:
                return
                
            self._running = False
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=1.0)
                
            log.info("Mac fn key handler stopped")

        def _polling_thread(self) -> None:
            """Thread that polls for fn key state changes."""
            last_state = False
            
            try:
                while self._running:
                    # Check current state
                    current_state = self.is_fn_pressed()
                    
                    # If state changed, notify callback
                    if current_state != last_state:
                        log.info("Fn key state changed: %s", current_state)
                        last_state = current_state
                        
                        if self._callback and self._loop:
                            self._loop.call_soon_threadsafe(self._callback, current_state)
                    
                    # Sleep for a short time
                    time.sleep(self._poll_interval)
            except Exception as e:
                log.error("Error in fn key polling thread: %s", e)
                if self._running and self._callback and self._loop:
                    self._loop.call_soon_threadsafe(
                        lambda: log.error("Fn key polling stopped due to error")
                    )

    # Create a singleton instance
    fn_key_handler = MacFnKeyHandler()

else:
    # Dummy implementation for non-Mac platforms
    class DummyFnKeyHandler:
        """Dummy implementation for non-Mac platforms."""
        def __init__(self):
            self._fn_pressed = False
            
        def is_fn_pressed(self) -> bool:
            """Always returns False on non-Mac platforms."""
            return False
            
        def start(self, callback: Callable[[bool], None], loop: asyncio.AbstractEventLoop) -> None:
            """Does nothing on non-Mac platforms."""
            log.info("Fn key handler not available on this platform")
            
        def stop(self) -> None:
            """Does nothing on non-Mac platforms."""
            pass
    
    # Create a singleton instance
    fn_key_handler = DummyFnKeyHandler()


class AsyncFnKeyHandler:
    """
    Asynchronous wrapper for fn key detection.
    
    This class provides an async interface for detecting fn key presses and releases.
    """
    def __init__(self):
        self._pressed_event = asyncio.Event()
        self._released_event = asyncio.Event()
        self._released_event.set()  # Initially released
        self._loop = None
        
    def _on_fn_key_change(self, pressed: bool) -> None:
        """Called when fn key state changes."""
        if pressed:
            self._loop.call_soon_threadsafe(
                lambda: (self._pressed_event.set(), self._released_event.clear())
            )
        else:
            self._loop.call_soon_threadsafe(
                lambda: (self._pressed_event.clear(), self._released_event.set())
            )
    
    async def start(self) -> None:
        """Start monitoring fn key events."""
        self._loop = asyncio.get_event_loop()
        fn_key_handler.start(self._on_fn_key_change, self._loop)
    
    async def stop(self) -> None:
        """Stop monitoring fn key events."""
        fn_key_handler.stop()
    
    async def wait_for_press(self) -> None:
        """Wait until fn key is pressed."""
        await self._pressed_event.wait()
    
    async def wait_for_release(self) -> None:
        """Wait until fn key is released."""
        await self._released_event.wait()
    
    def is_pressed(self) -> bool:
        """Returns whether the fn key is currently pressed."""
        return fn_key_handler.is_fn_pressed()


# Create a singleton instance
async_fn_key_handler = AsyncFnKeyHandler()
