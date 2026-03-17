import logging
import subprocess
import os
from lib.config import Config

class LLMFactory:
    def create_llm(self):
        if Config.use_local_model():
            return LocalLlama()
        else:
            return AzureFoundry()

class LocalLlama:
    def __init__(self):
        self.response_file = "response.log"

    def get_action(self, prompt):
        model_path = Config.get_model_path()
        if not model_path:
            raise ValueError("MODEL_PATH not configured")

        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        llama_binary = os.path.join(BASE_DIR, "..", "llama.cpp", "build", "bin", "llama-cli")

        if not os.path.isfile(llama_binary):
            raise FileNotFoundError(f"llama binary not found at: {llama_binary}")

        cmd = [
            llama_binary,
            "-m", model_path,
            "-p", prompt,
            "--temp", str(Config.get_temperature()),
            "--top-p", str(Config.get_top_p()),
            "--top-k", str(Config.get_top_k()),
            "--min-p", str(Config.get_min_p()),
            "-n", str(Config.get_output_tokens()),
            "--ctx-size", str(Config.get_model_context()),
            "--no-display-prompt",
            "-st"
        ]

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )

        response_content = ""
        current_iteration = 0

        while True:
            token = process.stdout.read(1)
            if current_iteration % 100 == 0 or not token:
                with open(self.response_file, 'w', encoding='utf-8') as response_log:
                    response_log.write(response_content)
            if not token:
                break
            response_content += token
            current_iteration += 1

        process.wait()

        try:
            import json
            return json.loads(response_content)
        except json.JSONDecodeError:
            return {
                "action": "wait",
                "element": "",
                "value": "2",
                "reasoning": "Fallback action due to JSON parsing error"
            }

class AzureFoundry:
    def __init__(self):
        self.client = None
        self.initialize_client()

    def initialize_client(self):
        from azure.ai.inference import ChatCompletionsClient
        from azure.core.credentials import AzureKeyCredential

        endpoint = Config.get_endpoint()
        api_key = Config.get_api_key()
        model_name = Config.get_model_name()

        if not all([endpoint, api_key, model_name]):
            raise ValueError("Missing Azure Foundry configuration")

        self.client = ChatCompletionsClient(
            endpoint=endpoint,
            credential=AzureKeyCredential(api_key),
            api_version="2024-05-01-preview"
        )

    def get_action(self, prompt):
        from azure.ai.inference.models import SystemMessage, UserMessage

        response = self.client.complete(
            stream=True,
            messages=[
                SystemMessage(content="You are a helpful web testing assistant. Respond with JSON."),
                UserMessage(content=prompt)
            ],
            max_tokens=Config.get_output_tokens(),
            model=Config.get_model_name()
        )

        response_content = ""
        for update in response:
            if update.choices and isinstance(update.choices, list) and len(update.choices) > 0:
                content = update.choices[0].get("delta", {}).get("content", "")
                if content is not None:
                    response_content += content
            else:
                break

        response.close()

        try:
            import json
            return json.loads(response_content)
        except json.JSONDecodeError:
            return {
                "action": "wait",
                "element": "",
                "value": "2",
                "reasoning": "Fallback action due to JSON parsing error"
            }
