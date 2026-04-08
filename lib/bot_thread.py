import threading
import time
import json
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime
from lib.config import Config
from lib.llm_integration import extract_line_based_content

class BotThread(threading.Thread):
    def __init__(self, bot_id, start_url, directive, db, bot_manager, bug_reporter, html_simplifier, screenshot_capturer, llm_factory, logger, steps_taken=None):
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
        self.logger = logger
        self.default_wait = Config.get_default_wait()
        self.max_failures = Config.get_max_failures()
        self.failure_count = 0
        self.max_failures = 3
        self.curious_mode = True
        self.select_options_cache = {}

    def run(self):
        self.db.update_bot_status(self.bot_id, 'running', datetime.now().isoformat())

        try:
            self.initialize_driver()
            self.llm = self.llm_factory.create_llm()

            step_number = len(self.db.get_steps(self.bot_id)) + 1

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
                    self.failure_count += 1
                    if self.failure_count >= self.max_failures:
                        break
                    time.sleep(5)
                    continue

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
                    'known_bugs': json.dumps(self.db.get_bugs(self.bot_id, False)),
                    'steps_taken': self.db.get_steps(self.bot_id),
                    'current_url': current_url,
                    'select_options_cache': self.select_options_cache
                }

                action = self.get_next_action(context)

                # Execute action
                result = self.execute_action(action, step_number)
                step_number += 1

                # Check for bugs
                try:
                    analysis_result, analysis = self.detect_bug()
                    if str(analysis_result).lower() == "true":
                        self.report_bug(action, result, context, analysis)
                except Exception as e:
                    self.logger.error(f"Bot {self.bot_id} - Error in bug detection: {str(e)}")
                    self.failure_count += 1

                # Update simplified HTML
                simplified_html = self.html_simplifier.simplify_html(self.driver.page_source)

                # Check if directive is complete
                try:
                    if self.is_directive_complete():
                        break
                except Exception as e:
                    self.logger.error(f"Bot {self.bot_id} - Error in completion check: {str(e)}")
                    self.failure_count += 1

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
        steps_taken = self.db.get_steps(self.bot_id)
        available_selectors = """
Available Selenium selectors:
1. CSS_SELECTOR: Select elements by CSS selector
2. ID: Select element by ID attribute
3. NAME: Select element by name attribute
4. XPATH: Select element by XPath expression
5. CLASS_NAME: Select element by class name
6. TAG_NAME: Select element by HTML tag name
7. LINK_TEXT: Select link by exact text
8. PARTIAL_LINK_TEXT: Select link by partial text

Available actions:
1. CLICK: Click on an element
2. SEND_KEYS: Send text to an input element
3. SELECT_BY_VALUE: Select option in dropdown by value
4. SELECT_BY_TEXT: Select option in dropdown by text
5. GET_SELECT_OPTIONS: Get all options for a select element
6. CLEAR: Clear an input field
7. SUBMIT: Submit a form
8. WAIT: Wait for a specific element to be present

For GET_SELECT_OPTIONS, specify the element selector and it will return all available options.
        """

        prompt = f"""
You are a web testing bot. Your current directive is: {context['directive']}

Current page HTML (simplified):
{context['current_page']}

{f"You previously requested these select options:{chr(10) + json.dumps(self.select_options_cache)}" if len(self.select_options_cache) == 1 else '' }

Known bugs to avoid:
{context['known_bugs']}

Steps taken:
{self.get_step_text()}

Current URL: {context['current_url']}

Previous action status:
{'SUCCESS' if len(steps_taken) > 0 and steps_taken[-1]['success'] else 'FAILED' if len(steps_taken) > 0 else 'N/A'}

{available_selectors}

What should your next action be? Respond ONLY with the following:

```
[newt_action_start]
ACTION_TYPE
[newt_action_end]
[newt_element_selector_type_start]
SELECTOR_TYPE (CSS_SELECTOR, ID, NAME, XPATH, CLASS_NAME, TAG_NAME, LINK_TEXT, PARTIAL_LINK_TEXT)
[newt_element_selector_type_end]
[newt_element_selector_value_start]
SELECTOR_VALUE
[newt_element_selector_value_end]
[newt_value_start]
VALUE_TO_SEND (if applicable, otherwise leave empty)
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
4) Use the appropriate Selenium action type for what you want to do
5) For input fields, use SEND_KEYS with the value you want to send
6) For dropdowns, use SELECT_BY_VALUE or SELECT_BY_TEXT
7) For GET_SELECT_OPTIONS, only provide the element selector and it will return the available options
8) Be curious! Try edge cases, unusual inputs, and attempt to break things within the bounds of your directive
9) Your goal is to get a high score - and your score is computed by the number of unique steps taken to the power of the number of identified bugs
10) ONLY determine your next action based on the known current page and nothing else

THAT'S AN ORDER, SOLDIER!
        """

        if Config.get_log_prompts():
            ticks = int(time.time() * 1000)
            prompt_filename = f"data/bot_{self.bot_id}_{ticks}_prompt.txt"
            with open(prompt_filename, "w") as f:
                f.write(prompt)

        try:
            action = self.llm.get_action(prompt)

            if Config.get_log_prompts():
                ticks = int(time.time() * 1000)
                response_filename = f"data/bot_{self.bot_id}_{ticks}_response.txt"
                with open(response_filename, "w") as f:
                    f.write(action)

            action_dict = {
                "action": extract_line_based_content(action, "[newt_action_start]", "[newt_action_end]"),
                "element_selector_type": extract_line_based_content(action, "[newt_element_selector_type_start]", "[newt_element_selector_type_end]"),
                "element_selector_value": extract_line_based_content(action, "[newt_element_selector_value_start]", "[newt_element_selector_value_end]"),
                "value": extract_line_based_content(action, "[newt_value_start]", "[newt_value_end]"),
                "friendly_description": extract_line_based_content(action, "[newt_friendly_description_start]", "[newt_friendly_description_end]"),
                "reasoning": extract_line_based_content(action, "[newt_reasoning_start]", "[newt_reasoning_end]"),
            }

            return action_dict
        except Exception as e:
            self.logger.error(f"Bot {self.bot_id} - Error getting next action: {str(e)}")
            return None

    def execute_action(self, action, step_number):
        try:
            self.select_options_cache = {}
            action_type = action['action']
            element_selector_type = action.get('element_selector_type', 'CSS_SELECTOR')
            element_selector_value = action.get('element_selector_value', '')
            value = action.get('value', '')

            # Map selector type to Selenium By enum
            selector_map = {
                'CSS_SELECTOR': By.CSS_SELECTOR,
                'ID': By.ID,
                'NAME': By.NAME,
                'XPATH': By.XPATH,
                'CLASS_NAME': By.CLASS_NAME,
                'TAG_NAME': By.TAG_NAME,
                'LINK_TEXT': By.LINK_TEXT,
                'PARTIAL_LINK_TEXT': By.PARTIAL_LINK_TEXT
            }

            selector_type = selector_map.get(element_selector_type, By.CSS_SELECTOR)
            selector_value = element_selector_value

            action_text = f"{action_type} on {element_selector_type}:{element_selector_value}"

            # Capture screenshot before action
            try:
                full_screenshot_data = self.screenshot_capturer.capture_screenshot(self.driver)
            except Exception as e:
                self.logger.error(f"Bot {self.bot_id} - Error capturing screenshot: {str(e)}")
                full_screenshot_data = None

            # Execute the action using Selenium
            if action_type == 'CLICK':
                try:
                    element = WebDriverWait(self.driver, self.default_wait).until(
                        EC.element_to_be_clickable((selector_type, selector_value))
                    )
                    element.click()
                except Exception as e:
                    # Fallback: try to find by CSS selector if ID selector failed
                    if selector_type == By.ID:
                        try:
                            self.logger.info(f"Bot {self.bot_id} - ID selector failed, trying CSS selector")
                            element = WebDriverWait(self.driver, self.default_wait).until(
                                EC.element_to_be_clickable((By.CSS_SELECTOR, selector_value))
                            )
                            element.click()
                        except Exception as e2:
                            raise Exception(f"Failed with both ID and CSS selectors: {str(e2)}")
                    else:
                        raise e
            elif action_type == 'SEND_KEYS':
                element = WebDriverWait(self.driver, self.default_wait).until(
                    EC.presence_of_element_located((selector_type, selector_value))
                )
                element.clear()
                element.send_keys(value)
            elif action_type == 'SELECT_BY_VALUE':
                select = Select(WebDriverWait(self.driver, self.default_wait).until(
                    EC.presence_of_element_located((selector_type, selector_value))
                ))
                select.select_by_value(value)
            elif action_type == 'SELECT_BY_TEXT':
                select = Select(WebDriverWait(self.driver, self.default_wait).until(
                    EC.presence_of_element_located((selector_type, selector_value))
                ))
                select.select_by_visible_text(value)
            elif action_type == 'GET_SELECT_OPTIONS':
                select = Select(WebDriverWait(self.driver, self.default_wait).until(
                    EC.presence_of_element_located((selector_type, selector_value))
                ))
                options = [opt.text for opt in select.options]
                self.select_options_cache[selector_value] = options
                action_text = f"Got select options for {selector_value}: {', '.join(options)}"
            elif action_type == 'CLEAR':
                element = WebDriverWait(self.driver, self.default_wait).until(
                    EC.presence_of_element_located((selector_type, selector_value))
                )
                element.clear()
            elif action_type == 'SUBMIT':
                element = WebDriverWait(self.driver, self.default_wait).until(
                    EC.presence_of_element_located((selector_type, selector_value))
                )
                element.submit()
            elif action_type == 'WAIT':
                WebDriverWait(self.driver, self.default_wait).until(
                    EC.presence_of_element_located((selector_type, selector_value))
                )

            # Wait for page to settle after action
            time.sleep(self.default_wait)

            # Capture screenshot after action
            try:
                full_screenshot_data = self.screenshot_capturer.capture_screenshot(self.driver)
            except Exception as e:
                self.logger.error(f"Bot {self.bot_id} - Error capturing screenshot: {str(e)}")
                full_screenshot_data = None

            self.db.add_step(self.bot_id, step_number, action_text, f"{element_selector_type}:{element_selector_value}", full_screenshot_data, action.get('friendly_description', ''), action.get('reasoning', ''))
            self.logger.info(f"Bot {self.bot_id} step {step_number} executed: {action_text}")

            result = {'success': True, 'screenshot': full_screenshot_data}
            return result

        except Exception as e:
            error_msg = f"Failed to execute action {action_type} on {action['element']}: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            self.logger.debug(f"Bot {self.bot_id} - Full error details: {str(e)}", exc_info=True)

            # Try to get a screenshot even if the action failed
            try:
                full_screenshot_data = self.screenshot_capturer.capture_screenshot(self.driver)
            except Exception as screenshot_error:
                self.logger.error(f"Bot {self.bot_id} - Error capturing error screenshot: {str(screenshot_error)}")
                full_screenshot_data = None

            element_selector_type = action.get('element_selector_type', 'CSS_SELECTOR')
            element_selector_value = action.get('element_selector_value', '')
            self.db.add_step(self.bot_id, step_number, error_msg, f"{element_selector_type}:{element_selector_value}", full_screenshot_data, action.get('friendly_description', ''), action.get('reasoning', ''), False)
            return {'success': False, 'screenshot': full_screenshot_data}

    def detect_bug(self):
        simplified_html = self.html_simplifier.simplify_html(self.driver.page_source)
        prompt = f"""
Analyze the following page content and determine if there's a new bug based on the previous action.

Current directive: {self.directive}

Steps taken:
{self.get_step_text()}

Known bugs:
{json.dumps(self.db.get_bugs(self.bot_id, False))}

Page content:
{simplified_html}

{f"You previously requested these select options:{chr(10) + json.dumps(self.select_options_cache)}" if len(self.select_options_cache) == 1 else '' }

Consider:
1. Any error messages, exceptions, or malfunctions
2. Logical blocking - elements that should be interactive but aren't
3. Typos or incorrect text that indicates a problem
4. Unexpected page states or behaviors
5. Edge cases or unusual conditions that might indicate a bug

Avoid:
1. Reporting a bug that is the same as an existing known bug
2. Reporting a bug that is due to an error in the test app (such as a bad selector), and not in the target application

Respond ONLY with the following:

```
[newt_isnewbug_start]
True or False
[newt_isnewbug_end]
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

        try:
            self.logger.debug(f"Bot {self.bot_id} - Bug detection prompt: {prompt[:500]}...")
            analysis = self.llm.get_action(prompt)

            if Config.get_log_prompts():
                ticks = int(time.time() * 1000)
                response_filename = f"data/bot_{self.bot_id}_{ticks}_response.txt"
                with open(response_filename, "w") as f:
                    f.write(analysis)

            self.logger.debug(f"Bot {self.bot_id} - Bug detection result: {analysis}")
            analysis_object = {
                "is_bug": extract_line_based_content(analysis, "[newt_isnewbug_start]", "[newt_isnewbug_end]"),
                "severity": extract_line_based_content(analysis, "[newt_severity_start]", "[newt_severity_end]"),
                "description": extract_line_based_content(analysis, "[newt_description_start]", "[newt_description_end]"),
                "recommendation": extract_line_based_content(analysis, "[newt_recommendation_start]", "[newt_recommendation_end]"),
            }
            return analysis_object.get('is_bug', False), analysis_object
        except Exception as e:
            self.logger.error(f"Bot {self.bot_id} - Error in bug detection: {str(e)}")
            return False, {}

    def report_bug(self, action, result, context, analysis):
        summary = f"NEWT Bug Detected: {analysis['description']}"
        steps = json.dumps(context['steps_taken'])

        try:
            bug_id = self.db.add_bug(self.bot_id, summary, steps)
            knowledge = analysis["description"] + chr(10) + analysis["recommendation"]
            self.db.add_knowledge(bug_id, knowledge)

            self.bug_reporter.send_notification(summary, knowledge, analysis.get('severity', 'medium'))
            return bug_id
        except Exception as e:
            self.logger.error(f"Bot {self.bot_id} - Error reporting bug: {str(e)}")
            return None

    def is_directive_complete(self):
        simplified_html = self.html_simplifier.simplify_html(self.driver.page_source)
        prompt = f"""
