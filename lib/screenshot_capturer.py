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

        # Capture full screenshot and encode as base64
        full_screenshot_data = driver.get_screenshot_as_base64()

        # Create thumbnail version
        from PIL import Image
        from io import BytesIO
        import base64

        # Convert base64 to image
        img_data = base64.b64decode(full_screenshot_data)
        img = Image.open(BytesIO(img_data))

        # Create thumbnail (max 300px height)
        img.thumbnail((1000, 300))

        # Convert thumbnail back to base64
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        thumbnail_data = base64.b64encode(buffered.getvalue()).decode('utf-8')

        return {
            'full': full_screenshot_data,
            'thumbnail': thumbnail_data
        }
