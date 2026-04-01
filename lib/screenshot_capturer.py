class ScreenshotCapturer:
    def __init__(self, upload_folder):
        self.upload_folder = upload_folder

    def capture_screenshot(self, driver):
        # Get page height
        page_height = driver.execute_script("return Math.max(document.body.scrollHeight, document.body.offsetHeight, document.documentElement.clientHeight, document.documentElement.scrollHeight, document.documentElement.offsetHeight);")
        # Set window size based on page height
        driver.set_window_size(1920, page_height)
        # Scroll to top
        driver.execute_script("window.scrollTo(0, 0)")
        # Wait briefly for scroll
        import time
        time.sleep(0.3)

        # Capture screenshot and encode as base64
        screenshot_data = driver.get_screenshot_as_base64()
        return screenshot_data
