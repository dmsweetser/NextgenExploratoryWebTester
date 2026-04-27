import threading
import time
import json
import logging
from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from datetime import datetime
from lib.config import Config
from lib.stages.stage_orchestrator import StageOrchestrator
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
        self.stage_orchestrator = None

    def run(self):
        self.db.update_bot_status(self.bot_id, 'running', datetime.now().isoformat())

        try:
            self.initialize_driver()
            self.llm = self.llm_factory.create_llm()
            self.action_chains = ActionChains(self.driver)
            self.stage_orchestrator = StageOrchestrator(
                self.bot_id,
                self.start_url,
                self.directive,
                self.db,
                self.bot_manager,
                self.bug_reporter,
                self.html_simplifier,
                self.screenshot_capturer,
                self.llm,
                self.driver,
                self.action_chains,
                self.logger
            )

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

                    # Execute the stage-based testing process
                    result = self.stage_orchestrator.execute_stages(self.previous_html, self.current_html, current_url)

                    # Handle bug reporting if a valid bug was detected
                    if result.get('bug_detection_result', {}).get('is_bug', False) and result.get('bug_validation_result', {}).get('is_valid_bug', False):
                        self.report_bug(result)

                    # Handle bug removal if any bugs should be removed
                    if result.get('bug_reevaluation_result', {}).get('remove_bug_ids'):
                        self.remove_bugs(result['bug_reevaluation_result']['remove_bug_ids'])

                    # Check if we should stop
                    if result.get('should_stop', False):
                        break

                    # Update previous HTML for next iteration
                    self.previous_html = self.current_html

                    # Check failure count and update
                    if result.get('success', False):
                        self.failure_count = max(0, self.failure_count - 1)
                    else:
                        self.failure_count += 1

                except Exception as e:
                    self.logger.error(f"Bot {self.bot_id} - Error in main loop: {str(e)}")
                    self.failure_count += 1
                    time.sleep(2)  # Brief pause to prevent rapid error loops

        except Exception as e:
            logging.error(f"Error in bot {self.bot_id}: {str(e)}")
        finally:
            self.cleanup()

    def report_bug(self, context):
        """Report a validated bug to the system"""
        bug_detection_result = context.get('bug_detection_result', {})
        bug_validation_result = context.get('bug_validation_result', {})

        # Use the revised description if available
        description = bug_validation_result.get('revised_description', bug_detection_result.get('description', ''))

        summary = f"NEWT Bug Detected: {description}..."
        steps = json.dumps(context.get('steps_taken', []))

        try:
            severity = bug_detection_result.get('severity', 'medium').lower()
            if severity not in ['high', 'medium', 'low']:
                severity = 'medium'

            category = bug_detection_result.get('category', 'other').lower()
            if category not in ['typos', 'ux_failure', 'app_crash', 'security', 'accessibility']:
                category = 'other'

            bug_id = self.db.add_bug(self.bot_id, summary, steps, severity=severity, status='new')
            knowledge = f"CATEGORY: {category}{chr(10)}{chr(10)}"
            knowledge += f"DESCRIPTION:{chr(10)}{description}{chr(10)}{chr(10)}"
            knowledge += f"RECOMMENDATION:{chr(10)}{bug_detection_result.get('recommendation', '')}{chr(10)}{chr(10)}"
            knowledge += f"CONFIRMATION:{chr(10)}{bug_detection_result.get('confirmation', '')}{chr(10)}{chr(10)}"
            knowledge += f"IMPACT ON USERS:{chr(10)}{bug_detection_result.get('impact', '')}{chr(10)}{chr(10)}"
            knowledge += f"VALIDATION REASONING:{chr(10)}{bug_validation_result.get('validation_reasoning', '')}"
            self.db.add_knowledge(bug_id, knowledge)

            # Handle obsolete bugs
            if bug_validation_result.get('obsolete_bug_ids'):
                for bug_id_to_remove in bug_validation_result['obsolete_bug_ids']:
                    self.logger.info(f"Bot {self.bot_id} - Removing obsolete bug {bug_id_to_remove}")
                    self.db.update_bug_status_to_resolved(bug_id_to_remove)

            self.bug_reporter.send_notification(summary, knowledge, severity)
            return bug_id
        except Exception as e:
            self.logger.error(f"Bot {self.bot_id} - Error reporting bug: {str(e)}")
            return None

    def remove_bugs(self, bug_ids):
        """Remove bugs that are no longer relevant"""
        for bug_id in bug_ids:
            try:
                self.logger.info(f"Bot {self.bot_id} - Removing bug {bug_id} as no longer relevant")
                self.db.update_bug_status_to_resolved(bug_id)
            except Exception as e:
                self.logger.error(f"Bot {self.bot_id} - Error removing bug {bug_id}: {str(e)}")

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

        if len(diff) < len(after_lines) * 0.7 and len(diff) > 0 and len(diff) <= self.max_diff_lines * 2:
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
