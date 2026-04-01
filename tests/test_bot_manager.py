import unittest
from unittest.mock import MagicMock
from lib.bot_manager import BotManager

class TestBotManager(unittest.TestCase):
    def setUp(self):
        self.manager = BotManager()

    def test_add_bot(self):
        bot_thread = MagicMock()
        bot_thread.bot_id = 1
        self.manager.add_bot(bot_thread)
        self.assertEqual(len(self.manager.bots), 1)
        self.assertIn(1, self.manager.bots)

    def test_remove_bot(self):
        bot_thread = MagicMock()
        bot_thread.bot_id = 1
        self.manager.add_bot(bot_thread)
        self.manager.remove_bot(1)
        self.assertEqual(len(self.manager.bots), 0)

    def test_stop_bot(self):
        bot_thread = MagicMock()
        bot_thread.bot_id = 1
        bot_thread.stop = MagicMock()
        self.manager.add_bot(bot_thread)
        self.manager.stop_bot(1)
        bot_thread.stop.assert_called_once()

    def test_get_active_bots(self):
        bot_thread1 = MagicMock()
        bot_thread1.bot_id = 1
        bot_thread1.is_alive.return_value = True

        bot_thread2 = MagicMock()
        bot_thread2.bot_id = 2
        bot_thread2.is_alive.return_value = False

        self.manager.add_bot(bot_thread1)
        self.manager.add_bot(bot_thread2)

        active_bots = self.manager.get_active_bots()
        self.assertEqual(len(active_bots), 1)
        self.assertEqual(active_bots[0].bot_id, 1)

if __name__ == '__main__':
    unittest.main()
