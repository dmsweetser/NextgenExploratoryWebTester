import random
import threading
import time
import json
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from datetime import datetime
from lib.config import Config
from lib.llm_integration import extract_line_based_content
import difflib

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
        self.select_options_cache = {}
        self.previous_html = ""
        self.current_html = ""
        self.max_diff_lines = Config.get_max_diff_lines() if hasattr(Config, 'get_max_diff_lines') else 10
        self.restarted = False
        self.action_chains = None

    def run(self):
        self.db.update_bot_status(self.bot_id, 'running', datetime.now().isoformat())

        try:
            self.initialize_driver()
            self.llm = self.llm_factory.create_llm()
            self.action_chains = ActionChains(self.driver)

            step_number = len(self.db.get_steps(self.bot_id)) + 1

            if self.restarted:
                self.record_restart_step(step_number)
                step_number += 1
                self.restarted = False

            try:
                self.driver.get(self.start_url)
                # Handle any unexpected alerts
                try:
                    alert = self.driver.switch_to.alert
                    alert.accept()
                except:
                    pass
                time.sleep(2)
                self.previous_html = self.html_simplifier.simplify_html(self.html_simplifier.get_visible_html(self.driver))
            except Exception as e:
                self.logger.error(f"Bot {self.bot_id} - Error navigating to URL: {str(e)}")
                self.failure_count += 1

            while not self.stop_event.is_set() and self.failure_count < self.max_failures:
                self.current_html = self.html_simplifier.simplify_html(self.html_simplifier.get_visible_html(self.driver))
                current_url = self.driver.current_url
                try:
                    # Check domain to prevent cross-domain navigation
                    if not self.is_same_domain(current_url, self.start_url):
                        logging.warning(f"Bot {self.bot_id} attempted to navigate to different domain: {current_url}")
                        break

                    # Build context for LLM with failure tracking
                    steps_taken = self.db.get_steps(self.bot_id)
                    recent_failures = sum(1 for step in steps_taken[-5:] if not step['success'])

                    context = {
                        'directive': self.directive,
                        'previous_page': self.previous_html,
                        'current_page': self.get_html_diff(self.previous_html, self.current_html),
                        'known_bugs': json.dumps(self.db.get_bugs(self.bot_id, False)),
                        'steps_taken': steps_taken,
                        'current_url': current_url,
                        'select_options_cache': self.select_options_cache,
                        'recent_failures': recent_failures,
                        'failure_count': self.failure_count
                    }

                    action = self.get_next_action(context)
                    if not action:
                        self.failure_count += 1
                        continue

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

                    # Update previous HTML for next iteration
                    self.previous_html = self.current_html

                    # Check if directive is complete
                    if Config.get_allow_conclude():
                        try:
                            if self.is_directive_complete():
                                break
                        except Exception as e:
                            self.logger.error(f"Bot {self.bot_id} - Error in completion check: {str(e)}")
                            self.failure_count += 1

                    # Reset failure count on successful action
                    if result.get('success', False):
                        self.failure_count = max(0, self.failure_count - 1)

                except Exception as e:
                    self.logger.error(f"Bot {self.bot_id} - Error in main loop: {str(e)}")
                    self.failure_count += 1
                    time.sleep(2)  # Brief pause to prevent rapid error loops

        except Exception as e:
            logging.error(f"Error in bot {self.bot_id}: {str(e)}")
        finally:
            self.cleanup()

    def record_restart_step(self, step_number):
        """Record a step indicating the bot was restarted"""
        try:
            restart_description = "Bot was restarted and returned to initial state"
            restart_reasoning = "The bot was stopped by the user and then restarted. This step records the restart event to provide context for subsequent actions."

            # Capture screenshot of the initial state after restart
            full_screenshot_data = None
            try:
                full_screenshot_data = self.screenshot_capturer.capture_screenshot(self.driver)
            except Exception as e:
                self.logger.error(f"Bot {self.bot_id} - Error capturing restart screenshot: {str(e)}")

            self.db.add_step(
                self.bot_id,
                step_number,
                "SYSTEM: BOT_RESTART",
                "SYSTEM:RESTART",
                full_screenshot_data,
                restart_description,
                restart_reasoning,
                True
            )
            self.logger.info(f"Bot {self.bot_id} recorded restart step {step_number}")
        except Exception as e:
            self.logger.error(f"Bot {self.bot_id} - Error recording restart step: {str(e)}")

    def get_html_diff(self, before_html, after_html):
        """Generate a diff between before and after HTML, showing only changes if they're small"""
        if not before_html or not after_html:
            return after_html

        before_lines = before_html.splitlines()
        after_lines = after_html.splitlines()

        diff = list(difflib.unified_diff(before_lines, after_lines, n=0))

        if len(diff) < len(after_lines) * 0.7 and len(diff) > 0:
            return "\n".join(diff)
        elif before_lines != after_lines:
            return after_html
        else:
            return "The AFTER HTML was identical to the BEFORE HTML"

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
        self.driver.set_window_size(1920, 10000)
        self.driver.implicitly_wait(10)
        self.action_chains = ActionChains(self.driver)

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
2. SEND_KEYS: Send text to an input element (human-like typing)
3. SELECT_BY_VALUE: Select option in dropdown by value
4. SELECT_BY_TEXT: Select option in dropdown by text
5. GET_SELECT_OPTIONS: Get all options for a select element
6. CLEAR: Clear an input field
7. SUBMIT: Submit a form
8. WAIT: Wait for a specific element to be present
9. SCROLL_TO: Scroll to a specific element
10. HOVER: Hover over an element
        """

        newt_operation_summary = """
