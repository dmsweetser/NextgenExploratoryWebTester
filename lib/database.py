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
                      screenshot_data TEXT,
                      friendly_description TEXT,
                      reasoning TEXT,
                      success BOOLEAN DEFAULT TRUE,
                      timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                      FOREIGN KEY(bot_id) REFERENCES bots(id))''')

        c.execute('''CREATE TABLE IF NOT EXISTS bugs
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      bot_id INTEGER,
                      summary TEXT,
                      steps TEXT,
                      status TEXT DEFAULT 'new',
                      reported_at TEXT,
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
        columns = [column[0] for column in c.description]
        bots = [dict(zip(columns, row)) for row in c.fetchall()]
        conn.close()
        return bots

    def get_bot(self, bot_id):
        conn = sqlite3.connect('data/bots.db')
        c = conn.cursor()
        c.execute("SELECT * FROM bots WHERE id = ?", (bot_id,))
        columns = [column[0] for column in c.description]
        row = c.fetchone()
        if row:
            bot = dict(zip(columns, row))
        else:
            bot = None
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

    def add_step(self, bot_id, step_number, action, element, screenshot_data, friendly_description, reasoning, success=True):
        conn = sqlite3.connect('data/bots.db')
        c = conn.cursor()
        c.execute("INSERT INTO steps (bot_id, step_number, action, element, screenshot_data, friendly_description, reasoning, success) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                 (bot_id, step_number, action, element, screenshot_data, friendly_description, reasoning, success))
        conn.commit()
        conn.close()

    def get_steps(self, bot_id):
        conn = sqlite3.connect('data/bots.db')
        c = conn.cursor()
        c.execute("SELECT * FROM steps WHERE bot_id = ? ORDER BY step_number", (bot_id,))
        columns = [column[0] for column in c.description]
        steps = [dict(zip(columns, row)) for row in c.fetchall()]
        conn.close()
        return steps

    def add_bug(self, bot_id, summary, steps, status='new'):
        conn = sqlite3.connect('data/bots.db')
        c = conn.cursor()
        c.execute("INSERT INTO bugs (bot_id, summary, steps, status, reported_at) VALUES (?, ?, ?, ?, ?)",
                 (bot_id, summary, steps, status, datetime.now().isoformat()))
        conn.commit()
        bug_id = c.lastrowid
        conn.close()
        return bug_id

    def get_bugs(self, bot_id, include_steps=True):
        conn = sqlite3.connect('data/bots.db')
        c = conn.cursor()
        if include_steps:
            script = "SELECT id, summary, steps FROM bugs WHERE bot_id = ? and status != 'resolved'"
        else:
            script = "SELECT id, summary FROM bugs WHERE bot_id = ? and status != 'resolved'"
        c.execute(script, (bot_id,))
        columns = [column[0] for column in c.description]
        bugs = [dict(zip(columns, row)) for row in c.fetchall()]
        conn.close()
        return bugs

    def get_bug_count(self, bot_id):
        conn = sqlite3.connect('data/bots.db')
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM bugs WHERE bot_id = ?", (bot_id,))
        count = c.fetchone()[0]
        conn.close()
        return count

    def get_all_bugs(self):
        conn = sqlite3.connect('data/bots.db')
        c = conn.cursor()
        c.execute("SELECT b.*, bt.name as bot_name FROM bugs b JOIN bots bt ON b.bot_id = bt.id ORDER BY b.id DESC")
        columns = [column[0] for column in c.description]
        bugs = [dict(zip(columns, row)) for row in c.fetchall()]
        conn.close()
        return bugs

    def get_bug_with_bot_name(self, bug_id):
        conn = sqlite3.connect('data/bots.db')
        c = conn.cursor()
        c.execute("SELECT b.*, bt.name as bot_name FROM bugs b JOIN bots bt ON b.bot_id = bt.id WHERE b.id = ?", (bug_id,))
        columns = [column[0] for column in c.description]
        row = c.fetchone()
        if row:
            bug = dict(zip(columns, row))
        else:
            bug = None
        conn.close()
        return bug

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
        columns = [column[0] for column in c.description]
        knowledge = {str(row[1]): row[2] for row in c.fetchall()}
        conn.close()
        return knowledge
