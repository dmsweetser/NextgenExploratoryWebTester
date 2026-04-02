import unittest
from unittest.mock import MagicMock
from lib.screenshot_capturer import ScreenshotCapturer

class TestScreenshotCapturer(unittest.TestCase):
    def setUp(self):
        self.capturer = ScreenshotCapturer('static/images')

    def test_capture_screenshot(self):
        mock_driver = MagicMock()
        mock_driver.execute_script.return_value = 1000
        mock_driver.get_screenshot_as_base64.return_value = 'base64data'

        result = self.capturer.capture_screenshot(mock_driver)

        self.assertEqual(result, 'base64data')
        mock_driver.execute_script.assert_called()
        mock_driver.set_window_size.assert_called_with(1920, 1000)
        mock_driver.get_screenshot_as_base64.assert_called_once()

if __name__ == '__main__':
    unittest.main()