NEWT OPERATION SUMMARY:
You are an AI-driven exploratory web testing bot. Your goal is to thoroughly test web applications by:
1. Making intelligent decisions about what actions to take based on the current page state
2. Analyzing page content for REAL, FUNCTIONAL bugs that impact end users
3. Exploring edge cases and unusual scenarios within the bounds of your directive
4. Being curious and trying to find REAL issues, not test apparatus limitations

IMPORTANT NOTES ABOUT THE HTML YOU RECEIVE:
- The HTML is SIMPLIFIED to remove noise and focus on semantic content
- Styles, scripts, and non-essential attributes are removed
- Hidden elements (display:none, visibility:hidden) are removed
- Only visible, semantic content is preserved
- This is INTENTIONAL to help you focus on functionality, not presentation
- Missing styles or layout issues are NOT bugs - focus on functionality and user experience

CRITICAL BUG DETECTION GUIDELINES:
1. ONLY report bugs that would genuinely impact end users
2. IGNORE issues related to the testing apparatus (e.g., "element not interactable" unless you've confirmed it's not a test limitation)
3. FOCUS on functional issues like:
   - Broken functionality that prevents task completion
   - Logical inconsistencies in application behavior
   - Data corruption or loss
   - Security vulnerabilities
   - Accessibility issues that prevent usage
   - Unexpected behavior that would confuse users
4. DO NOT report:
   - Visual styling issues
   - Missing classes or attributes in simplified HTML
   - Temporary loading states
   - Issues that could be resolved by further interaction
   - Test apparatus limitations

You receive:
- The testing directive (what you should test)
- The BEFORE HTML (complete page state before your last action)
- The AFTER HTML (either a diff showing changes or the complete page state after your last action)
- Steps you've already taken
- Known bugs to avoid
- Current URL and select options cache

Your output must follow the strict format provided in the prompt.
"""

        prompt = f"""
{newt_operation_summary}

Current directive: {context['directive']}

Page HTML BEFORE the most recent action (simplified):
{context['previous_page']}

Page HTML AFTER the most recent action (simplified):
{context['current_page']}

{f"You previously requested these select options:{chr(10) + json.dumps(self.select_options_cache)}" if len(self.select_options_cache) == 1 else '' }

Known bugs to avoid:
{context['known_bugs']}

Steps taken:
{self.get_step_text()}

Current URL: {context['current_url']}

Previous action status:
{'SUCCESS' if len(steps_taken) > 0 and steps_taken[-1]['success'] else 'FAILED' if len(steps_taken) > 0 else 'N/A'}

Recent failures in last 5 steps: {context['recent_failures']}
Total failures: {context['failure_count']}

IMPORTANT: If you have failed 3 or more times in a row, or if you see you are not making progress, you MUST try a completely different approach!

{available_selectors}

What should your next action be? Respond ONLY with the following:

