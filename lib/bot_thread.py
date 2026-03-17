import threading
import time
import json
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from datetime import datetime
from lib.config import Config
from lib.llm_integration import LLMFactory

class BotThread(threading.Thread):
    def __init__(self, bot_id, start_url, directive, db, bot_manager, bug_reporter, html_simplifier, screenshot_capturer, llm_factory):
        threading.Thread.__init__(self)
        self.bot_id = bot_id
        self.start_url = start_url
        self.directive = directive
        self.db = db
        self.bot_manager = bot_manager
        self.bug_reporter = bug_reporter
        self.html_simplifier = html_simplifier
        self.screenshot_capturer = screenshot_capturer
        self.llm_factory = llm_factory
        self.stop_event = threading.Event()
        self.llm = None
        self.driver = None

    def run(self):
        self.db.update_bot_status(self.bot_id, 'running', datetime.now().isoformat())

        try:
            self.initialize_driver()
            self.llm = self.llm_factory.create_llm()

            known_bugs = self.db.get_known_bugs()
            step_number = 1
            steps_taken = []

            while not self.stop_event.is_set():
                self.driver.get(self.start_url)
                time.sleep(2)

                simplified_html = self.html_simplifier.simplify_html(self.driver.page_source)
                current_url = self.driver.current_url

                # Check domain to prevent cross-domain navigation
                if not self.is_same_domain(current_url, self.start_url):
                    logging.warning(f"Bot {self.bot_id} attempted to navigate to different domain: {current_url}")
                    break

                # Build context for LLM
                context = {
                    'directive': self.directive,
                    'current_page': simplified_html,
                    'known_bugs': known_bugs,
                    'steps_taken': steps_taken,
                    'current_url': current_url
                }

                action = self.get_next_action(context)

                # Execute action
                result = self.execute_action(action, step_number)
                if result['success']:
                    steps_taken.append({
                        'step': step_number,
                        'action': action['action'],
                        'element': action.get('element', ''),
                        'value': action.get('value', ''),
                        'screenshot': result['screenshot']
                    })
                    step_number += 1

                    # Check for bugs
                    if self.detect_bug(action, result):
                        bug_id = self.report_bug(action, result, context)
                        known_bugs.append(self.db.get_knowledge_for_bug(bug_id))

                    # Update simplified HTML
                    simplified_html = self.html_simplifier.simplify_html(self.driver.page_source)
                else:
                    break

                # Check if directive is complete
                if self.is_directive_complete():
                    break

        except Exception as e:
            logging.error(f"Error in bot {self.bot_id}: {str(e)}")
        finally:
            self.cleanup()

    def stop(self):
        self.stop_event.set()

    def initialize_driver(self):
        options = webdriver.ChromeOptions()
        if Config.get_headless():
            options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        self.driver = webdriver.Chrome(options=options)

    def get_next_action(self, context):
        prompt = f"""
        You are a web testing bot. Your current directive is: {context['directive']}

        Current page HTML (simplified):
        {context['current_page']}

        Known bugs to avoid:
        {chr(10).join(context['known_bugs'])}

        Steps taken so far:
        {chr(10).join([f"Step {s['step']}: {s['action']} {s.get('element', '')}" for s in context['steps_taken']])}

        Current URL: {context['current_url']}

        What should your next action be? Respond with a JSON object containing:
        - "action": The type of action (e.g., "click", "fill", "select", "submit", "wait", "get_select_values")
        - "element": The CSS selector for the element to interact with
        - "value": For fill/select actions, the value to fill (if needed)
        - "reasoning": Brief explanation of your choice
        """

        return self.llm.get_action(prompt)

    def execute_action(self, action, step_number):
        try:
            if action['action'] == 'click':
                element = self.driver.find_element(By.CSS_SELECTOR, action['element'])
                element.click()
                action_text = f"Clicked {action['element']}"
            elif action['action'] == 'fill':
                element = self.driver.find_element(By.CSS_SELECTOR, action['element'])
                element.send_keys(action['value'])
                action_text = f"Filled {action['element']} with {action['value']}"
            elif action['action'] == 'select':
                select = Select(self.driver.find_element(By.CSS_SELECTOR, action['element']))
                select.select_by_value(action['value'])
                action_text = f"Selected {action['value']} from {action['element']}"
            elif action['action'] == 'submit':
                element = self.driver.find_element(By.CSS_SELECTOR, action['element'])
                element.submit()
                action_text = f"Submitted form via {action['element']}"
            elif action['action'] == 'wait':
                time.sleep(int(action['value']))
                action_text = f"Waited for {action['value']} seconds"
                return {'success': True, 'screenshot': None}
            elif action['action'] == 'get_select_values':
                select = Select(self.driver.find_element(By.CSS_SELECTOR, action['element']))
                options = [{'text': option.text, 'value': option.get_attribute('value')} for option in select.options]
                action_text = f"Got select values from {action['element']}"
                self.db.add_step(self.bot_id, step_number, action_text, action['element'], None)
                return {'success': True, 'screenshot': None}

            screenshot_path = self.screenshot_capturer.capture_screenshot(self.driver, f"bot_{self.bot_id}_step_{step_number}.png")
            self.db.add_step(self.bot_id, step_number, action_text, action.get('element', ''), screenshot_path)
            return {'success': True, 'screenshot': screenshot_path}

        except Exception as e:
            error_msg = f"Failed to {action['action']} element {action.get('element', '')}: {str(e)}"
            logging.error(error_msg)
            screenshot_path = self.screenshot_capturer.capture_screenshot(self.driver, f"bot_{self.bot_id}_error_step_{step_number}.png")
            self.db.add_step(self.bot_id, step_number, error_msg, action.get('element', ''), screenshot_path)
            return {'success': False, 'screenshot': screenshot_path}

    def detect_bug(self, action, result):
        page_source = self.driver.page_source.lower()
        return any(keyword in page_source for keyword in ['error', 'exception', 'problem', 'failed', 'not found'])

    def report_bug(self, action, result, context):
        summary = f"Potential error detected after action: {action['action']} {action.get('element', '')}"
        steps = json.dumps(context['steps_taken'])
        bug_id = self.db.add_bug(self.bot_id, summary, steps, result['screenshot'])

        knowledge_prompt = f"""
        The following error occurred while trying to {action['action']} element {action.get('element', '')}:
        {self.driver.page_source[:1000]}

        Provide a concise summary of what went wrong and how to avoid it in the future.
        """
        knowledge = self.llm.get_action(knowledge_prompt)['reasoning']
        self.db.add_knowledge(bug_id, knowledge)

        self.bug_reporter.send_notification(summary, knowledge)
        return bug_id

    def is_directive_complete(self):
        page_source = self.driver.page_source.lower()
        return any(keyword in page_source for keyword in ['success', 'completed', 'done', 'finished'])

    def is_same_domain(self, url1, url2):
        from urllib.parse import urlparse
        domain1 = urlparse(url1).netloc
        domain2 = urlparse(url2).netloc
        return domain1 == domain2

    def cleanup(self):
        if self.driver:
            self.driver.quit()
        self.db.update_bot_status(self.bot_id, 'completed', datetime.now().isoformat())
        self.bot_manager.remove_bot(self.bot_id)
