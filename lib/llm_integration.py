import logging
from lib.config import Config
from typing import Dict, Any, Optional
import time
from datetime import datetime

class LocalLlama:
    """Local Llama model integration"""

    def __init__(self):
        self.model = None
        self.initialize_model()

    def initialize_model(self):
        """Initialize the local Llama model"""
        try:
            from llama_cpp import Llama
            model_path = Config.get_model_path()
            if not model_path:
                raise ValueError("MODEL_PATH not configured in config.py")

            self.model = Llama(
                model_path=model_path,
                n_ctx=Config.get_model_context(),
                n_threads=Config.get_model_threads(),
                n_batch=Config.get_model_batch(),
                n_gpu_layers=Config.get_model_gpu_layers()
            )
        except ImportError:
            logging.error("llama_cpp not installed. Please install with: pip install llama-cpp-python")
            raise
        except Exception as e:
            logging.error(f"Failed to initialize local Llama model: {str(e)}")
            raise

    def get_action(self, prompt: str) -> Dict[str, Any]:
        """Get the next action from the LLM"""
        if not self.model:
            raise RuntimeError("Model not initialized")

        response_content = ""
        try:
            # Generate response with streaming
            for response in self.model(prompt, stream=True):
                response_content += response['choices'][0]['text']

            # Parse the JSON response
            try:
                import json
                action = json.loads(response_content)
                return action
            except json.JSONDecodeError:
                # Fallback if JSON parsing fails
                return {
                    "action": "click",
                    "element": "body",
                    "value": "",
                    "reasoning": "Fallback action due to JSON parsing error"
                }

        except Exception as e:
            logging.error(f"Error getting action from LLM: {str(e)}")
            return {
                "action": "wait",
                "element": "",
                "value": "2",
                "reasoning": "Error in LLM, waiting to recover"
            }

class AzureFoundry:
    """Azure Foundry model integration"""

    def __init__(self):
        self.client = None
        self.initialize_client()

    def initialize_client(self):
        """Initialize the Azure Foundry client"""
        try:
            from azure.ai.inference import ChatCompletionsClient
            from azure.core.credentials import AzureKeyCredential

            endpoint = Config.get_endpoint()
            api_key = Config.get_api_key()
            model_name = Config.get_model_name()

            if not all([endpoint, api_key, model_name]):
                raise ValueError("Missing Azure Foundry configuration in config.py")

            self.client = ChatCompletionsClient(
                endpoint=endpoint,
                credential=AzureKeyCredential(api_key),
                api_version="2024-05-01-preview"
            )
        except ImportError:
            logging.error("azure-ai-inference not installed. Please install with: pip install azure-ai-inference")
            raise
        except Exception as e:
            logging.error(f"Failed to initialize Azure Foundry client: {str(e)}")
            raise

    def get_action(self, prompt: str) -> Dict[str, Any]:
        """Get the next action from the Azure Foundry model"""
        if not self.client:
            raise RuntimeError("Client not initialized")

        try:
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

            # Parse the JSON response
            try:
                import json
                action = json.loads(response_content)
                return action
            except json.JSONDecodeError:
                # Fallback if JSON parsing fails
                return {
                    "action": "click",
                    "element": "body",
                    "value": "",
                    "reasoning": "Fallback action due to JSON parsing error"
                }

        except Exception as e:
            logging.error(f"Error getting action from Azure Foundry: {str(e)}")
            return {
                "action": "wait",
                "element": "",
                "value": "2",
                "reasoning": "Error in Azure Foundry, waiting to recover"
            }