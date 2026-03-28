import sqlite3
from datetime import datetime

class Database:
    def __init__(self):
        self.init_db()

    def init_db(self):
        conn = sqlite3.connect('data/bots.db')
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS bots
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      name TEXT NOT NULL,
                      start_url TEXT NOT NULL,
                      directive TEXT NOT NULL,
                      status TEXT DEFAULT 'idle',
                      last_activity TEXT,
                      created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')

        c.execute('''CREATE TABLE IF NOT EXISTS steps
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      bot_id INTEGER,
                      step_number INTEGER,
                      action TEXT,
                      element TEXT,
                      screenshot_path TEXT,
                      friendly_description TEXT,
                      success BOOLEAN DEFAULT TRUE,
                      timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                      FOREIGN KEY(bot_id) REFERENCES bots(id))''')

        c.execute('''CREATE TABLE IF NOT EXISTS bugs
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      bot_id INTEGER,
                      summary TEXT,
                      steps TEXT,
                      screenshot_path TEXT,
                      screenshot_data BLOB,
                      status TEXT DEFAULT 'new',
                      resolved_at TEXT,
                      FOREIGN KEY(bot_id) REFERENCES bots(id))''')

        c.execute('''CREATE TABLE IF NOT EXISTS bug_knowledge
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      bug_id INTEGER,
                      knowledge_text TEXT,
                      FOREIGN KEY(bug_id) REFERENCES bugs(id))''')

        conn.commit()
        conn.close()

    def create_bot(self, name, start_url, directive):
        conn = sqlite3.connect('data/bots.db')
        c = conn.cursor()
        c.execute("INSERT INTO bots (name, start_url, directive) VALUES (?, ?, ?)",
                 (name, start_url, directive))
        conn.commit()
        bot_id = c.lastrowid
        conn.close()
        return bot_id

    def get_all_bots(self):
        conn = sqlite3.connect('data/bots.db')
        c = conn.cursor()
        c.execute("SELECT * FROM bots ORDER BY created_at DESC")
        bots = c.fetchall()
        conn.close()
        return bots

    def get_bot(self, bot_id):
        conn = sqlite3.connect('data/bots.db')
        c = conn.cursor()
        c.execute("SELECT * FROM bots WHERE id = ?", (bot_id,))
        bot = c.fetchone()
        conn.close()
        return bot

    def update_bot_status(self, bot_id, status, last_activity=None):
        conn = sqlite3.connect('data/bots.db')
        c = conn.cursor()
        if last_activity:
            c.execute("UPDATE bots SET status = ?, last_activity = ? WHERE id = ?",
                     (status, last_activity, bot_id))
        else:
            c.execute("UPDATE bots SET status = ? WHERE id = ?", (status, bot_id))
        conn.commit()
        conn.close()

    def add_step(self, bot_id, step_number, action, element, screenshot_path, friendly_description, success=True):
        conn = sqlite3.connect('data/bots.db')
        c = conn.cursor()
        c.execute("INSERT INTO steps (bot_id, step_number, action, element, screenshot_path, friendly_description, success) VALUES (?, ?, ?, ?, ?, ?, ?)",
                 (bot_id, step_number, action, element, screenshot_path, friendly_description, success))
        conn.commit()
        conn.close()

    def get_steps(self, bot_id):
        conn = sqlite3.connect('data/bots.db')
        c = conn.cursor()
        c.execute("SELECT * FROM steps WHERE bot_id = ? ORDER BY step_number", (bot_id,))
        steps = c.fetchall()
        conn.close()
        return steps

    def add_bug(self, bot_id, summary, steps, screenshot_data=None):
        conn = sqlite3.connect('data/bots.db')
        c = conn.cursor()
        c.execute("INSERT INTO bugs (bot_id, summary, steps, screenshot_data) VALUES (?, ?, ?, ?)",
                 (bot_id, summary, steps, screenshot_data))
        conn.commit()
        bug_id = c.lastrowid
        conn.close()
        return bug_id

    def get_bugs(self, bot_id):
        conn = sqlite3.connect('data/bots.db')
        c = conn.cursor()
        c.execute("SELECT * FROM bugs WHERE bot_id = ?", (bot_id,))
        bugs = c.fetchall()
        conn.close()
        return bugs

    def get_all_bugs(self):
        conn = sqlite3.connect('data/bots.db')
        c = conn.cursor()
        c.execute("SELECT b.*, bt.name as bot_name FROM bugs b JOIN bots bt ON b.bot_id = bt.id ORDER BY b.id DESC")
        bugs = c.fetchall()
        conn.close()
        return bugs

    def get_bug_with_bot_name(self, bug_id):
        conn = sqlite3.connect('data/bots.db')
        c = conn.cursor()
        c.execute("SELECT b.*, bt.name as bot_name FROM bugs b JOIN bots bt ON b.bot_id = bt.id WHERE b.id = ?", (bug_id,))
        bug = c.fetchone()
        conn.close()
        return bug if bug else None

    def resolve_bug(self, bug_id):
        conn = sqlite3.connect('data/bots.db')
        c = conn.cursor()
        c.execute("UPDATE bugs SET status = 'resolved', resolved_at = ? WHERE id = ?",
                 (datetime.now().isoformat(), bug_id))
        conn.commit()
        conn.close()

    def add_knowledge(self, bug_id, knowledge_text):
        conn = sqlite3.connect('data/bots.db')
        c = conn.cursor()
        c.execute("INSERT INTO bug_knowledge (bug_id, knowledge_text) VALUES (?, ?)",
                 (bug_id, knowledge_text))
        conn.commit()
        conn.close()

    def get_knowledge_for_bug(self, bug_id):
        conn = sqlite3.connect('data/bots.db')
        c = conn.cursor()
        c.execute("SELECT knowledge_text FROM bug_knowledge WHERE bug_id = ?", (bug_id,))
        result = c.fetchone()
        conn.close()
        return result[0] if result else ""

    def get_all_knowledge(self):
        conn = sqlite3.connect('data/bots.db')
        c = conn.cursor()
        c.execute("SELECT * FROM bug_knowledge")
        knowledge = {row[1]: row[2] for row in c.fetchall()}
        conn.close()
        return knowledge

    def get_known_bugs(self):
        conn = sqlite3.connect('data/bots.db')
        c = conn.cursor()
        c.execute("SELECT knowledge_text FROM bug_knowledge")
        known_bugs = [row[0] for row in c.fetchall()]
        conn.close()
        return known_bugs
