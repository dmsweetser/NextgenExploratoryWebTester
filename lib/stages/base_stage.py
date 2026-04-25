import difflib
import json
import time
from lib.config import Config
from lib.llm_integration import extract_line_based_content

class BaseStage:
    def __init__(self, bot_id, logger):
        self.bot_id = bot_id
        self.logger = logger

    def execute(self, context):
        """Execute the stage with the given context"""
        raise NotImplementedError

    def get_html_diff(self, before_html, after_html, max_lines=10):
        """Generate a diff between before and after HTML, showing only changes if they're small"""
        if not before_html or not after_html:
            return after_html

        before_lines = before_html.splitlines()
        after_lines = after_html.splitlines()

        diff = list(difflib.unified_diff(before_lines, after_lines, n=0))

        if len(diff) < len(after_lines) * 0.7 and len(diff) > 0 and len(diff) <= max_lines * 2:
            return "\n".join(diff)
        elif before_lines != after_lines:
            return after_html
        else:
            return "The AFTER HTML was identical to the BEFORE HTML"

    def log_prompt(self, prompt, suffix=""):
        """Log the prompt to a file if logging is enabled"""
        if Config.get_log_prompts():
            ticks = int(time.time() * 1000)
            prompt_filename = f"data/bot_{self.bot_id}_{ticks}_{suffix}_prompt.txt"
            with open(prompt_filename, "w") as f:
                f.write(prompt)

    def log_response(self, response, suffix=""):
        """Log the response to a file if logging is enabled"""
        if Config.get_log_prompts():
            ticks = int(time.time() * 1000)
            response_filename = f"data/bot_{self.bot_id}_{ticks}_{suffix}_response.txt"
            with open(response_filename, "w") as f:
                f.write(response)
