import unittest
import sqlite3
import os
from lib.database import Database

class TestDatabase(unittest.TestCase):
    def setUp(self):
        self.db = Database()
        # Use a test database
        self.db_path = 'test_bots.db'
        self.conn = sqlite3.connect(self.db_path)
        self.c = self.conn.cursor()

        # Create test data
        self.c.execute("INSERT INTO bots (name, start_url, directive) VALUES (?, ?, ?)",
                      ('Test Bot', 'http://test.com', 'Test directive'))
        self.bot_id = self.c.lastrowid
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_create_bot(self):
        new_bot_id = self.db.create_bot('New Bot', 'http://new.com', 'New directive')
        self.assertIsInstance(new_bot_id, int)
        self.assertGreater(new_bot_id, 0)

    def test_get_all_bots(self):
        bots = self.db.get_all_bots()
        self.assertIsInstance(bots, list)
        self.assertGreater(len(bots), 0)
        self.assertIsInstance(bots[0], dict)
        self.assertIn('id', bots[0])
        self.assertIn('name', bots[0])

    def test_get_bot(self):
        bot = self.db.get_bot(self.bot_id)
        self.assertIsInstance(bot, dict)
        self.assertEqual(bot['id'], self.bot_id)
        self.assertEqual(bot['name'], 'Test Bot')

    def test_update_bot_status(self):
        self.db.update_bot_status(self.bot_id, 'completed')
        bot = self.db.get_bot(self.bot_id)
        self.assertEqual(bot['status'], 'completed')

    def test_add_step(self):
        self.db.add_step(self.bot_id, 1, 'click', '#button', 'screenshot', 'Clicked button', 'Testing')
        steps = self.db.get_steps(self.bot_id)
        self.assertEqual(len(steps), 1)
        self.assertEqual(steps[0]['action'], 'click')

    def test_get_steps(self):
        steps = self.db.get_steps(self.bot_id)
        self.assertIsInstance(steps, list)

    def test_add_bug(self):
        bug_id = self.db.add_bug(self.bot_id, 'Test bug', 'steps')
        self.assertIsInstance(bug_id, int)
        self.assertGreater(bug_id, 0)

    def test_get_bugs(self):
        bugs = self.db.get_bugs(self.bot_id)
        self.assertIsInstance(bugs, list)

    def test_get_bug_count(self):
        count = self.db.get_bug_count(self.bot_id)
        self.assertIsInstance(count, int)

    def test_get_all_bugs(self):
        bugs = self.db.get_all_bugs()
        self.assertIsInstance(bugs, list)

    def test_get_bug_with_bot_name(self):
        bug_id = self.db.add_bug(self.bot_id, 'Test bug', 'steps')
        bug = self.db.get_bug_with_bot_name(bug_id)
        self.assertIsInstance(bug, dict)
        self.assertEqual(bug['bot_name'], 'Test Bot')

    def test_resolve_bug(self):
        bug_id = self.db.add_bug(self.bot_id, 'Test bug', 'steps')
        self.db.resolve_bug(bug_id)
        bug = self.db.get_bug_with_bot_name(bug_id)
        self.assertEqual(bug['status'], 'resolved')

    def test_add_knowledge(self):
        bug_id = self.db.add_bug(self.bot_id, 'Test bug', 'steps')
        self.db.add_knowledge(bug_id, 'Test knowledge')
        knowledge = self.db.get_knowledge_for_bug(bug_id)
        self.assertEqual(knowledge, 'Test knowledge')

    def test_get_knowledge_for_bug(self):
        bug_id = self.db.add_bug(self.bot_id, 'Test bug', 'steps')
        self.db.add_knowledge(bug_id, 'Test knowledge')
        knowledge = self.db.get_knowledge_for_bug(bug_id)
        self.assertEqual(knowledge, 'Test knowledge')

    def test_get_all_knowledge(self):
        bug_id = self.db.add_bug(self.bot_id, 'Test bug', 'steps')
        self.db.add_knowledge(bug_id, 'Test knowledge')
        knowledge = self.db.get_all_knowledge()
        self.assertIsInstance(knowledge, dict)
        self.assertIn(str(bug_id), knowledge)

if __name__ == '__main__':
    unittest.main()
