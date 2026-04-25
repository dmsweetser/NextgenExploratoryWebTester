import json
import time
from lib.config import Config
from lib.stages.action_selection_stage import ActionSelectionStage
from lib.stages.action_execution_stage import ActionExecutionStage
from lib.stages.bug_detection_stage import BugDetectionStage
from lib.stages.bug_reevaluation_stage import BugReevaluationStage
from lib.stages.completion_check_stage import CompletionCheckStage

class StageOrchestrator:
    def __init__(self, bot_id, start_url, directive, db, bot_manager, bug_reporter,
                 html_simplifier, screenshot_capturer, llm, driver, action_chains, logger):
        self.bot_id = bot_id
        self.start_url = start_url
        self.directive = directive
        self.db = db
        self.bot_manager = bot_manager
        self.bug_reporter = bug_reporter
        self.html_simplifier = html_simplifier
        self.screenshot_capturer = screenshot_capturer
        self.llm = llm
        self.driver = driver
        self.action_chains = action_chains
        self.logger = logger
        self.select_options_cache = {}
        self.failure_count = 0

        # Initialize stages
        self.stages = [
            ActionSelectionStage(bot_id, start_url, directive, db, llm, logger),
            ActionExecutionStage(bot_id, db, screenshot_capturer, driver, action_chains, logger),
            BugDetectionStage(bot_id, directive, db, llm, logger),
            BugReevaluationStage(bot_id, directive, db, llm, logger),
            CompletionCheckStage(bot_id, directive, db, llm, logger)
        ]

    def execute_stages(self, previous_html, current_html, current_url):
        context = {
            'bot_id': self.bot_id,
            'directive': self.directive,
            'previous_html': previous_html,
            'current_html': current_html,
            'current_url': current_url,
            'steps_taken': self.db.get_steps(self.bot_id),
            'known_bugs': self.db.get_bugs(self.bot_id, False),
            'select_options_cache': self.select_options_cache,
            'failure_count': self.failure_count,
            'should_stop': False,
            'success': False
        }

        # Execute stages in sequence
        for stage in self.stages:
            try:
                result = stage.execute(context)
                context.update(result)

                # Update failure count based on stage result
                if 'success' in result and not result['success']:
                    self.failure_count += 1
                elif 'success' in result and result['success']:
                    self.failure_count = max(0, self.failure_count - 1)

                # Update context with any changes
                if 'select_options_cache' in result:
                    self.select_options_cache = result['select_options_cache']

                # Check if we should stop
                if result.get('should_stop', False):
                    context['should_stop'] = True
                    break

            except Exception as e:
                self.logger.error(f"Bot {self.bot_id} - Error in stage {stage.__class__.__name__}: {str(e)}")
                self.failure_count += 1
                context['success'] = False
                break

        return context
