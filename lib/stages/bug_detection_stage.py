from lib.config import Config
from lib.stages.base_stage import BaseStage
from lib.llm_integration import extract_line_based_content
import json

class BugDetectionStage(BaseStage):
    def __init__(self, bot_id, directive, db, llm, logger):
        super().__init__(bot_id, logger)
        self.directive = directive
        self.db = db
        self.llm = llm

    def execute(self, context):
        # Get configured bug categories with detailed descriptions
        categories_str = Config.get_bug_categories()
        if categories_str:
            categories = [c.strip() for c in categories_str.split(',')]
        else:
            categories = ['typos', 'ux_failure', 'app_crash', 'security']

        # Create detailed descriptions for each bug category
        category_descriptions = {
            'typos': 'Typographical Errors: Incorrect or misspelled text that indicates problems in the application content. This includes spelling mistakes, grammatical errors, or incorrect terminology that could confuse users or indicate data corruption.',
            'ux_failure': 'User Experience Failures: Logical inconsistencies, confusing flows, or unexpected behaviors that make the application difficult or impossible to use. This includes navigation issues, broken workflows, or elements that appear to work but don\'t perform their intended function.',
            'app_crash': 'Application Crashes: Complete or partial failures of the application that prevent users from completing their tasks. This includes error messages, exceptions, blank screens, or any state that prevents normal operation of the application.',
            'security': 'Security Vulnerabilities: Issues that could compromise the security of the application or its users. This includes potential for data leaks, injection vulnerabilities, authentication bypasses, or any other security-related concerns.',
            'accessibility': 'Accessibility Issues: Problems that prevent users with disabilities from using the application effectively. This includes missing alt text, poor color contrast, keyboard navigation issues, or any other accessibility barriers.'
        }

        # Filter to only include the configured categories
        active_categories = {k: v for k, v in category_descriptions.items() if k in categories}
        category_list = ", ".join([f"{k}: {v}" for k, v in active_categories.items()])

        newt_operation_summary = """
NEWT BUG DETECTION SUMMARY:
You are analyzing page changes to detect SPECIFIC TYPES OF bugs defined by the user. Your goal is to:
1. Identify ONLY bugs from the allowed categories below
2. IGNORE all other types of issues, including interactivity failures, test apparatus limitations, and minor visual glitches
3. Focus on confirmed issues that match the specific categories
4. Consider the full context of actions taken and their outcomes
5. Avoid false positives from simplified HTML or temporary states
6. Require multiple confirming observations before reporting a bug

ALLOWED BUG CATEGORIES:
{category_list}

IMPORTANT NOTES ABOUT THE HTML YOU RECEIVE:
- The HTML is SIMPLIFIED to remove noise and focus on semantic content
- Styles, scripts, and non-essential attributes are intentionally removed
- Hidden elements (display:none, visibility:hidden) are removed
- This helps you focus on functionality, not presentation
- Missing styles or layout issues are NOT bugs
- Focus ONLY on the specific bug categories listed above

CRITICAL BUG DETECTION RULES:
1. YOU MUST NOT report a bug based solely on HTML appearance
2. YOU MUST confirm any suspected issue through multiple observations
3. YOU MUST consider the full sequence of actions leading to the state
4. YOU MUST verify that any "blocking" is actually preventing functionality for end users
5. YOU MUST check if the issue persists after trying alternative approaches
6. YOU MUST NOT report issues that could be resolved by further interaction
7. YOU MUST prioritize bugs that fall into the specific categories above
8. YOU MUST IGNORE test apparatus limitations
9. YOU MUST focus on functional issues that prevent task completion
"""

        # Prepare known bugs for removal check
        known_bugs = context.get('known_bugs', [])
        known_bugs_text = json.dumps(known_bugs, indent=2) if known_bugs else "None"

        prompt = f"""
{newt_operation_summary.format(category_list=category_list)}

Current directive: {self.directive}

Page HTML BEFORE the most recent action (simplified):
{context['previous_html']}

Page HTML AFTER the most recent action (simplified):
{self.get_html_diff(context['previous_html'], context['current_html'])}

Steps taken (with success/failure status):
{self.get_step_text(context['steps_taken'])}

Known bugs currently in the system:
{known_bugs_text}

{f"You previously requested these select options:{chr(10) + json.dumps(context.get('select_options_cache', {}))}" if len(context.get('select_options_cache', {})) > 0 else '' }

CONTEXTUAL INFORMATION:
- Recent failures: {context.get('failure_count', 0)} consecutive failures
- Last action success: {'SUCCESS' if len(context['steps_taken']) > 0 and context['steps_taken'][-1]['success'] else 'FAILED' if len(context['steps_taken']) > 0 else 'N/A'}
- Current URL: {context.get('current_url', 'N/A')}

CRITICAL BUG DETECTION QUESTIONS YOU MUST ANSWER:
1. Have you attempted to interact with the element you suspect is problematic using multiple approaches?
2. Have you tried alternative approaches to confirm the issue isn't just a temporary state or test limitation?
3. Does this issue persist across multiple actions and page states?
4. Would this issue genuinely impact an end user's ability to complete their task?
5. Is there any way this could be expected behavior rather than a bug?
6. Have you confirmed this isn't already a known bug?
7. Does this issue prevent completion of the testing directive for a real user?
8. Is this a REAL, FUNCTIONAL issue that impacts end users, or just a test apparatus limitation?
9. Does this bug fall into one of the allowed categories: {', '.join(active_categories.keys())}?

BUG REPORTING REQUIREMENTS:
- You MUST provide specific, reproducible steps that demonstrate the bug
- You MUST explain why this is a functional issue that impacts end users
- You MUST confirm the issue affects end users, not just the testing process
- You MUST NOT report issues that could be resolved by further interaction
- You MUST NOT report test apparatus limitations
- You MUST focus on REAL, FUNCTIONAL bugs that impact end users
- You MUST ONLY report bugs from the allowed categories: {', '.join(active_categories.keys())}

Respond ONLY with the following:

```
~newt_isnewbug_start~
True or False - MUST be False if you haven't confirmed the bug through multiple observations and verified it's a REAL issue impacting end users
~newt_isnewbug_end~
~newt_severity_start~
High, Medium or Low - ONLY if this is a confirmed bug that impacts end users
~newt_severity_end~
~newt_category_start~
The specific bug category from the allowed list: {', '.join(active_categories.keys())} - ONLY if this is a confirmed bug
~newt_category_end~
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
~newt_remove_bug_ids_start~
Comma-separated list of existing bug IDs that are no longer relevant or have been resolved. If none, leave empty.
~newt_remove_bug_ids_end~
```
        """

        self.log_prompt(prompt, "bug_detection")

        try:
            analysis = self.llm.get_action(prompt)
            self.log_response(analysis, "bug_detection")

            analysis_object = {
                "is_bug": extract_line_based_content(analysis, "~newt_isnewbug_start~", "~newt_isnewbug_end~").lower() == "true",
                "severity": extract_line_based_content(analysis, "~newt_severity_start~", "~newt_severity_end~"),
                "category": extract_line_based_content(analysis, "~newt_category_start~", "~newt_category_end~"),
                "description": extract_line_based_content(analysis, "~newt_description_start~", "~newt_description_end~"),
                "recommendation": extract_line_based_content(analysis, "~newt_recommendation_start~", "~newt_recommendation_end~"),
                "confirmation": extract_line_based_content(analysis, "~newt_confirmation_start~", "~newt_confirmation_end~"),
                "impact": extract_line_based_content(analysis, "~newt_impact_start~", "~newt_impact_end~"),
                "remove_bug_ids": extract_line_based_content(analysis, "~newt_remove_bug_ids_start~", "~newt_remove_bug_ids_end~").strip()
            }

            # Parse remove_bug_ids into a list
            if analysis_object["remove_bug_ids"]:
                try:
                    analysis_object["remove_bug_ids"] = [int(x.strip()) for x in analysis_object["remove_bug_ids"].split(',') if x.strip().isdigit()]
                except:
                    analysis_object["remove_bug_ids"] = []
            else:
                analysis_object["remove_bug_ids"] = []

            return {
                'bug_detection_result': analysis_object,
                'success': True
            }

        except Exception as e:
            self.logger.error(f"Bot {self.bot_id} - Error in bug detection: {str(e)}")
            return {
                'bug_detection_result': {
                    "is_bug": False,
                    "severity": "",
                    "category": "",
                    "description": "",
                    "recommendation": "",
                    "confirmation": "",
                    "impact": "",
                    "remove_bug_ids": []
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
