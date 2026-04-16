import subprocess
import os
import time
from lib.config import Config

def extract_line_based_content(response_content, start_marker, end_marker):
    try:
        start = response_content.find(start_marker)
        end = response_content.find(end_marker)
        if start != -1 and end != -1:
            content = response_content[start + len(start_marker):end~.strip()
            return content
        return ""
    except Exception as e:
        return ""

class LLMFactory:
    def create_llm(self):
        if Config.use_local_model():
            return LocalLlama()
        else:
            return AzureFoundry()

class LocalLlama:

    def get_action(self, prompt, bot_id=None):
        model_path = Config.get_model_path()
        if not model_path:
            raise ValueError("MODEL_PATH not configured")

        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        llama_binary = os.path.join(BASE_DIR, "..", Config.get_llama_binary_path())

        if not os.path.isfile(llama_binary):
            # Try alternative binary locations
            alternative_paths = [
                os.path.join(BASE_DIR, "..", "llama.cpp", "build", "bin", "llama-cli"),
                os.path.join(BASE_DIR, "..", "llama.cpp", "build", "bin", "main"),
                os.path.join(BASE_DIR, "..", "llama.cpp", "build", "bin", "llama"),
            ]

            for alt_path in alternative_paths:
                if os.path.isfile(alt_path):
                    llama_binary = alt_path
                    break

        if not os.path.isfile(llama_binary):
            raise FileNotFoundError(f"llama binary not found at: {llama_binary}")

        ticks = int(time.time() * 1000)
        filename = f"data/prompt_{ticks}.txt"
        with open(filename, "w") as f:
            f.write(prompt)

        cmd = [
            llama_binary,
            "-m", model_path,
            "-f", filename,
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
        process_error = None

        while True:
            try:
                token = process.stdout.read(1)
                if not token:
                    break
                response_content += token
                current_iteration += 1
                if current_iteration > 10000:
                    process.terminate()
                    break
            except Exception as e:
                process_error = e
                self.logger.error(f"Error reading from process: {str(e)}")
                break

        process.wait()

        # Clean up the prompt file
        try:
            if os.path.exists(filename):
                os.remove(filename)
        except Exception as e:
            self.logger.error(f"Error removing prompt file: {str(e)}")

        if process_error:
            raise RuntimeError(f"Error in LLM process: {str(process_error)}")

        return response_content

class AzureFoundry():
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

    def get_action(self, prompt, bot_id=None):
        from azure.ai.inference.models import SystemMessage, UserMessage

        try:
            response = self.client.complete(
                stream=True,
                messages=[
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
            return response_content
        except Exception as e:
            raise RuntimeError(f"Error in Azure LLM request: {str(e)}")
