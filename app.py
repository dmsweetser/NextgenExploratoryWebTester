import os
import sqlite3
import logging
from flask import Flask, render_template, request, redirect, url_for, send_file, jsonify
from werkzeug.utils import secure_filename
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import threading
import time
from bs4 import BeautifulSoup
import pdfkit
import json
from lib.config import Config
from lib.llm_integration import LocalLlama, AzureFoundry

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload size

# Initialize database
def init_db():
    conn = sqlite3.connect('bots.db')
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
                  timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY(bot_id) REFERENCES bots(id))''')

    c.execute('''CREATE TABLE IF NOT EXISTS bugs
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  bot_id INTEGER,
                  summary TEXT,
                  steps TEXT,
                  screenshot_path TEXT,
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

# Initialize database at startup
init_db()

# Helper functions
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def simplify_html(html):
    """Simplify HTML to just the essential elements for bot interaction"""
    soup = BeautifulSoup(html, 'html.parser')

    # Remove script and style elements
    for script in soup(['script', 'style', 'noscript', 'meta', 'link']):
        script.decompose()

    # Simplify input elements
    for input_tag in soup.find_all('input'):
        if input_tag.get('type') == 'text':
            input_tag['value'] = input_tag.get('value', '')
        elif input_tag.get('type') == 'checkbox':
            input_tag['checked'] = 'checked' if input_tag.get('checked') else None
        elif input_tag.get('type') == 'radio':
            input_tag['checked'] = 'checked' if input_tag.get('checked') else None

    # Simplify select elements
    for select_tag in soup.find_all('select'):
        select = Select(select_tag)
        options = []
        for option in select.options:
            options.append({
                'text': option.text,
                'value': option.get_attribute('value')
            })
        select_tag['data-options'] = json.dumps(options)

    # Return simplified HTML
    return str(soup)

def capture_screenshot(driver, filename):
    """Capture screenshot and save to uploads folder"""
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    screenshot_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    driver.save_screenshot(screenshot_path)
    return screenshot_path