```
~newt_action_start~
ACTION_TYPE
~newt_action_end~
~newt_element_selector_type_start~
SELECTOR_TYPE (CSS_SELECTOR, ID, NAME, XPATH, CLASS_NAME, TAG_NAME, LINK_TEXT, PARTIAL_LINK_TEXT)
~newt_element_selector_type_end~
~newt_element_selector_value_start~
SELECTOR_VALUE
~newt_element_selector_value_end~
~newt_value_start~
VALUE_TO_SEND (if applicable, otherwise leave empty)
~newt_value_end~
~newt_friendly_description_start~
A user-friendly description of what this action will do (e.g., "Click on the Show Log button")
~newt_friendly_description_end~
~newt_reasoning_start~
Brief explanation of your choice, considering any previous failures and the changes observed between the BEFORE and AFTER HTML. Focus on finding REAL, FUNCTIONAL bugs that impact end users.
~newt_reasoning_end~
```

IMPORTANT:
1) If the previous action failed, choose a different approach or try a similar action with a different selector
2) Avoid repeating actions that have already been attempted
3) Consider the previous bugs and steps to determine a new approach
4) Use the appropriate Selenium action type for what you want to do
5) For input fields, use SEND_KEYS with the value you want to send (it will be typed human-like)
6) For dropdowns, use SELECT_BY_VALUE or SELECT_BY_TEXT
7) For GET_SELECT_OPTIONS, only provide the element selector and it will return the available options
8) Be curious! Try something UNUSUAL, EDGE CASE, or POTENTIALLY BREAKING within the bounds of your directive.
9) Your goal is to find REAL bugs that impact end users, not test apparatus limitations
10) ONLY determine your next action based on the known current page and nothing else
11) Pay special attention to the differences between the BEFORE and AFTER HTML to understand what changed and guide your next action
12) Focus on FUNCTIONAL issues that would genuinely impact end users

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
                "action": extract_line_based_content(action, "~newt_action_start~", "~newt_action_end~"),
                "element_selector_type": extract_line_based_content(action, "~newt_element_selector_type_start~", "~newt_element_selector_type_end~") or "CSS_SELECTOR",
                "element_selector_value": extract_line_based_content(action, "~newt_element_selector_value_start~", "~newt_element_selector_value_end~") or "",
                "value": extract_line_based_content(action, "~newt_value_start~", "~newt_value_end~") or "",
                "friendly_description": extract_line_based_content(action, "~newt_friendly_description_start~", "~newt_friendly_description_end~") or "",
                "reasoning": extract_line_based_content(action, "~newt_reasoning_start~", "~newt_reasoning_end~") or "",
                "element": f"{extract_line_based_content(action, '~newt_element_selector_type_start~', '~newt_element_selector_type_end~') or 'CSS_SELECTOR'}:{extract_line_based_content(action, '~newt_element_selector_value_start~', '~newt_element_selector_value_end~') or ''}"
            }

            return action_dict
        except Exception as e:
            self.logger.error(f"Bot {self.bot_id} - Error getting next action: {str(e)}")
            return None

    def _type_text_reliably(self, element, text):
        """Type text into an element with human-like delays and error handling"""
        try:
            for char in text:
                element.send_keys(char)
                # Add small delay between keystrokes
                time.sleep(.5)
        except Exception as e:
            self.logger.error(f"Error typing text reliably: {str(e)}")
            # Fallback to standard send_keys if the reliable method fails
            element.send_keys(text)

    def execute_action(self, action, step_number):
        try:
            self.select_options_cache = {}
            if not action:
                return {'success': False, 'screenshot': None}

            action_type = action.get('action', '')
            element_selector_type = action.get('element_selector_type', 'CSS_SELECTOR')
            element_selector_value = action.get('element_selector_value', '')
            value = action.get('value', '')
            friendly_description = action.get('friendly_description', '')
            reasoning = action.get('reasoning', '')

            # Validate required fields
            if not action_type or not element_selector_type or not element_selector_value:
                error_msg = f"Invalid action parameters: {action}"
                self.logger.error(error_msg)
                return {'success': False, 'screenshot': None}

            # Map selector type to Selenium By enum with preference order
            selector_map = {
                'ID': By.ID,
                'NAME': By.NAME,
                'CSS_SELECTOR': By.CSS_SELECTOR,
                'CLASS_NAME': By.CLASS_NAME,
                'LINK_TEXT': By.LINK_TEXT,
                'PARTIAL_LINK_TEXT': By.PARTIAL_LINK_TEXT,
                'TAG_NAME': By.TAG_NAME,
                'XPATH': By.XPATH
            }

            selector_type = selector_map.get(element_selector_type, By.CSS_SELECTOR)
            selector_value = element_selector_value

            action_text = f"{action_type} on {element_selector_type}:{element_selector_value}"

            # Capture screenshot before action
            screenshot_data = None
            try:
                screenshot_data = self.screenshot_capturer.capture_screenshot(self.driver)
                full_screenshot_data = screenshot_data['full']
                thumbnail_data = screenshot_data['thumbnail']
            except Exception as e:
                self.logger.error(f"Bot {self.bot_id} - Error capturing screenshot: {str(e)}")
                full_screenshot_data = None
                thumbnail_data = None

            # Execute the action using Selenium with error handling
            try:
                if action_type == 'CLICK':
                    try:
                        element = WebDriverWait(self.driver, self.default_wait).until(
                            EC.element_to_be_clickable((selector_type, selector_value))
                        )
                        self.highlight_element(element)
                        self.action_chains.move_to_element(element).click().perform()
                        self.unhighlight_element(element)
                    except Exception as e:
                        # Fallback: try to find by CSS selector if ID selector failed
                        if selector_type == By.ID:
                            try:
                                self.logger.info(f"Bot {self.bot_id} - ID selector failed, trying CSS selector")
                                element = WebDriverWait(self.driver, self.default_wait).until(
                                    EC.element_to_be_clickable((By.CSS_SELECTOR, selector_value))
                                )
                                self.highlight_element(element)
                                self.action_chains.move_to_element(element).click().perform()
                                self.unhighlight_element(element)
                            except Exception as e2:
                                raise Exception(f"Failed with both ID and CSS selectors: {str(e2)}")
                        else:
                            raise e
                elif action_type == 'SEND_KEYS':
                    element = WebDriverWait(self.driver, self.default_wait).until(
                        EC.presence_of_element_located((selector_type, selector_value))
                    )
                    self.highlight_element(element)
                    element.clear()
                    self._type_text_reliably(element, value)
                    self.unhighlight_element(element)
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
                    self.highlight_element(element)
                    element.clear()
                    self.unhighlight_element(element)
                elif action_type == 'SUBMIT':
                    element = WebDriverWait(self.driver, self.default_wait).until(
                        EC.presence_of_element_located((selector_type, selector_value))
                    )
                    self.highlight_element(element)
                    element.submit()
                    self.unhighlight_element(element)
                elif action_type == 'WAIT':
                    WebDriverWait(self.driver, self.default_wait).until(
                        EC.presence_of_element_located((selector_type, selector_value))
                    )
                elif action_type == 'SCROLL_TO':
                    element = WebDriverWait(self.driver, self.default_wait).until(
                        EC.presence_of_element_located((selector_type, selector_value))
                    )
                    self.highlight_element(element)
                    self.action_chains.scroll_to_element(element).perform()
                    self.unhighlight_element(element)
                elif action_type == 'HOVER':
                    element = WebDriverWait(self.driver, self.default_wait).until(
                        EC.presence_of_element_located((selector_type, selector_value))
                    )
                    self.highlight_element(element)
                    self.action_chains.move_to_element(element).perform()
                    self.unhighlight_element(element)
                else:
                    raise Exception(f"Unknown action type: {action_type}")

                # Wait for page to settle after action
                time.sleep(self.default_wait)

                # Capture screenshot after action
                try:
                    screenshot_data = self.screenshot_capturer.capture_screenshot(self.driver)
                    full_screenshot_data = screenshot_data['full']
                    thumbnail_data = screenshot_data['thumbnail']
                except Exception as e:
                    self.logger.error(f"Bot {self.bot_id} - Error capturing screenshot after action: {str(e)}")
                    full_screenshot_data = None
                    thumbnail_data = None

                self.db.add_step(self.bot_id, step_number, action_text, action['element'], {
                    'full': full_screenshot_data,
                    'thumbnail': thumbnail_data
                }, friendly_description, reasoning)
                self.logger.info(f"Bot {self.bot_id} step {step_number} executed: {action_text}")

                return {'success': True, 'screenshot': full_screenshot_data}

            except Exception as e:
                error_msg = f"Failed to execute action {action_type} on {action['element']}: {str(e)}"
                self.logger.error(error_msg, exc_info=True)

                # Try to get a screenshot even if the action failed
                try:
                    screenshot_data = self.screenshot_capturer.capture_screenshot(self.driver)
                    full_screenshot_data = screenshot_data['full']
                    thumbnail_data = screenshot_data['thumbnail']
                except Exception as screenshot_error:
                    self.logger.error(f"Bot {self.bot_id} - Error capturing error screenshot: {str(screenshot_error)}")
                    full_screenshot_data = None
                    thumbnail_data = None

                self.db.add_step(self.bot_id, step_number, error_msg, action['element'], {
                    'full': full_screenshot_data,
                    'thumbnail': thumbnail_data
                }, friendly_description, reasoning, False)
                return {'success': False, 'screenshot': full_screenshot_data}

        except Exception as e:
            error_msg = f"Unexpected error executing action: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            return {'success': False, 'screenshot': None}

    def detect_bug(self):
        current_html = self.html_simplifier.simplify_html(self.html_simplifier.get_visible_html(self.driver))
        html_diff = self.get_html_diff(self.previous_html, current_html)

        newt_operation_summary = """
NEWT BUG DETECTION SUMMARY:
You are analyzing page changes to detect REAL, FUNCTIONAL bugs that impact end users. Your goal is to:
1. Identify ONLY genuine malfunctions that would impact real users
2. Focus on confirmed functional issues, not speculative problems
3. Consider the full context of actions taken and their outcomes
4. Avoid false positives from simplified HTML or temporary states
5. Require multiple confirming observations before reporting a bug
6. IGNORE test apparatus limitations and focus on REAL user impact

IMPORTANT NOTES ABOUT THE HTML YOU RECEIVE:
- The HTML is SIMPLIFIED to remove noise and focus on semantic content
- Styles, scripts, and non-essential attributes are intentionally removed
- Hidden elements (display:none, visibility:hidden) are removed
- This helps you focus on functionality, not presentation
- Missing styles or layout issues are NOT bugs
- Focus ONLY on confirmed functional issues that impact end users

CRITICAL BUG DETECTION RULES:
1. YOU MUST NOT report a bug based solely on HTML appearance
2. YOU MUST confirm any suspected issue through multiple observations
3. YOU MUST consider the full sequence of actions leading to the state
4. YOU MUST verify that any "blocking" is actually preventing functionality for end users
5. YOU MUST check if the issue persists after trying alternative approaches
6. YOU MUST NOT report issues that could be resolved by further interaction
7. YOU MUST prioritize bugs that would genuinely impact end users
8. YOU MUST IGNORE test apparatus limitations (e.g., "element not interactable" unless confirmed as a real issue)
9. YOU MUST focus on functional issues that prevent task completion

SPECIFIC GUIDELINES FOR REAL BUGS:
- Functional issues that prevent task completion
- Logical inconsistencies in application behavior
- Data corruption or loss
- Security vulnerabilities
- Accessibility issues that prevent usage
- Unexpected behavior that would confuse users
- Broken functionality that persists across multiple attempts

SPECIFIC GUIDELINES FOR WHAT TO IGNORE:
- Visual styling issues
- Missing classes or attributes in simplified HTML
- Temporary loading states
- Issues that could be resolved by further interaction
- Test apparatus limitations
- "Element not interactable" unless confirmed as a real user-facing issue
- Overlays or popups that are part of normal application flow
"""

        prompt = f"""
{newt_operation_summary}

Current directive: {self.directive}

Page HTML BEFORE the most recent action (simplified):
{self.previous_html}

Page HTML AFTER the most recent action (simplified):
{html_diff}

Steps taken (with success/failure status):
{self.get_step_text()}

Known bugs:
{json.dumps(self.db.get_bugs(self.bot_id, False))}

{f"You previously requested these select options:{chr(10) + json.dumps(self.select_options_cache)}" if len(self.select_options_cache) == 1 else '' }

CONTEXTUAL INFORMATION:
- Recent failures: {self.failure_count} consecutive failures
- Last action success: {'SUCCESS' if len(self.db.get_steps(self.bot_id)) > 0 and self.db.get_steps(self.bot_id)[-1]['success'] else 'FAILED'}
- Current URL: {self.driver.current_url if self.driver else 'N/A'}

CRITICAL BUG DETECTION QUESTIONS YOU MUST ANSWER:
1. Have you attempted to interact with the element you suspect is problematic using multiple approaches?
2. Have you tried alternative approaches to confirm the issue isn't just a temporary state or test limitation?
3. Does this issue persist across multiple actions and page states?
4. Would this issue genuinely impact an end user's ability to complete their task?
5. Is there any way this could be expected behavior rather than a bug?
6. Have you confirmed this isn't already a known bug?
7. Does this issue prevent completion of the testing directive for a real user?
8. Is this a REAL, FUNCTIONAL issue that impacts end users, or just a test apparatus limitation?

BUG REPORTING REQUIREMENTS:
- You MUST provide specific, reproducible steps that demonstrate the bug
- You MUST explain why this is a functional issue that impacts end users
- You MUST confirm the issue affects end users, not just the testing process
- You MUST NOT report issues that could be resolved by further interaction
- You MUST NOT report test apparatus limitations
- You MUST focus on REAL, FUNCTIONAL bugs that impact end users

Respond ONLY with the following:

```
~newt_isnewbug_start~
True or False - MUST be False if you haven't confirmed the bug through multiple observations and verified it's a REAL issue impacting end users
~newt_isnewbug_end~
~newt_severity_start~
High, Medium or Low - ONLY if this is a confirmed bug that impacts end users
~newt_severity_end~
~newt_description_start~
DETAILED end user-friendly explanation of the confirmed bug, including:
1. Specific steps to reproduce (must be end-user focused)
2. Expected behavior vs actual behavior
3. Why this is a functional issue that impacts end users
4. How this impacts the user experience
5. Evidence from multiple observations confirming the bug
6. Why this is NOT a test apparatus limitation
~newt_description_end~
~newt_recommendation_start~
Specific recommendations for fixing this bug, including technical details if relevant
~newt_recommendation_end~
~newt_confirmation_start~
Explain how you confirmed this bug through multiple observations or alternative approaches, and why it's a REAL issue impacting end users (not a test limitation)
~newt_confirmation_end~
~newt_impact_start~
Explain specifically how this bug impacts end users and prevents them from completing their tasks
~newt_impact_end~
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
                "is_bug": extract_line_based_content(analysis, "~newt_isnewbug_start~", "~newt_isnewbug_end~").lower() == "true",
                "severity": extract_line_based_content(analysis, "~newt_severity_start~", "~newt_severity_end~"),
                "description": extract_line_based_content(analysis, "~newt_description_start~", "~newt_description_end~"),
                "recommendation": extract_line_based_content(analysis, "~newt_recommendation_start~", "~newt_recommendation_end~"),
                "confirmation": extract_line_based_content(analysis, "~newt_confirmation_start~", "~newt_confirmation_end~"),
                "impact": extract_line_based_content(analysis, "~newt_impact_start~", "~newt_impact_end~"),
            }

            # Only return True if the bug is confirmed through multiple observations and is a REAL issue
            if analysis_object["is_bug"]:
                if not analysis_object["confirmation"] or not analysis_object["impact"]:
                    self.logger.info(f"Bot {self.bot_id} - Potential bug detected but not confirmed as a REAL issue impacting end users")
                    return False, analysis_object

            return analysis_object.get('is_bug', False), analysis_object
        except Exception as e:
            self.logger.error(f"Bot {self.bot_id} - Error in bug detection: {str(e)}")
            return False, {}

    def report_bug(self, action, result, context, analysis):
        # Only report bugs that have been properly confirmed as REAL issues impacting end users
        if not analysis.get('confirmation') or not analysis.get('impact'):
            self.logger.info(f"Bot {self.bot_id} - Bug not reported: insufficient confirmation or not a REAL issue impacting end users")
            return None

        summary = f"NEWT Bug Detected: {analysis['description']}..."
        steps = json.dumps(context['steps_taken'])

        try:
            bug_id = self.db.add_bug(self.bot_id, summary, steps)
            knowledge = f"DESCRIPTION:{chr(10)}{analysis['description']}{chr(10)}{chr(10)}"
            knowledge += f"RECOMMENDATION:{chr(10)}{analysis['recommendation']}{chr(10)}{chr(10)}"
            knowledge += f"CONFIRMATION:{chr(10)}{analysis['confirmation']}{chr(10)}{chr(10)}"
            knowledge += f"IMPACT ON USERS:{chr(10)}{analysis['impact']}"
            self.db.add_knowledge(bug_id, knowledge)

            severity = analysis.get('severity', 'medium').lower()
            if severity not in ['high', 'medium', 'low']:
                severity = 'medium'

            self.bug_reporter.send_notification(summary, knowledge, severity)
            return bug_id
        except Exception as e:
            self.logger.error(f"Bot {self.bot_id} - Error reporting bug: {str(e)}")
            return None

    def is_directive_complete(self):
        current_html = self.html_simplifier.simplify_html(self.html_simplifier.get_visible_html(self.driver))
        html_diff = self.get_html_diff(self.previous_html, current_html)

        newt_operation_summary = """