Based on the current page content and the NEWT bot's directive, determine if the testing is complete.

Current directive: {self.directive}

Steps taken:
{self.get_step_text()}

Known bugs to avoid:
{json.dumps(self.db.get_bugs(self.bot_id, False))}

Current page content: {simplified_html}

{f"You previously requested these select options:{chr(10) + json.dumps(self.select_options_cache)}" if len(self.select_options_cache) == 1 else '' }

Consider:
1. Has the directive been fully satisfied?
2. Are there any remaining interactive elements that need testing?
3. Is there any indication that testing should continue?
4. Have all major functionality areas been covered?
5. Have you tried edge cases and unusual scenarios?

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

        try:
            completion_check = self.llm.get_action(prompt)

            if Config.get_log_prompts():
                ticks = int(time.time() * 1000)
                response_filename = f"data/bot_{self.bot_id}_{ticks}_response.txt"
                with open(response_filename, "w") as f:
                    f.write(completion_check)

            parsed_completion_check = extract_line_based_content(completion_check, "[newt_iscomplete_start]", "[newt_iscomplete_end]")
            return parsed_completion_check == "True"
        except Exception as e:
            self.logger.error(f"Bot {self.bot_id} - Error in completion check: {str(e)}")
            return False

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

    def get_step_text(self):
        steps = self.db.get_steps(self.bot_id)
        return chr(10).join([f"Step {s['step_number']}: {s['action']}"
                             + chr(10)
                             + "Element: "
                             + s['element']
                             + chr(10)
                             + "Friendly Description: "
                             + s['friendly_description']
                             + chr(10)
                             + "Reasoning: "
                             + s['reasoning']
                             + chr(10)
                             + "Success: "
                             + ("Yes" if s['success'] else "No") for s in steps])
