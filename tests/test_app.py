import unittest
from unittest.mock import patch, MagicMock
from app import app, db, bot_manager
import json
import io
import zipfile

class TestApp(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

        # Mock database
        self.db = MagicMock()
        self.db.get_all_bots.return_value = [
            {'id': 1, 'name': 'Test Bot 1', 'start_url': 'http://test.com', 'directive': 'Test directive', 'status': 'running', 'last_activity': '2023-01-01'},
            {'id': 2, 'name': 'Test Bot 2', 'start_url': 'http://test2.com', 'directive': 'Another directive', 'status': 'completed', 'last_activity': '2023-01-02'}
        ]
        self.db.get_bug_count.return_value = 5
        self.db.get_bot.return_value = {'id': 1, 'name': 'Test Bot', 'start_url': 'http://test.com', 'directive': 'Test', 'status': 'running', 'last_activity': '2023-01-01', 'created_at': '2023-01-01'}
        self.db.get_steps.return_value = [
            {'id': 1, 'bot_id': 1, 'step_number': 1, 'action': 'click', 'element': '#button', 'screenshot_data': 'data1', 'friendly_description': 'Clicked button', 'reasoning': 'Testing', 'success': True, 'timestamp': '2023-01-01'},
            {'id': 2, 'bot_id': 1, 'step_number': 2, 'action': 'fill', 'element': '#input', 'screenshot_data': 'data2', 'friendly_description': 'Filled input', 'reasoning': 'Testing', 'success': True, 'timestamp': '2023-01-02'}
        ]
        self.db.get_bugs.return_value = [
            {'id': 1, 'bot_id': 1, 'summary': 'Test bug', 'steps': 'steps', 'status': 'new'}
        ]
        self.db.get_bug_with_bot_name.return_value = (
            {'id': 1, 'bot_id': 1, 'summary': 'Test bug', 'steps': 'steps', 'status': 'new', 'reported_at': '2023-01-01', 'resolved_at': None, 'name': 'Test Bot'},
            'Test Bot'
        )
        self.db.get_knowledge_for_bug.return_value = 'Test knowledge'

        with self.app.app_context():
            self.app.config['db'] = self.db

    def test_index_route(self):
        response = self.app.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Dashboard', response.data)
        self.db.get_all_bots.assert_called_once()
        self.db.get_bug_count.assert_called()

    def test_bot_route(self):
        response = self.app.get('/bot/1')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Test Bot', response.data)
        self.db.get_bot.assert_called_with(1)
        self.db.get_steps.assert_called_with(1)
        self.db.get_bugs.assert_called_with(1)

    def test_bugs_route(self):
        self.db.get_all_bugs.return_value = [
            {'id': 1, 'bot_id': 1, 'summary': 'Bug 1', 'steps': 'steps', 'status': 'new', 'reported_at': '2023-01-01', 'resolved_at': None, 'name': 'Test Bot'}
        ]
        self.db.get_all_knowledge.return_value = {'1': 'knowledge'}
        response = self.app.get('/bugs')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Bugs', response.data)
        self.db.get_all_bugs.assert_called_once()
        self.db.get_all_knowledge.assert_called_once()

    def test_create_bot_post(self):
        with patch('app.BotThread') as mock_thread, patch('app.bot_manager') as mock_manager:
            mock_thread_instance = MagicMock()
            mock_thread.return_value = mock_thread_instance
            mock_manager.add_bot.return_value = None

            response = self.app.post('/create', data={
                'name': 'New Bot',
                'start_url': 'http://newtest.com',
                'directive': 'New directive'
            }, follow_redirects=True)

            self.assertEqual(response.status_code, 200)
            self.db.create_bot.assert_called_with('New Bot', 'http://newtest.com', 'New directive')
            mock_thread.assert_called()
            mock_manager.add_bot.assert_called_with(mock_thread_instance)

    def test_export_bug(self):
        response = self.app.get('/bug/1/export')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content_type, 'application/zip')

        # Verify ZIP contents
        zip_file = zipfile.ZipFile(io.BytesIO(response.data))
        self.assertIn('bug_report.html', zip_file.namelist())
        self.assertIn('bug_data.json', zip_file.namelist())
        self.assertIn('bug_summary.txt', zip_file.namelist())

        # Verify JSON content
        json_data = json.loads(zip_file.read('bug_data.json'))
        self.assertEqual(json_data['bug_id'], 1)
        self.assertEqual(json_data['summary'], 'Test bug')

    def test_resolve_bug(self):
        response = self.app.post('/bug/1/resolve', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.db.resolve_bug.assert_called_with(1)

    def test_stop_bot(self):
        response = self.app.post('/stop/1', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.db.update_bot_status.assert_called_with(1, 'stopped')

    def test_restart_bot(self):
        self.db.get_bot.return_value = {'id': 1, 'name': 'Test Bot', 'start_url': 'http://test.com', 'directive': 'Test', 'status': 'stopped', 'last_activity': '2023-01-01', 'created_at': '2023-01-01'}
        with patch('app.BotThread') as mock_thread, patch('app.bot_manager') as mock_manager:
            mock_thread_instance = MagicMock()
            mock_thread.return_value = mock_thread_instance
            mock_manager.add_bot.return_value = None

            response = self.app.post('/restart/1', follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            mock_thread.assert_called()
            mock_manager.add_bot.assert_called_with(mock_thread_instance)
            self.db.update_bot_status.assert_called_with(1, 'running')

    def test_remove_bot(self):
        response = self.app.post('/remove/1', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.db.update_bot_status.assert_called_with(1, 'removed')

    def test_run_self_test(self):
        with patch('app.BotThread') as mock_thread, patch('app.bot_manager') as mock_manager:
            mock_thread_instance = MagicMock()
            mock_thread.return_value = mock_thread_instance
            mock_manager.add_bot.return_value = None

            response = self.app.post('/self-test', follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.db.create_bot.assert_called()
            mock_thread.assert_called()
            mock_manager.add_bot.assert_called_with(mock_thread_instance)

    def test_test_website(self):
        response = self.app.get('/test-website')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Test Website', response.data)

if __name__ == '__main__':
    unittest.main()
