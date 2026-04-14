from datetime import datetime
import os
import logging
from flask import Flask, render_template, request, redirect, url_for, send_file
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
    bug_count = 0
    for bot in bots:
        bug_count += db.get_bug_count(bot['id'])
    return render_template('index.html', bots=bots, db=db, bug_count=bug_count)

@app.route('/create', methods=['GET', 'POST'])
def create_bot():
    if request.method == 'POST':
        name = request.form['name']
        start_url = request.form['start_url']
        directive = request.form['directive']

        # Validate start URL
        try:
            from urllib.parse import urlparse
            result = urlparse(start_url)
            if not all([result.scheme, result.netloc]):
                return render_template('create.html', error="Please enter a valid URL with http:// or https://")
        except:
            return render_template('create.html', error="Please enter a valid URL")

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
            steps_taken=[]
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
    if not bug:
        return redirect(url_for('bugs'))
    steps = db.get_steps(bug['bot_id'])
    knowledge = db.get_knowledge_for_bug(bug_id)

    # Create HTML with embedded images
    html_content = render_template('bug_report.html', bug=bug, steps=steps, knowledge=knowledge, embed_images=True)

    # Create JSON data
    json_data = {
        'bug_id': bug['id'],
        'bot_id': bug['bot_id'],
        'bot_name': bug.get('bot_name', 'Unknown Bot'),
        'summary': bug['summary'],
        'status': bug['status'],
        'reported_at': bug['reported_at'],
        'resolved_at': bug.get('resolved_at'),
        'steps': steps,
        'knowledge': knowledge
    }

    # Create text summary
    text_summary = f"Bug #{bug['id']} - {bug['summary']}" + chr(10)
    text_summary += f"Bot: {bug.get('bot_name', 'Unknown Bot')}" + chr(10)
    text_summary += f"Status: {bug['status']}" + chr(10)
    text_summary += f"Reported: {bug['reported_at']}" + chr(10)
    text_summary += chr(10) + "Steps:" + chr(10)
    for step in steps:
        text_summary += f"- Step {step['step_number']}: {step['action']}" + chr(10)
    text_summary += chr(10) + "Knowledge:" + chr(10)
    text_summary += knowledge

    # Create ZIP file
    from io import BytesIO
    from zipfile import ZipFile
    import base64

    zip_buffer = BytesIO()
    with ZipFile(zip_buffer, 'w') as zip_file:
        # Add HTML report
        zip_file.writestr('bug_report.html', html_content)

        # Add JSON data
        zip_file.writestr('bug_data.json', json.dumps(json_data, indent=2))

        # Add text summary
        zip_file.writestr('bug_summary.txt', text_summary)

    zip_buffer.seek(0)
    return send_file(
        zip_buffer,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f'bug_report_{bug_id}.zip'
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
        bot_id=bot['id'],
        start_url=bot['start_url'],
        directive=bot['directive'],
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
        start_url='http://localhost:' + str(Config.get_port()) + '/test-website',
        directive='Test this dummy website and find any bugs using NEWT'
    )
    bot_thread = BotThread(
        bot_id=bot_id,
        start_url='http://localhost:' + str(Config.get_port()) + '/test-website',
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

if __name__ == '__main__':
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    app.run(host='127.0.0.1', port=Config.get_port(), debug=Config.get_debug())
