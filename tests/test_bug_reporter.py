import unittest
from unittest.mock import patch, MagicMock
from lib.bug_reporter import BugReporter
from lib.config import Config

class TestBugReporter(unittest.TestCase):
    def setUp(self):
        self.reporter = BugReporter()

    @patch('smtplib.SMTP')
    @patch('lib.bug_reporter.Config.get_smtp_host', return_value='smtp.test.com')
    @patch('lib.bug_reporter.Config.get_smtp_port', return_value=587)
    @patch('lib.bug_reporter.Config.get_smtp_user', return_value='user')
    @patch('lib.bug_reporter.Config.get_smtp_password', return_value='pass')
    @patch('lib.bug_reporter.Config.get_smtp_from', return_value='from@test.com')
    @patch('lib.bug_reporter.Config.get_bug_notification_emails', return_value='to@test.com')
    def test_send_notification(self, mock_from, mock_to, mock_user, mock_pass, mock_port, mock_host, mock_smtp):
        mock_smtp_instance = MagicMock()
        mock_smtp.return_value = mock_smtp_instance

        result = self.reporter.send_notification('Test summary', 'Test knowledge', 'high')

        self.assertIsNone(result)
        mock_smtp.assert_called_with('smtp.test.com', 587)
        mock_smtp_instance.starttls.assert_called_once()
        mock_smtp_instance.login.assert_called_with('user', 'pass')
        mock_smtp_instance.send_message.assert_called_once()

    @patch('lib.bug_reporter.Config.get_smtp_host', return_value=None)
    def test_send_notification_no_smtp(self, mock_host):
        result = self.reporter.send_notification('Test summary', 'Test knowledge', 'high')
        self.assertIsNone(result)

if __name__ == '__main__':
    unittest.main()
