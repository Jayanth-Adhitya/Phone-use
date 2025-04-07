import adbutils
import time
import logging

logger = logging.getLogger(__name__)

class ADBController:
    def __init__(self, host="127.0.0.1", port=5037):
        try:
            self.adb = adbutils.adb
            # Attempt to connect to a device. adb server might start if not running.
            self.device = self.adb.device() # Get first available device
            logger.info(f"Connected to device: {self.device.serial}")
            self._screen_dimensions = None # Cache dimensions
        except adbutils.errors.AdbError as e:
            logger.error(f"ADB Error: {e}. Is ADB installed and a device connected/authorized?")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize ADBController: {e}")
            raise

    def get_screen_dimensions(self):
        """Gets the screen width and height in pixels."""
        if self._screen_dimensions:
            return self._screen_dimensions
        try:
            width, height = self.device.window_size()
            self._screen_dimensions = (width, height)
            logger.info(f"Screen dimensions: {width}x{height}")
            return self._screen_dimensions
        except Exception as e:
            logger.error(f"Failed to get screen dimensions: {e}")
            return None

    def take_screenshot(self, local_path):
        """Takes a screenshot and saves it locally."""
        try:
            logger.debug(f"Taking screenshot and saving to {local_path}")
            pil_image = self.device.screenshot()
            pil_image.save(local_path)
            logger.debug(f"Screenshot saved successfully.")
            return True
        except Exception as e:
            logger.error(f"Failed to take screenshot: {e}")
            return False

    def tap(self, x, y):
        """Taps at the given pixel coordinates."""
        try:
            logger.info(f"Tapping at coordinates: ({x}, {y})")
            self.device.click(x, y)
            return True
        except Exception as e:
            logger.error(f"Failed to tap: {e}")
            return False

    def swipe(self, x1, y1, x2, y2, duration_ms=300):
        """Swipes from (x1, y1) to (x2, y2) in pixels."""
        try:
            logger.info(f"Swiping from ({x1}, {y1}) to ({x2}, {y2}) in {duration_ms}ms")
            self.device.swipe(x1, y1, x2, y2, duration_ms / 1000.0) # swipe takes seconds
            return True
        except Exception as e:
            logger.error(f"Failed to swipe: {e}")
            return False

    def input_text(self, text):
        """Inputs the given text into the focused field."""
        try:
            # Escape special characters for adb shell input text
            # Basic escaping, might need refinement for complex cases
            escaped_text = text.replace("'", "'\\''").replace(" ", "%s").replace("&", "\&").replace("<", "\<").replace(">", "\>").replace("?", "\?").replace("*", "\*").replace("|", "\|")
            logger.info(f"Inputting text: {text} (escaped: {escaped_text})")
            # Using adb shell directly as adbutils doesn't have a direct text input method as of last check
            self.device.shell(["input", "text", escaped_text])
            return True
        except Exception as e:
            logger.error(f"Failed to input text: {e}")
            return False

    def wait(self, seconds):
        """Waits for a specified number of seconds."""
        logger.info(f"Waiting for {seconds} seconds.")
        time.sleep(seconds)