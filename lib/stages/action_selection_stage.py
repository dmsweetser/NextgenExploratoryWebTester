from lib.stages.base_stage import BaseStage
from lib.llm_integration import extract_line_based_content

class ActionSelectionStage(BaseStage):
    def __init__(self, bot_id, start_url, directive, db, llm, logger):
        super().__init__(bot_id, logger)
        self.start_url = start_url
        self.directive = directive
        self.db = db
        self.llm = llm

    def execute(self, context):
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

Current directive: {self.directive}

Page HTML BEFORE the most recent action (simplified):
{context['previous_html']}

Page HTML AFTER the most recent action (simplified):
{self.get_html_diff(context['previous_html'], context['current_html'])}

{f"You previously requested these select options:{chr(10) + json.dumps(context['select_options_cache'])}" if len(context['select_options_cache']) > 0 else '' }

Known bugs to avoid:
{json.dumps(context['known_bugs'])}

Steps taken:
{self.get_step_text(context['steps_taken'])}

Current URL: {context['current_url']}

Previous action status:
{'SUCCESS' if len(context['steps_taken']) > 0 and context['steps_taken'][-1]['success'] else 'FAILED' if len(context['steps_taken']) > 0 else 'N/A'}

Recent failures in last 5 steps: {sum(1 for step in context['steps_taken'][-5:] if not step['success'])}
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

        self.log_prompt(prompt, "action_selection")

        try:
            action = self.llm.get_action(prompt)
            self.log_response(action, "action_selection")

            action_dict = {
                "action": extract_line_based_content(action, "~newt_action_start~", "~newt_action_end~"),
                "element_selector_type": extract_line_based_content(action, "~newt_element_selector_type_start~", "~newt_element_selector_type_end~") or "CSS_SELECTOR",
                "element_selector_value": extract_line_based_content(action, "~newt_element_selector_value_start~", "~newt_element_selector_value_end~") or "",
                "value": extract_line_based_content(action, "~newt_value_start~", "~newt_value_end~") or "",
                "friendly_description": extract_line_based_content(action, "~newt_friendly_description_start~", "~newt_friendly_description_end~") or "",
                "reasoning": extract_line_based_content(action, "~newt_reasoning_start~", "~newt_reasoning_end~") or "",
                "element": f"{extract_line_based_content(action, '~newt_element_selector_type_start~', '~newt_element_selector_type_end~') or 'CSS_SELECTOR'}:{extract_line_based_content(action, '~newt_element_selector_value_start~', '~newt_element_selector_value_end~') or ''}"
            }

            return {
                'action': action_dict,
                'success': True
            }
        except Exception as e:
            self.logger.error(f"Bot {self.bot_id} - Error getting next action: {str(e)}")
            return {
                'action': None,
                'success': False
            }

    def get_step_text(self, steps):
        detailed_steps = []
        for s in steps:
            status = "SUCCESS" if s['success'] else "FAILED"
            step_text = f"Step {s['step_number']} [{status}]: {s['action']}"
            step_text += f"{chr(10)}  Element: {s['element']}"
            step_text += f"{chr(10)}  Description: {s['friendly_description']}"
            step_text += f"{chr(10)}  Reasoning: {s['reasoning']}"
            detailed_steps.append(step_text)
        return chr(10).join(detailed_steps)
