from lib.config import Config
from lib.stages.base_stage import BaseStage
from lib.llm_integration import extract_line_based_content
import json

class BugReevaluationStage(BaseStage):
    def __init__(self, bot_id, directive, db, llm, logger):
        super().__init__(bot_id, logger)
        self.directive = directive
        self.db = db
        self.llm = llm

    def execute(self, context):
        # Only proceed if we have a bug detection result
        if not context.get('bug_detection_result'):
            return {'success': True}

        bug_detection_result = context['bug_detection_result']

        # If no bug was detected, just check if we need to remove any existing bugs
        if not bug_detection_result.get('is_bug', False):
            return self.reevaluate_existing_bugs(context)

        # If a bug was detected, check if it's valid and if it makes any existing bugs obsolete
        return self.validate_new_bug(context)

    def validate_new_bug(self, context):
        bug_detection_result = context['bug_detection_result']

        # Get configured bug categories with detailed descriptions
        categories_str = Config.get_bug_categories()
        if categories_str:
            categories = [c.strip() for c in categories_str.split(',')]
        else:
            categories = ['typos', 'ux_failure', 'app_crash', 'security']

        # Create detailed descriptions for each bug category
        category_descriptions = {
            'typos': 'Typographical Errors: Incorrect or misspelled text that indicates problems in the application content.',
            'ux_failure': 'User Experience Failures: Logical inconsistencies or confusing flows that make the application difficult to use.',
            'app_crash': 'Application Crashes: Complete or partial failures that prevent users from completing their tasks.',
            'security': 'Security Vulnerabilities: Issues that could compromise the security of the application or its users.',
            'accessibility': 'Accessibility Issues: Problems that prevent users with disabilities from using the application effectively.'
        }

        # Filter to only include the configured categories
        active_categories = {k: v for k, v in category_descriptions.items() if k in categories}
        category_list = ", ".join([f"{k}: {v}" for k, v in active_categories.items()])

        newt_operation_summary = """
NEWT BUG REEVALUATION SUMMARY:
You are validating a newly detected bug to ensure it's a REAL, FUNCTIONAL issue that impacts end users.
Your goal is to:
1. Confirm the bug is valid and not a false positive
2. Ensure the bug falls into one of the allowed categories: {category_list}
3. Check if this bug makes any existing bugs obsolete
4. Verify the bug would genuinely impact end users
5. Confirm this is not a test apparatus limitation

IMPORTANT NOTES:
- The HTML is SIMPLIFIED to focus on functionality, not presentation
- You must be absolutely certain this is a REAL bug before confirming it
- You must check if this bug makes any existing bugs no longer relevant
- You must ensure this bug would impact real users, not just the testing process
"""

        # Get all existing bugs
        existing_bugs = self.db.get_bugs(self.bot_id, False)
        existing_bugs_text = json.dumps(existing_bugs, indent=2) if existing_bugs else "None"

        prompt = f"""
{newt_operation_summary.format(category_list=category_list)}

Current directive: {self.directive}

Page HTML BEFORE the most recent action (simplified):
{context['previous_html']}

Page HTML AFTER the most recent action (simplified):
{self.get_html_diff(context['previous_html'], context['current_html'])}

Steps taken (with success/failure status):
{self.get_step_text(context['steps_taken'])}

Newly detected potential bug:
Category: {bug_detection_result.get('category', 'Not specified')}
Severity: {bug_detection_result.get('severity', 'Not specified')}
Description: {bug_detection_result.get('description', 'Not specified')}
Confirmation: {bug_detection_result.get('confirmation', 'Not specified')}
Impact: {bug_detection_result.get('impact', 'Not specified')}

Existing bugs in the system:
{existing_bugs_text}

CRITICAL VALIDATION QUESTIONS:
1. Is this REALLY a bug that impacts end users, or could it be a test limitation?
2. Does this bug fall into one of the allowed categories: {', '.join(active_categories.keys())}?
3. Does this bug make any existing bugs obsolete or no longer relevant?
4. Would this bug genuinely prevent end users from completing their tasks?
5. Have you confirmed this isn't just a temporary state or test artifact?
6. Is there any chance this could be expected behavior rather than a bug?

Respond ONLY with the following:

```
~newt_isvalidbug_start~
True or False - MUST be True only if you're absolutely certain this is a REAL bug impacting end users
~newt_isvalidbug_end~
~newt_revised_description_start~
If this is a valid bug, provide a revised, more accurate description if needed. Otherwise, explain why it's not valid.
~newt_revised_description_end~
~newt_obsolete_bug_ids_start~
Comma-separated list of existing bug IDs that are now obsolete or no longer relevant due to this new bug. If none, leave empty.
~newt_obsolete_bug_ids_end~
~newt_validation_reasoning_start~
Explain your reasoning for validating or invalidating this bug, including why it is or isn't a REAL issue impacting end users.
~newt_validation_reasoning_end~
```
        """

        self.log_prompt(prompt, "bug_reevaluation")

        try:
            response = self.llm.get_action(prompt)
            self.log_response(response, "bug_reevaluation")

            result = {
                "is_valid_bug": extract_line_based_content(response, "~newt_isvalidbug_start~", "~newt_isvalidbug_end~").lower() == "true",
                "revised_description": extract_line_based_content(response, "~newt_revised_description_start~", "~newt_revised_description_end~"),
                "obsolete_bug_ids": extract_line_based_content(response, "~newt_obsolete_bug_ids_start~", "~newt_obsolete_bug_ids_end~").strip(),
                "validation_reasoning": extract_line_based_content(response, "~newt_validation_reasoning_start~", "~newt_validation_reasoning_end~")
            }

            # Parse obsolete_bug_ids into a list
            if result["obsolete_bug_ids"]:
                try:
                    result["obsolete_bug_ids"] = [int(x.strip()) for x in result["obsolete_bug_ids"].split(',') if x.strip().isdigit()]
                except:
                    result["obsolete_bug_ids"] = []
            else:
                result["obsolete_bug_ids"] = []

            # If the bug is valid, update the bug detection result with the revised description
            if result["is_valid_bug"] and result["revised_description"]:
                bug_detection_result["description"] = result["revised_description"]

            return {
                'bug_validation_result': result,
                'bug_detection_result': bug_detection_result,
                'success': True
            }

        except Exception as e:
            self.logger.error(f"Bot {self.bot_id} - Error in bug reevaluation: {str(e)}")
            return {
                'bug_validation_result': {
                    "is_valid_bug": False,
                    "revised_description": "",
                    "obsolete_bug_ids": [],
                    "validation_reasoning": f"Error in bug reevaluation: {str(e)}"
                },
                'bug_detection_result': bug_detection_result,
                'success': False
            }

    def reevaluate_existing_bugs(self, context):
        """Reevaluate existing bugs to see if any should be removed based on current state"""
        # Get all existing bugs
        existing_bugs = self.db.get_bugs(self.bot_id, False)
        if not existing_bugs:
            return {'success': True}

        # Get configured bug categories with detailed descriptions
        categories_str = Config.get_bug_categories()
        if categories_str:
            categories = [c.strip() for c in categories_str.split(',')]
        else:
            categories = ['typos', 'ux_failure', 'app_crash', 'security']

        # Create detailed descriptions for each bug category
        category_descriptions = {
            'typos': 'Typographical Errors: Incorrect or misspelled text that indicates problems in the application content.',
            'ux_failure': 'User Experience Failures: Logical inconsistencies or confusing flows that make the application difficult to use.',
            'app_crash': 'Application Crashes: Complete or partial failures that prevent users from completing their tasks.',
            'security': 'Security Vulnerabilities: Issues that could compromise the security of the application or its users.',
            'accessibility': 'Accessibility Issues: Problems that prevent users with disabilities from using the application effectively.'
        }

        # Filter to only include the configured categories
        active_categories = {k: v for k, v in category_descriptions.items() if k in categories}
        category_list = ", ".join([f"{k}: {v}" for k, v in active_categories.items()])

        newt_operation_summary = """
NEWT EXISTING BUG REEVALUATION SUMMARY:
You are reevaluating existing bugs to determine if any should be removed based on the current state.
Your goal is to:
1. Check if any existing bugs are no longer relevant
2. Verify if any bugs have been resolved by recent actions
3. Confirm that all remaining bugs are still valid issues impacting end users
4. Ensure no bugs are test apparatus limitations

IMPORTANT NOTES:
- The HTML is SIMPLIFIED to focus on functionality, not presentation
- You must be absolutely certain a bug should be removed before recommending removal
- You must ensure remaining bugs are still REAL issues impacting end users
"""

        existing_bugs_text = json.dumps(existing_bugs, indent=2)

        prompt = f"""
{newt_operation_summary}

Current directive: {self.directive}

Page HTML BEFORE the most recent action (simplified):
{context['previous_html']}

Page HTML AFTER the most recent action (simplified):
{self.get_html_diff(context['previous_html'], context['current_html'])}

Steps taken (with success/failure status):
{self.get_step_text(context['steps_taken'])}

Existing bugs in the system:
{existing_bugs_text}

CRITICAL REEVALUATION QUESTIONS:
1. Have any of these bugs been resolved by recent actions?
2. Are any of these bugs no longer relevant based on the current state?
3. Are all of these bugs still REAL issues impacting end users?
4. Should any of these bugs be removed because they were false positives?
5. Have you confirmed that none of these bugs are test apparatus limitations?

Respond ONLY with the following:

```
~newt_remove_bug_ids_start~
Comma-separated list of bug IDs that should be removed. If none, leave empty.
~newt_remove_bug_ids_end~
~newt_reevaluation_reasoning_start~
Explain your reasoning for removing any bugs, including why they are no longer relevant or were false positives.
~newt_reevaluation_reasoning_end~
```
        """

        self.log_prompt(prompt, "existing_bug_reevaluation")

        try:
            response = self.llm.get_action(prompt)
            self.log_response(response, "existing_bug_reevaluation")

            result = {
                "remove_bug_ids": extract_line_based_content(response, "~newt_remove_bug_ids_start~", "~newt_remove_bug_ids_end~").strip(),
                "reevaluation_reasoning": extract_line_based_content(response, "~newt_reevaluation_reasoning_start~", "~newt_reevaluation_reasoning_end~")
            }

            # Parse remove_bug_ids into a list
            if result["remove_bug_ids"]:
                try:
                    result["remove_bug_ids"] = [int(x.strip()) for x in result["remove_bug_ids"].split(',') if x.strip().isdigit()]
                except:
                    result["remove_bug_ids"] = []
            else:
                result["remove_bug_ids"] = []

            return {
                'bug_reevaluation_result': result,
                'success': True
            }

        except Exception as e:
            self.logger.error(f"Bot {self.bot_id} - Error in existing bug reevaluation: {str(e)}")
            return {
                'bug_reevaluation_result': {
                    "remove_bug_ids": [],
                    "reevaluation_reasoning": f"Error in existing bug reevaluation: {str(e)}"
                },
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
