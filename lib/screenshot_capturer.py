import os

class ScreenshotCapturer:
    def __init__(self, upload_folder):
        self.upload_folder = upload_folder
        if not os.path.exists(self.upload_folder):
            os.makedirs(self.upload_folder)

    def capture_screenshot(self, driver, filename):
        screenshot_path = os.path.join(self.upload_folder, filename)
        driver.save_screenshot(screenshot_path)
        return screenshot_path
