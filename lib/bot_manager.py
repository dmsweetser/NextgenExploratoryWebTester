import threading
import logging

class BotManager:
    def __init__(self):
        self.bots = {}

    def add_bot(self, bot_thread):
        self.bots[bot_thread.bot_id] = bot_thread

    def remove_bot(self, bot_id):
        if bot_id in self.bots:
            del self.bots[bot_id]

    def stop_bot(self, bot_id):
        if bot_id in self.bots:
            self.bots[bot_id].stop()

    def get_active_bots(self):
        return [bot for bot in self.bots.values() if bot.is_alive()]
