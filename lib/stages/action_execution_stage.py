from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from lib.stages.base_stage import BaseStage
import time

class ActionExecutionStage(BaseStage):
    def __init__(self, bot_id, db, screenshot_capturer, driver, action_chains, logger):
        super().__init__(bot_id, logger)
        self.db = db
        self.screenshot_capturer = screenshot_capturer
        self.driver = driver
        self.action_chains = action_chains
        self.default_wait = 10

    def execute(self, context):
        action = context.get('action')
        if not action:
            return {'success': False}

        try:
            step_number = len(context['steps_taken']) + 1
            result = self.execute_action(action, step_number)
            return {
                'success': result.get('success', False),
                'screenshot_data': result.get('screenshot', None)
            }
        except Exception as e:
            self.logger.error(f"Bot {self.bot_id} - Error executing action: {str(e)}")
            return {'success': False}

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
                    select_options_cache = {selector_value: options}
                    action_text = f"Got select options for {selector_value}: {', '.join(options)}"
                    return {
                        'success': True,
                        'screenshot': full_screenshot_data,
                        'select_options_cache': select_options_cache
                    }
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
