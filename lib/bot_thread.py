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
from lib.llm_integration import LLMFactory, extract_line_based_content

class BotThread(threading.Thread):
    def __init__(self, bot_id, start_url, directive, db, bot_manager, bug_reporter, html_simplifier, screenshot_capturer, llm_factory, logger, steps_taken=None, known_bug_summaries=None):
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
        self.steps_taken = steps_taken or []
        self.known_bug_summaries = known_bug_summaries or []
        self.logger = logger
        self.default_wait = Config.get_default_wait()

    def run(self):
        self.db.update_bot_status(self.bot_id, 'running', datetime.now().isoformat())

        try:
            self.initialize_driver()
            self.llm = self.llm_factory.create_llm()

            # Get known bugs for this specific bot only
            self.known_bug_summaries = self.db.get_knowledge_for_bot(self.bot_id)
            step_number = len(self.steps_taken) + 1

            while not self.stop_event.is_set():
                try:
                    self.driver.get(self.start_url)
                    # Handle any unexpected alerts
                    try:
                        alert = self.driver.switch_to.alert
                        alert.accept()
                    except:
                        pass
                    time.sleep(2)
                except Exception as e:
                    self.logger.error(f"Bot {self.bot_id} - Error navigating to URL: {str(e)}")
                    break

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
                    'known_bugs': self.known_bug_summaries,
                    'steps_taken': self.steps_taken,
                    'current_url': current_url,
                    'previous_bug_summaries': self.known_bug_summaries
                }

                action = self.get_next_action(context)

                # Execute action
                result = self.execute_action(action, step_number)
                self.steps_taken.append({
                    'step': step_number,
                    'action': action['action'],
                    'element': action.get('element', ''),
                    'value': action.get('value', ''),
                    'friendly_description': action.get('friendly_description', ''),
                    'screenshot': result['screenshot'],
                    'success': result['success']
                })
                step_number += 1

                # Add default wait after every action
                time.sleep(self.default_wait)

                # Check for bugs
                analysis_result, analysis = self.detect_bug(action, result)
                if analysis_result:
                    bug_id = self.report_bug(action, result, context, analysis)
                    # Update known bugs for this bot
                    self.known_bug_summaries = self.db.get_knowledge_for_bot(self.bot_id)

                # Update simplified HTML
                simplified_html = self.html_simplifier.simplify_html(self.driver.page_source)

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
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-infobars')
        options.add_argument('--disable-notifications')
        options.add_argument('--disable-popup-blocking')
        options.add_argument('--ignore-certificate-errors')
        options.add_argument('--allow-running-insecure-content')
        options.add_argument('--disable-web-security')
        options.add_argument('--disable-features=VizDisplayCompositor')
        self.driver = webdriver.Chrome(options=options)
        self.driver.set_window_size(1920, 1080)
        self.driver.implicitly_wait(10)

    def get_next_action(self, context):
        prompt = f"""
        You are a web testing bot. Your current directive is: {context['directive']}

        Current page HTML (simplified):
        {context['current_page']}

        Known bugs to avoid:
        {chr(10).join(context['known_bugs'])}

        Previous bug summaries:
        {chr(10).join(context['previous_bug_summaries'])}

        Steps taken so far:
        {chr(10).join([f"Step {s['step']}: {s['action']} {s.get('element', '')}" for s in context['steps_taken']])}

        Current URL: {context['current_url']}

        Previous action status:
        {'SUCCESS' if len(context['steps_taken']) > 0 and context['steps_taken'][-1]['success'] else 'FAILED'}

        What should your next action be? Respond ONLY with the following:

        ```
        [newt_action_start]
        The type of action (e.g., "click", "fill", "select", "submit", "wait", "get_select_values")
        [newt_action_end]
        [newt_element_start]
        The CSS selector for the element to interact with
        [newt_element_end]
        [newt_value_start]
        For fill/select actions, the value to fill (if needed)
        [newt_value_end]
        [newt_friendly_description_start]
        A user-friendly description of what this action will do (e.g., "Click on the Show Log button")
        [newt_friendly_description_end]
        [newt_reasoning_start]
        Brief explanation of your choice, considering any previous failures
        [newt_reasoning_end]
        ```        

        IMPORTANT:
        1) If the previous action failed, choose a different approach or try a similar action with a different selector
        2) Avoid repeating actions that have already been attempted
        3) Consider the previous bugs and steps to determine a new approach
        4) Use the most specific, unique selector when interacting with an element

        THAT'S AN ORDER, SOLDIER!
        """

        action = self.llm.get_action(prompt)
        action_dict = {
            "action": extract_line_based_content(action, "[newt_action_start]", "[newt_action_end]"),
            "element": extract_line_based_content(action, "[newt_element_start]", "[newt_element_end]"),
            "value": extract_line_based_content(action, "[newt_value_start]", "[newt_value_end]"),
            "friendly_description": extract_line_based_content(action, "[newt_friendly_description_start]", "[newt_friendly_description_end]"),
            "reasoning": extract_line_based_content(action, "[newt_reasoning_start]", "[newt_reasoning_end]"),
        }

        # If previous action failed and we're not waiting, add a small wait to allow page to stabilize
        if context['steps_taken'] and not context['steps_taken'][-1]['success'] and action_dict['action'] not in ['wait', 'get_select_values']:
            action_dict['action'] = 'wait'
            action_dict['value'] = '2'
            action_dict['friendly_description'] = 'Wait to allow page to stabilize after previous failure'

        return action_dict

    def execute_action(self, action, step_number):
        element = None
        action_text = ""

        try:
            if action['action'] == 'click':
                element = self.driver.find_element(By.CSS_SELECTOR, action['element'])
                action_text = f"Clicked {action['element']}"
                self.highlight_element(element)
                element.click()
                self.handle_alerts()
            elif action['action'] == 'fill':
                element = self.driver.find_element(By.CSS_SELECTOR, action['element'])
                action_text = f"Filled {action['element']} with {action['value']}"
                self.highlight_element(element)
                element.send_keys(action['value'])
                self.handle_alerts()
            elif action['action'] == 'select':
                element = self.driver.find_element(By.CSS_SELECTOR, action['element'])
                action_text = f"Selected {action['value']} from {action['element']}"
                self.highlight_element(element)
                select = Select(element)
                select.select_by_value(action['value'])
                self.handle_alerts()
            elif action['action'] == 'submit':
                element = self.driver.find_element(By.CSS_SELECTOR, action['element'])
                action_text = f"Submitted form via {action['element']}"
                self.highlight_element(element)
                element.submit()
                self.handle_alerts()
            elif action['action'] == 'wait':
                time.sleep(int(action['value']))
                action_text = f"Waited for {action['value']} seconds"
                # Capture screenshot
                try:
                    full_screenshot_data = self.screenshot_capturer.capture_screenshot(self.driver)
                except Exception as e:
                    self.logger.error(f"Bot {self.bot_id} - Error capturing screenshot: {str(e)}")
                    full_screenshot_data = None

                self.db.add_step(self.bot_id, step_number, action_text, None, full_screenshot_data, action.get('friendly_description', ''))
                self.logger.info(f"Bot {self.bot_id} step {step_number} executed: {action_text}")

                result = {'success': True, 'screenshot': full_screenshot_data}
                return result
            elif action['action'] == 'get_select_values':
                element = self.driver.find_element(By.CSS_SELECTOR, action['element'])
                action_text = f"Got select values from {action['element']}"
                select = Select(element)
                options = [{'text': option.text, 'value': option.get_attribute('value')} for option in select.options]
                # Capture screenshot
                try:
                    full_screenshot_data = self.screenshot_capturer.capture_screenshot(self.driver)
                except Exception as e:
                    self.logger.error(f"Bot {self.bot_id} - Error capturing screenshot: {str(e)}")
                    full_screenshot_data = None

                self.db.add_step(self.bot_id, step_number, action_text, action['element'], full_screenshot_data, action.get('friendly_description', ''))
                self.logger.info(f"Bot {self.bot_id} step {step_number} executed: {action_text}")

                result = {'success': True, 'screenshot': full_screenshot_data}
                return result

            self.handle_alerts()

            # Capture screenshot
            try:
                full_screenshot_data = self.screenshot_capturer.capture_screenshot(self.driver)
            except Exception as e:
                self.logger.error(f"Bot {self.bot_id} - Error capturing screenshot: {str(e)}")
                full_screenshot_data = None

            self.unhighlight_element(element)

            self.db.add_step(self.bot_id, step_number, action_text, action.get('element', ''), full_screenshot_data, action.get('friendly_description', ''))
            self.logger.info(f"Bot {self.bot_id} step {step_number} executed: {action_text}")

            result = {'success': True, 'screenshot': full_screenshot_data}
            return result

        except Exception as e:
            error_msg = f"Failed to {action['action']} element {action.get('element', '')}: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            self.logger.debug(f"Bot {self.bot_id} - Full error details: {str(e)}", exc_info=True)
            full_screenshot_data = self.screenshot_capturer.capture_screenshot(self.driver)
            self.db.add_step(self.bot_id, step_number, error_msg, action.get('element', ''), full_screenshot_data, None, False)
            return {'success': False, 'screenshot': full_screenshot_data}

    def detect_bug(self, action, result):
        simplified_html = self.html_simplifier.simplify_html(self.driver.page_source)
        steps_context = chr(10).join([f"Step {s['step']}: {s['action']} {s.get('element', '')} {s.get('value', '')}" for s in self.steps_taken])
        prompt = f"""
        Analyze the following page content and determine if there's a bug based on the previous action.

        Current directive: {self.directive}

        Previous steps taken:
        {steps_context}

        Current action: {action['action']} {action.get('element', '')}

        Known bugs to avoid:
        {chr(10).join(self.known_bug_summaries)}

        Page content:
        {simplified_html}

        Consider:
        1. Any error messages, exceptions, or malfunctions
        2. Logical blocking - elements that should be interactive but aren't
        3. Typos or incorrect text that indicates a problem
        4. Unexpected page states or behaviors
        5. Comparison with known bugs to determine if this is a new issue

        Respond ONLY with the following:

        ```
        [newt_isbug_start]
        True or False
        [newt_isbug_end]
        [newt_severity_start]
        High, Medium or Low
        [newt_severity_end]
        [newt_description_start]
        Detailed explanation of why this is a bug
        [newt_description_end]
        [newt_recommendation_start]
        How to fix or work around this bug
        [newt_recommendation_end]
        ```
        """

        if Config.get_log_prompts():
            ticks = int(time.time() * 1000)
            prompt_filename = f"data/bot_{self.bot_id}_{ticks}_prompt.txt"
            with open(prompt_filename, "w") as f:
                f.write(prompt)

        self.logger.debug(f"Bot {self.bot_id} - Bug detection prompt: {prompt[:500]}...")
        analysis = self.llm.get_action(prompt)

        if Config.get_log_prompts():
            ticks = int(time.time() * 1000)
            response_filename = f"data/bot_{self.bot_id}_{ticks}_response.txt"
            with open(response_filename, "w") as f:
                f.write(analysis)

        self.logger.debug(f"Bot {self.bot_id} - Bug detection result: {analysis}")
        analysis_object = {
            "is_bug": extract_line_based_content(analysis, "[newt_isbug_start]", "[newt_isbug_end]"),
            "severity": extract_line_based_content(analysis, "[newt_severity_start]", "[newt_severity_end]"),
            "description": extract_line_based_content(analysis, "[newt_description_start]", "[newt_description_end]"),
            "recommendation": extract_line_based_content(analysis, "[newt_recommendation_start]", "[newt_recommendation_end]"),
        }
        return analysis_object.get('is_bug', False), analysis_object

    def report_bug(self, action, result, context, analysis):
        summary = f"NEWT Bug Detected: {analysis['description']}"
        steps = json.dumps(context['steps_taken'])

        # Read screenshot data for embedding
        screenshot_data = None
        if result['screenshot']:
            try:
                with open(result['screenshot'], 'rb') as img_file:
                    screenshot_data = img_file.read()
            except Exception as e:
                self.logger.error(f"Bot {self.bot_id} - Error reading screenshot: {str(e)}")

        bug_id = self.db.add_bug(self.bot_id, summary, steps, screenshot_data)
        knowledge = analysis["description"] + chr(10) + analysis["recommendation"]
        self.db.add_knowledge(bug_id, knowledge)

        self.bug_reporter.send_notification(summary, knowledge, analysis.get('severity', 'medium'))
        return bug_id

    def is_directive_complete(self):
        simplified_html = self.html_simplifier.simplify_html(self.driver.page_source)
        steps_context = chr(10).join([f"Step {s['step']}: {s['action']} {s.get('element', '')} {s.get('value', '')}" for s in self.steps_taken])
        prompt = f"""
        Based on the current page content and the NEWT bot's directive, determine if the testing is complete.

        Current directive: {self.directive}

        Previous steps taken:
        {steps_context}

        Known bugs to avoid:
        {chr(10).join(self.known_bug_summaries)}

        Current page content: {simplified_html}

        Consider:
        1. Has the directive been fully satisfied?
        2. Are there any remaining interactive elements that need testing?
        3. Is there any indication that testing should continue?
        4. Have all major functionality areas been covered?

        Respond ONLY with the following:

        ```
        [newt_iscomplete_start]
        True or False
        [newt_iscomplete_end]
        [newt_reasoning_start]
        Detailed explanation of why testing should continue or stop
        [newt_reasoning_end]
        [newt_nextarea_start]
        If not complete, suggest the next area to test
        [newt_nextarea_end]
        ```
        """

        if Config.get_log_prompts():
            ticks = int(time.time() * 1000)
            prompt_filename = f"data/bot_{self.bot_id}_{ticks}_prompt.txt"
            with open(prompt_filename, "w") as f:
                f.write(prompt)

        completion_check = self.llm.get_action(prompt)

        if Config.get_log_prompts():
            ticks = int(time.time() * 1000)
            response_filename = f"data/bot_{self.bot_id}_{ticks}_response.txt"
            with open(response_filename, "w") as f:
                f.write(completion_check)

        parsed_completion_check = extract_line_based_content(completion_check, "[newt_iscomplete_start]", "[newt_iscomplete_end]")
        return parsed_completion_check == "True"

    def is_same_domain(self, url1, url2):
        from urllib.parse import urlparse
        domain1 = urlparse(url1).netloc
        domain2 = urlparse(url2).netloc
        return domain1 == domain2

    def handle_alerts(self):
        """Handle any unexpected alerts that may appear during bot execution"""
        try:
            alert = self.driver.switch_to.alert
            alert_text = alert.text
            alert.accept()
            self.logger.info(f"Bot {self.bot_id} - Accepted alert: {alert_text}")
            return True
        except:
            return False

    def cleanup(self):
        if self.driver:
            self.driver.quit()
            self.logger.info(f"Bot {self.bot_id} driver closed")
        self.db.update_bot_status(self.bot_id, 'completed', datetime.now().isoformat())
        self.bot_manager.remove_bot(self.bot_id)
        self.logger.info(f"Bot {self.bot_id} completed and removed from manager")

    def highlight_element(self, element):
        """Highlight an element to make it visible in the screenshot"""

        # Add highlighting style
        self.driver.execute_script("""
            arguments[0].style.border = '3px solid #ff0000';
            arguments[0].style.boxShadow = '0 0 10px 5px rgba(255, 0, 0, 0.5)';
        """, element)

    def unhighlight_element(self, element):
        """Highlight an element to make it visible in the screenshot"""

        # Add highlighting style
        self.driver.execute_script("""
            arguments[0].style.border = '';
            arguments[0].style.boxShadow = '';
        """, element)
