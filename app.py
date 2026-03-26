from datetime import datetime
import os
import sqlite3
import logging
from flask import Flask, render_template, request, redirect, url_for, send_file, jsonify
from werkzeug.utils import secure_filename
import threading
import time
import json
from lib.config import Config
from lib.bot_thread import BotThread
from lib.bot_manager import BotManager
from lib.bug_reporter import BugReporter
from lib.llm_integration import LLMFactory
from lib.database import Database
from lib.html_simplifier import HTMLSimplifier
from lib.screenshot_capturer import ScreenshotCapturer

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/images'
app.config['DATA_DIR'] = 'data'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload size

if not os.path.exists(app.config['DATA_DIR']):
    os.makedirs(app.config['DATA_DIR'])

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(app.config['DATA_DIR'] + '/newt.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Initialize components
db = Database()
bot_manager = BotManager()
bug_reporter = BugReporter()
html_simplifier = HTMLSimplifier()
screenshot_capturer = ScreenshotCapturer(app.config['UPLOAD_FOLDER'])
logger.info("NEWT application initialized")

@app.route('/')
def index():
    bots = db.get_all_bots()
    return render_template('index.html', bots=bots, db=db)

@app.route('/create', methods=['GET', 'POST'])
def create_bot():
    if request.method == 'POST':
        name = request.form['name']
        start_url = request.form['start_url']
        directive = request.form['directive']

        bot_id = db.create_bot(name, start_url, directive)
        bot_thread = BotThread(
            bot_id=bot_id,
            start_url=start_url,
            directive=directive,
            db=db,
            bot_manager=bot_manager,
            bug_reporter=bug_reporter,
            html_simplifier=html_simplifier,
            screenshot_capturer=screenshot_capturer,
            llm_factory=LLMFactory(),
            logger=logger,
            steps_taken=[],
            known_bug_summaries=[]
        )
        bot_thread.start()
        bot_manager.add_bot(bot_thread)

        return redirect(url_for('bot', bot_id=bot_id))

    return render_template('create.html')

@app.route('/bot/<int:bot_id>')
def bot(bot_id):
    bot = db.get_bot(bot_id)
    steps = db.get_steps(bot_id)
    bugs = db.get_bugs(bot_id)
    return render_template('bot.html', bot=bot, steps=steps, bugs=bugs)

@app.route('/bugs')
def bugs():
    bugs = db.get_all_bugs()
    knowledge = db.get_all_knowledge()
    return render_template('bugs.html', bugs=bugs, knowledge=knowledge)

@app.route('/bug/<int:bug_id>/resolve', methods=['POST'])
def resolve_bug(bug_id):
    db.resolve_bug(bug_id)
    return redirect(url_for('bugs'))

@app.route('/bug/<int:bug_id>/export')
def export_bug(bug_id):
    bug = db.get_bug_with_bot_name(bug_id)
    steps = db.get_steps(bug[1])
    knowledge = db.get_knowledge_for_bug(bug_id)

    html = render_template('bug_report.html', bug=bug, steps=steps, knowledge=knowledge)
    pdf = generate_pdf(html)
    return send_file(
        pdf,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'bug_report_{bug_id}.pdf'
    )

@app.route('/stop/<int:bot_id>', methods=['POST'])
def stop_bot(bot_id):
    bot_manager.stop_bot(bot_id)
    db.update_bot_status(bot_id, 'stopped')
    return redirect(url_for('bot', bot_id=bot_id))

@app.route('/restart/<int:bot_id>', methods=['POST'])
def restart_bot(bot_id):
    bot = db.get_bot(bot_id)
    if not bot:
        return redirect(url_for('index'))

    bot_thread = BotThread(
        bot_id=bot[0],
        start_url=bot[2],
        directive=bot[3],
        db=db,
        bot_manager=bot_manager,
        bug_reporter=bug_reporter,
        html_simplifier=html_simplifier,
        screenshot_capturer=screenshot_capturer,
        llm_factory=LLMFactory(),
        logger=logger,
        steps_taken=[],
        known_bug_summaries=[]
    )
    bot_thread.start()
    bot_manager.add_bot(bot_thread)
    db.update_bot_status(bot_id, 'running', datetime.now().isoformat())

    return redirect(url_for('bot', bot_id=bot_id))

@app.route('/remove/<int:bot_id>', methods=['POST'])
def remove_bot(bot_id):
    bot_manager.stop_bot(bot_id)
    db.update_bot_status(bot_id, 'removed', datetime.now().isoformat())
    logger.info(f"Bot {bot_id} removed by user")
    return redirect(url_for('index'))

@app.route('/self-test', methods=['POST'])
def run_self_test():
    bot_id = db.create_bot(
        name='NEWT Self-Test Bot',
        start_url='http://localhost:5000/test-website',
        directive='Test this dummy website and find any bugs using NEWT'
    )
    bot_thread = BotThread(
        bot_id=bot_id,
        start_url='http://localhost:5000/test-website',
        directive='Test this dummy website and find any bugs using NEWT',
        db=db,
        bot_manager=bot_manager,
        bug_reporter=bug_reporter,
        html_simplifier=html_simplifier,
        screenshot_capturer=screenshot_capturer,
        llm_factory=LLMFactory(),
        logger=logger,
        steps_taken=[]
    )
    bot_thread.start()
    bot_manager.add_bot(bot_thread)
    logger.info(f"Self-test bot {bot_id} started")
    return redirect(url_for('bot', bot_id=bot_id))

@app.route('/test-website')
def test_website():
    return render_template('test_website.html')

def generate_pdf(html_content):
    try:
        import pdfkit
        options = {
            'page-size': 'A4',
            'margin-top': '0.75in',
            'margin-right': '0.75in',
            'margin-bottom': '0.75in',
            'margin-left': '0.75in',
            'enable-local-file-access': None,
            'no-stop-slow-scripts': None,
            'javascript-delay': '200',
            'quiet': ''
        }
        return pdfkit.from_string(html_content, False, options=options)
    except Exception as e:
        logger.error(f"Error generating PDF: {str(e)}")
        # Fallback to plain text if PDF generation fails
        from io import BytesIO
        from reportlab.pdfgen import canvas
        buffer = BytesIO()
        p = canvas.Canvas(buffer)
        p.drawString(100, 750, "NEWT Bug Report - PDF Generation Failed")
        p.drawString(100, 730, f"Error: {str(e)}")
        p.drawString(100, 710, "Please check wkhtmltopdf installation and configuration.")
        p.showPage()
        p.save()
        buffer.seek(0)
        return buffer

if __name__ == '__main__':
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    app.run(host='0.0.0.0', port=5000, debug=Config.get_debug())