class BotThread(threading.Thread):
    def __init__(self, bot_id, start_url, directive):
        threading.Thread.__init__(self)
        self.bot_id = bot_id
        self.start_url = start_url
        self.directive = directive
        self.stop_event = threading.Event()

    def run(self):
        conn = sqlite3.connect('bots.db')
        c = conn.cursor()

        # Update bot status
        c.execute("UPDATE bots SET status = ?, last_activity = ? WHERE id = ?",
                 ('running', datetime.now().isoformat(), self.bot_id))
        conn.commit()

        # Initialize Selenium
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')  # Run in headless mode
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        driver = webdriver.Chrome(options=options)

        try:
            # Initialize LLM
            llm = LocalLlama() if Config.use_local_model() else AzureFoundry()

            # Navigate to start URL
            driver.get(self.start_url)
            time.sleep(2)  # Wait for page to load

            # Simplify HTML for first page
            simplified_html = simplify_html(driver.page_source)

            # Get initial knowledge about known bugs
            c.execute("SELECT knowledge_text FROM bug_knowledge")
            known_bugs = [row[0] for row in c.fetchall()]

            # Main bot loop
            step_number = 1
            while not self.stop_event.is_set():
                # Get next action from LLM
                prompt = f"""
                You are a web testing bot. Your current directive is: {self.directive}

                Current page HTML (simplified):
                {simplified_html}

                Known bugs to avoid:
                {chr(10).join(known_bugs)}

                What should your next action be? Respond with a JSON object containing:
                - "action": The type of action (e.g., "click", "fill", "select", "submit", "wait")
                - "element": The CSS selector for the element to interact with
                - "value": For fill actions, the value to fill (if needed)
                - "reasoning": Brief explanation of your choice
                """

                action = llm.get_action(prompt)

                # Execute action
                try:
                    if action['action'] == 'click':
                        element = driver.find_element(By.CSS_SELECTOR, action['element'])
                        element.click()
                        action_text = f"Clicked {action['element']}"
                    elif action['action'] == 'fill':
                        element = driver.find_element(By.CSS_SELECTOR, action['element'])
                        element.send_keys(action['value'])
                        action_text = f"Filled {action['element']} with {action['value']}"
                    elif action['action'] == 'select':
                        select = Select(driver.find_element(By.CSS_SELECTOR, action['element']))
                        select.select_by_value(action['value'])
                        action_text = f"Selected {action['value']} from {action['element']}"
                    elif action['action'] == 'submit':
                        element = driver.find_element(By.CSS_SELECTOR, action['element'])
                        element.submit()
                        action_text = f"Submitted form via {action['element']}"
                    elif action['action'] == 'wait':
                        time.sleep(int(action['value']))
                        action_text = f"Waited for {action['value']} seconds"
                        # Don't capture screenshot for wait actions
                        step_number += 1
                        continue

                    # Capture screenshot
                    screenshot_path = capture_screenshot(driver, f"bot_{self.bot_id}_step_{step_number}.png")

                    # Record step
                    c.execute("INSERT INTO steps (bot_id, step_number, action, element, screenshot_path) VALUES (?, ?, ?, ?, ?)",
                             (self.bot_id, step_number, action_text, action['element'], screenshot_path))
                    conn.commit()

                    # Check for bugs (this is a simple implementation - you might want to enhance it)
                    if "error" in driver.page_source.lower() or "exception" in driver.page_source.lower():
                        # Record bug
                        summary = f"Potential error detected after action: {action_text}"
                        steps = json.dumps([{
                            'step': step_number,
                            'action': action_text,
                            'screenshot': screenshot_path
                        }])

                        c.execute("INSERT INTO bugs (bot_id, summary, steps, screenshot_path) VALUES (?, ?, ?, ?)",
                                 (self.bot_id, summary, steps, screenshot_path))
                        conn.commit()

                        # Get knowledge about this bug
                        knowledge_prompt = f"""
                        The following error occurred while trying to {action_text}:
                        {driver.page_source[:1000]}  # First 1000 chars of page source

                        Provide a concise summary of what went wrong and how to avoid it in the future.
                        """
                        knowledge = llm.get_action(knowledge_prompt)['reasoning']

                        # Record knowledge
                        c.execute("INSERT INTO bug_knowledge (bug_id, knowledge_text) VALUES (?, ?)",
                                 (c.lastrowid, knowledge))
                        conn.commit()

                        # Send email notification if configured
                        self.send_bug_notification(summary, knowledge)

                    # Update simplified HTML for next iteration
                    simplified_html = simplify_html(driver.page_source)

                    step_number += 1

                except (NoSuchElementException, TimeoutException) as e:
                    # Record bug for element not found
                    summary = f"Failed to {action['action']} element {action['element']}: {str(e)}"
                    steps = json.dumps([{
                        'step': step_number,
                        'action': f"Attempted {action['action']} {action['element']}",
                        'screenshot': capture_screenshot(driver, f"bot_{self.bot_id}_error_step_{step_number}.png")
                    }])

                    c.execute("INSERT INTO bugs (bot_id, summary, steps, screenshot_path) VALUES (?, ?, ?, ?)",
                             (self.bot_id, summary, steps, steps[-1]['screenshot']))
                    conn.commit()

                    # Get knowledge about this bug
                    knowledge_prompt = f"""
                    The following error occurred while trying to {action['action']} element {action['element']}:
                    {str(e)}

                    Provide a concise summary of what went wrong and how to avoid it in the future.
                    """
                    knowledge = llm.get_action(knowledge_prompt)['reasoning']

                    # Record knowledge
                    c.execute("INSERT INTO bug_knowledge (bug_id, knowledge_text) VALUES (?, ?)",
                             (c.lastrowid, knowledge))
                    conn.commit()

                    # Send email notification if configured
                    self.send_bug_notification(summary, knowledge)

                    # Break out of loop if critical error
                    break

                # Check if directive is complete
                if "success" in driver.page_source.lower() or "completed" in driver.page_source.lower():
                    break

        except Exception as e:
            logging.error(f"Error in bot {self.bot_id}: {str(e)}")
        finally:
            driver.quit()
            c.execute("UPDATE bots SET status = ?, last_activity = ? WHERE id = ?",
                     ('completed', datetime.now().isoformat(), self.bot_id))
            conn.commit()
            conn.close()

    def stop(self):
        self.stop_event.set()

    def send_bug_notification(self, summary, knowledge):
        """Send email notification about a new bug"""
        if not Config.get_smtp_host():
            return

        msg = MIMEMultipart()
        msg['From'] = Config.get_smtp_from()
        msg['To'] = Config.get_bug_notification_emails()
        msg['Subject'] = f"New Bug Found: {summary}"

        body = f"""
        A new bug has been found by the bot system.

        Summary: {summary}

        Knowledge about this bug:
        {knowledge}

        Please investigate and update the system accordingly.
        """
        msg.attach(MIMEText(body, 'plain'))

        try:
            with smtplib.SMTP(Config.get_smtp_host(), Config.get_smtp_port()) as server:
                server.starttls()
                server.login(Config.get_smtp_user(), Config.get_smtp_password())
                server.send_message(msg)
        except Exception as e:
            logging.error(f"Failed to send email notification: {str(e)}")

# Flask routes
@app.route('/')
def index():
    conn = sqlite3.connect('bots.db')
    c = conn.cursor()
    c.execute("SELECT * FROM bots ORDER BY created_at DESC")
    bots = c.fetchall()
    conn.close()
    return render_template('index.html', bots=bots)