NEWT COMPLETION CHECK SUMMARY:
You are determining if testing should continue or if the directive has been satisfied. Consider:
1. Whether all major functionality areas have been explored
2. If edge cases and unusual scenarios have been tested
3. Whether the directive's requirements have been met
4. If there are still unexplored areas based on the page changes
5. Whether you've found REAL, FUNCTIONAL bugs that impact end users

IMPORTANT NOTES ABOUT THE HTML YOU RECEIVE:
- The HTML is SIMPLIFIED to remove noise and focus on semantic content
- Styles, scripts, and non-essential attributes are removed
- Hidden elements (display:none, visibility:hidden) are removed
- Only visible, semantic content is preserved
- This is INTENTIONAL to help you focus on functionality, not presentation
- Missing styles, layout issues, or missing classes are NOT bugs
- Focus on FUNCTIONALITY and USER EXPERIENCE issues
"""

        prompt = f"""
{newt_operation_summary}

Current directive: {self.directive}

Page HTML BEFORE the most recent action (simplified):
{self.previous_html}

Page HTML AFTER the most recent action (simplified):
{html_diff}

Steps taken:
{self.get_step_text()}

Known bugs:
{json.dumps(self.db.get_bugs(self.bot_id, False))}

{f"You previously requested these select options:{chr(10) + json.dumps(self.select_options_cache)}" if len(self.select_options_cache) == 1 else '' }

