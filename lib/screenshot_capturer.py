import os
import time

class ScreenshotCapturer:
    def __init__(self, upload_folder):
        self.upload_folder = upload_folder
        if not os.path.exists(self.upload_folder):
            os.makedirs(self.upload_folder)

    def capture_screenshot(self, driver, filename, full_size=False):
        screenshot_path = os.path.join(self.upload_folder, filename)

        if full_size:
            # Set window size to capture full page
            driver.set_window_size(1920, 1080)
            # Scroll to top to ensure full page is captured
            driver.execute_script("window.scrollTo(0, 0)")
            # Wait for scroll to complete
            time.sleep(0.5)
        else:
            # Use a smaller viewport for thumbnail
            driver.set_window_size(200, 150)

        driver.save_screenshot(screenshot_path)
        return screenshot_path
