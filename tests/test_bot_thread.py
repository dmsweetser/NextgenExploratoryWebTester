import unittest
from unittest.mock import patch, MagicMock, Mock
from lib.bot_thread import BotThread
from lib.llm_integration import extract_line_based_content

class TestBotThread(unittest.TestCase):
    def setUp(self):
        self.mock_db = MagicMock()
        self.mock_bot_manager = MagicMock()
        self.mock_bug_reporter = MagicMock()
        self.mock_html_simplifier = MagicMock()
        self.mock_screenshot_capturer = MagicMock()
        self.mock_llm_factory = MagicMock()
        self.mock_logger = MagicMock()

        self.mock_llm = MagicMock()
        self.mock_llm_factory.create_llm.return_value = self.mock_llm

        self.mock_driver = MagicMock()
        self.mock_driver.page_source = '<html><body>Test</body></html>'
        self.mock_driver.current_url = 'http://test.com'

        self.bot_thread = BotThread(
            bot_id=1,
            start_url='http://test.com',
            directive='Test directive',
            db=self.mock_db,
            bot_manager=self.mock_bot_manager,
            bug_reporter=self.mock_bug_reporter,
            html_simplifier=self.mock_html_simplifier,
            screenshot_capturer=self.mock_screenshot_capturer,
            llm_factory=self.mock_llm_factory,
            logger=self.mock_logger,
            steps_taken=[]
        )

    @patch('lib.bot_thread.webdriver.Chrome')
    def test_initialize_driver(self, mock_chrome):
        self.bot_thread.initialize_driver()
        mock_chrome.assert_called_once()
        self.assertEqual(self.bot_thread.driver, mock_chrome.return_value)
        mock_chrome.return_value.set_window_size.assert_called_with(1920, 1080)

    def test_get_next_action(self):
        self.mock_llm.get_action.return_value = """
[newt_action_start]
click
[newt_action_end]
[newt_element_start]
#button
[newt_element_end]
[newt_value_start]
[newt_value_end]
[newt_friendly_description_start]
Click the button
[newt_friendly_description_end]
[newt_reasoning_start]
Testing the button
[newt_reasoning_end]
"""
        self.mock_db.get_steps.return_value = []
        self.mock_html_simplifier.simplify_html.return_value = '<html><body>Test</body></html>'

        action = self.bot_thread.get_next_action({
            'directive': 'Test directive',
            'current_page': '<html><body>Test</body></html>',
            'known_bugs': [],
            'steps_taken': [],
            'current_url': 'http://test.com'
        })

        self.assertEqual(action['action'], 'click')
        self.assertEqual(action['element'], '#button')
        self.assertEqual(action['friendly_description'], 'Click the button')
        self.assertEqual(action['reasoning'], 'Testing the button')

    def test_execute_action_click(self):
        self.mock_driver.find_element.return_value = MagicMock()
        self.mock_screenshot_capturer.capture_screenshot.return_value = 'screenshot_data'

        action = {
            'action': 'click',
            'element': '#button',
            'friendly_description': 'Click button',
            'reasoning': 'Testing'
        }

        result = self.bot_thread.execute_action(action, 1)

        self.assertTrue(result['success'])
        self.mock_driver.find_element.assert_called_with('css selector', '#button')
        self.mock_driver.find_element.return_value.click.assert_called_once()
        self.mock_db.add_step.assert_called_once()

    def test_execute_action_fill(self):
        self.mock_driver.find_element.return_value = MagicMock()
        self.mock_screenshot_capturer.capture_screenshot.return_value = 'screenshot_data'

        action = {
            'action': 'fill',
            'element': '#input',
            'value': 'test value',
            'friendly_description': 'Fill input',
            'reasoning': 'Testing'
        }

        result = self.bot_thread.execute_action(action, 1)

        self.assertTrue(result['success'])
        self.mock_driver.find_element.assert_called_with('css selector', '#input')
        self.mock_driver.find_element.return_value.send_keys.assert_called_with('test value')
        self.mock_db.add_step.assert_called_once()

    def test_execute_action_wait(self):
        self.mock_screenshot_capturer.capture_screenshot.return_value = 'screenshot_data'

        action = {
            'action': 'wait',
            'value': '2',
            'friendly_description': 'Wait 2 seconds',
            'reasoning': 'Testing'
        }

        with patch('time.sleep') as mock_sleep:
            result = self.bot_thread.execute_action(action, 1)
            mock_sleep.assert_called_with(2)

        self.assertTrue(result['success'])
        self.mock_db.add_step.assert_called_once()

    def test_detect_bug(self):
        self.mock_llm.get_action.return_value = """
[newt_isbug_start]
True
[newt_isbug_end]
[newt_severity_start]
High
[newt_severity_end]
[newt_description_start]
Test bug description
[newt_description_end]
[newt_recommendation_start]
Test recommendation
[newt_recommendation_end]
"""
        self.mock_html_simplifier.simplify_html.return_value = '<html><body>Test</body></html>'
        self.mock_db.get_steps.return_value = []
        self.mock_db.get_bugs.return_value = []

        is_bug, analysis = self.bot_thread.detect_bug()

        self.assertTrue(is_bug)
        self.assertEqual(analysis['severity'], 'High')
        self.assertEqual(analysis['description'], 'Test bug description')

    def test_report_bug(self):
        self.mock_db.add_bug.return_value = 1
        action = {'action': 'click', 'element': '#button'}
        result = {'success': True}
        context = {'steps_taken': []}
        analysis = {
            'description': 'Bug description',
            'recommendation': 'Bug recommendation',
            'severity': 'high'
        }

        self.bot_thread.report_bug(action, result, context, analysis)

        self.mock_db.add_bug.assert_called_once()
        self.mock_db.add_knowledge.assert_called_once()
        self.mock_bug_reporter.send_notification.assert_called_once()

    def test_is_directive_complete(self):
        self.mock_llm.get_action.return_value = """
[newt_iscomplete_start]
True
[newt_iscomplete_end]
[newt_reasoning_start]
Testing complete
[newt_reasoning_end]
[newt_nextarea_start]
None
[newt_nextarea_end]
"""
        self.mock_html_simplifier.simplify_html.return_value = '<html><body>Test</body></html>'
        self.mock_db.get_steps.return_value = []
        self.mock_db.get_bugs.return_value = []

        is_complete = self.bot_thread.is_directive_complete()

        self.assertTrue(is_complete)

    def test_is_same_domain(self):
        self.assertTrue(self.bot_thread.is_same_domain('http://test.com/page1', 'http://test.com/page2'))
        self.assertFalse(self.bot_thread.is_same_domain('http://test.com', 'http://other.com'))

    def test_handle_alerts(self):
        self.mock_driver.switch_to.alert = MagicMock()
        self.mock_driver.switch_to.alert.text = 'Test alert'
        self.mock_driver.switch_to.alert.accept = MagicMock()

        result = self.bot_thread.handle_alerts()

        self.assertTrue(result)
        self.mock_driver.switch_to.alert.accept.assert_called_once()

    def test_cleanup(self):
        self.bot_thread.driver = MagicMock()
        self.bot_thread.cleanup()

        self.bot_thread.driver.quit.assert_called_once()
        self.mock_db.update_bot_status.assert_called_with(1, 'completed')
        self.mock_bot_manager.remove_bot.assert_called_with(1)

if __name__ == '__main__':
    unittest.main()
