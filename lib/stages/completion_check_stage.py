import json

from lib.config import Config
from lib.stages.base_stage import BaseStage
from lib.llm_integration import extract_line_based_content

class CompletionCheckStage(BaseStage):
    def __init__(self, bot_id, directive, db, llm, logger):
        super().__init__(bot_id, logger)
        self.directive = directive
        self.db = db
        self.llm = llm

    def execute(self, context):
        if not Config.get_allow_conclude():
            return {'should_stop': False, 'success': True}

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
{context['previous_html']}

Page HTML AFTER the most recent action (simplified):
{self.get_html_diff(context['previous_html'], context['current_html'])}

Steps taken:
{self.get_step_text(context['steps_taken'])}

Known bugs:
{json.dumps(context.get('known_bugs', []))}

{f"You previously requested these select options:{chr(10) + json.dumps(context.get('select_options_cache', {}))}" if len(context.get('select_options_cache', {})) > 0 else '' }

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

        self.log_prompt(prompt, "completion_check")

        try:
            completion_check = self.llm.get_action(prompt)
            self.log_response(completion_check, "completion_check")

            parsed_completion_check = extract_line_based_content(completion_check, "~newt_iscomplete_start~", "~newt_iscomplete_end~")
            should_stop = parsed_completion_check == "True"

            return {
                'should_stop': should_stop,
                'success': True
            }
        except Exception as e:
            self.logger.error(f"Bot {self.bot_id} - Error in completion check: {str(e)}")
            return {
                'should_stop': False,
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