@app.route('/create', methods=['GET', 'POST'])
def create_bot():
    if request.method == 'POST':
        name = request.form['name']
        start_url = request.form['start_url']
        directive = request.form['directive']

        conn = sqlite3.connect('bots.db')
        c = conn.cursor()
        c.execute("INSERT INTO bots (name, start_url, directive) VALUES (?, ?, ?)",
                 (name, start_url, directive))
        conn.commit()
        bot_id = c.lastrowid
        conn.close()

        # Start bot thread
        bot_thread = BotThread(bot_id, start_url, directive)
        bot_thread.start()

        return redirect(url_for('bot', bot_id=bot_id))

    return render_template('create.html')

@app.route('/bot/<int:bot_id>')
def bot(bot_id):
    conn = sqlite3.connect('bots.db')
    c = conn.cursor()

    c.execute("SELECT * FROM bots WHERE id = ?", (bot_id,))
    bot = c.fetchone()

    c.execute("SELECT * FROM steps WHERE bot_id = ? ORDER BY step_number", (bot_id,))
    steps = c.fetchall()

    c.execute("SELECT * FROM bugs WHERE bot_id = ?", (bot_id,))
    bugs = c.fetchall()

    conn.close()

    return render_template('bot.html', bot=bot, steps=steps, bugs=bugs)

@app.route('/bugs')
def bugs():
    conn = sqlite3.connect('bots.db')
    c = conn.cursor()

    c.execute("SELECT b.*, bt.name as bot_name FROM bugs b JOIN bots bt ON b.bot_id = bt.id ORDER BY b.id DESC")
    bugs = c.fetchall()

    c.execute("SELECT * FROM bug_knowledge")
    knowledge = {row[1]: row[2] for row in c.fetchall()}

    conn.close()

    return render_template('bugs.html', bugs=bugs, knowledge=knowledge)

@app.route('/bug/<int:bug_id>/resolve', methods=['POST'])
def resolve_bug(bug_id):
    conn = sqlite3.connect('bots.db')
    c = conn.cursor()
    c.execute("UPDATE bugs SET status = 'resolved', resolved_at = ? WHERE id = ?",
             (datetime.now().isoformat(), bug_id))
    conn.commit()
    conn.close()
    return redirect(url_for('bugs'))

@app.route('/bug/<int:bug_id>/export')
def export_bug(bug_id):
    conn = sqlite3.connect('bots.db')
    c = conn.cursor()

    c.execute("SELECT b.*, bt.name as bot_name FROM bugs b JOIN bots bt ON b.bot_id = bt.id WHERE b.id = ?", (bug_id,))
    bug = c.fetchone()

    c.execute("SELECT * FROM steps WHERE bot_id = ? ORDER BY step_number", (bug[1],))
    steps = c.fetchall()

    c.execute("SELECT knowledge_text FROM bug_knowledge WHERE bug_id = ?", (bug_id,))
    knowledge = c.fetchone()[0] if c.fetchone() else ""

    conn.close()

    # Generate HTML for PDF
    html = f"""
    <h1>Bug Report #{bug[0]}</h1>
    <h2>Summary: {bug[2]}</h2>
    <p><strong>Bot:</strong> {bug[9]} | <strong>Status:</strong> {bug[6]}</p>

    <h3>Steps to Reproduce:</h3>
    <ol>
    {''.join([f'<li>{step[3]} - {step[4]}</li>' for step in steps])}
    </ol>

    <h3>Knowledge:</h3>
    <p>{knowledge}</p>

    <h3>Screenshot:</h3>
    <img src="{bug[5]}" style="max-width: 100%;">
    """

    # Convert to PDF
    options = {
        'page-size': 'A4',
        'margin-top': '0.75in',
        'margin-right': '0.75in',
        'margin-bottom': '0.75in',
        'margin-left': '0.75in',
    }
    pdf = pdfkit.from_string(html, False, options=options)

    return send_file(
        pdf,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'bug_report_{bug_id}.pdf'
    )

@app.route('/stop/<int:bot_id>', methods=['POST'])
def stop_bot(bot_id):
    conn = sqlite3.connect('bots.db')
    c = conn.cursor()
    c.execute("SELECT * FROM bots WHERE id = ?", (bot_id,))
    bot = c.fetchone()
    conn.close()

    if bot and bot[3] == 'running':
        # Find and stop the bot thread
        for thread in threading.enumerate():
            if isinstance(thread, BotThread) and thread.bot_id == bot_id:
                thread.stop()
                break

        # Update status
        conn = sqlite3.connect('bots.db')
        c = conn.cursor()
        c.execute("UPDATE bots SET status = ?, last_activity = ? WHERE id = ?",
                 ('stopped', datetime.now().isoformat(), bot_id))
        conn.commit()
        conn.close()

    return redirect(url_for('bot', bot_id=bot_id))

if __name__ == '__main__':
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    app.run(host='0.0.0.0', port=5000, debug=True)