Consider:
1. Has the directive been fully satisfied?
2. Are there any remaining interactive elements that need testing?
3. Is there any indication that testing should continue?
4. Have all major functionality areas been covered?
5. Have you tried edge cases and unusual scenarios?
6. Based on the differences between BEFORE and AFTER HTML, are there any unexplored areas?
7. Have you found REAL, FUNCTIONAL bugs that impact end users?
8. Is there more value in continuing to test, or have you covered the important areas?

Respond ONLY with the following:

```
~newt_iscomplete_start~
True or False
~newt_iscomplete_end~
~newt_reasoning_start~
Detailed explanation of why testing should continue or stop, including observations about what changed between BEFORE and AFTER. Focus on whether you've found REAL issues and whether there's more value in continuing.
~newt_reasoning_end~
~newt_nextarea_start~
If not complete, suggest the next area to test based on the observed changes and what would provide the most value
~newt_nextarea_end~
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

            parsed_completion_check = extract_line_based_content(completion_check, "~newt_iscomplete_start~", "~newt_iscomplete_end~")
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
        try:
            # Add highlighting style
            self.driver.execute_script("""
                arguments[0].style.border = '3px solid #ff0000';
                arguments[0].style.boxShadow = '0 0 10px 5px rgba(255, 0, 0, 0.5)';
            """, element)
        except Exception as e:
            self.logger.debug(f"Bot {self.bot_id} - Error highlighting element: {str(e)}")

    def unhighlight_element(self, element):
        """Remove highlighting from an element"""
        try:
            # Remove highlighting style
            self.driver.execute_script("""
                arguments[0].style.border = '';
                arguments[0].style.boxShadow = '';
            """, element)
        except Exception as e:
            self.logger.debug(f"Bot {self.bot_id} - Error unhighlighting element: {str(e)}")

    def get_step_text(self):
        steps = self.db.get_steps(self.bot_id)
        detailed_steps = []
        for s in steps:
            status = "SUCCESS" if s['success'] else "FAILED"
            step_text = f"Step {s['step_number']} [{status}]: {s['action']}"
            step_text += f"{chr(10)}  Element: {s['element']}"
            step_text += f"{chr(10)}  Description: {s['friendly_description']}"
            step_text += f"{chr(10)}  Reasoning: {s['reasoning']}"
            detailed_steps.append(step_text)
        return chr(10).join(detailed_steps)
