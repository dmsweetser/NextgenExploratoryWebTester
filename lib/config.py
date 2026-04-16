import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    @classmethod
    def use_local_model(cls) -> bool:
        return os.getenv('USE_LOCAL_MODEL', 'true').lower() == 'true'

    @classmethod
    def get_model_path(cls) -> str:
        return os.getenv('MODEL_PATH', 'models/llama-2-7b-chat.ggmlv3.q4_0.bin')

    @classmethod
    def get_llama_binary_path(cls) -> str:
        return os.getenv('LLAMA_BINARY_PATH', 'llama.cpp/build/bin/llama-completion')

    @classmethod
    def get_model_context(cls) -> int:
        return int(os.getenv('MODEL_CONTEXT', '131072'))

    @classmethod
    def get_model_threads(cls) -> int:
        return int(os.getenv('MODEL_THREADS', '4'))

    @classmethod
    def get_model_batch(cls) -> int:
        return int(os.getenv('MODEL_BATCH', '512'))

    @classmethod
    def get_model_gpu_layers(cls) -> int:
        return int(os.getenv('MODEL_GPU_LAYERS', '0'))

    @classmethod
    def get_endpoint(cls) -> str:
        return os.getenv('AZURE_ENDPOINT', '')

    @classmethod
    def get_api_key(cls) -> str:
        return os.getenv('AZURE_API_KEY', '')

    @classmethod
    def get_model_name(cls) -> str:
        return os.getenv('AZURE_MODEL_NAME', 'gpt-35-turbo')

    @classmethod
    def get_output_tokens(cls) -> int:
        return int(os.getenv('OUTPUT_TOKENS', '32768'))

    @classmethod
    def get_temperature(cls) -> float:
        return float(os.getenv('TEMPERATURE', '0.7'))

    @classmethod
    def get_top_p(cls) -> float:
        return float(os.getenv('TOP_P', '0.9'))

    @classmethod
    def get_top_k(cls) -> int:
        return int(os.getenv('TOP_K', '40'))

    @classmethod
    def get_min_p(cls) -> float:
        return float(os.getenv('MIN_P', '0.05'))

    @classmethod
    def get_smtp_host(cls) -> str:
        return os.getenv('SMTP_HOST', '')

    @classmethod
    def get_smtp_port(cls) -> int:
        return int(os.getenv('SMTP_PORT', '587'))

    @classmethod
    def get_smtp_user(cls) -> str:
        return os.getenv('SMTP_USER', '')

    @classmethod
    def get_smtp_password(cls) -> str:
        return os.getenv('SMTP_PASSWORD', '')

    @classmethod
    def get_smtp_from(cls) -> str:
        return os.getenv('SMTP_FROM', 'bot@yourdomain.com')

    @classmethod
    def get_bug_notification_emails(cls) -> str:
        return os.getenv('BUG_NOTIFICATION_EMAILS', '')

    @classmethod
    def get_allowed_origins(cls) -> str:
        return os.getenv('ALLOWED_ORIGINS', '*')

    @classmethod
    def get_debug(cls) -> bool:
        return os.getenv('DEBUG', 'false').lower() == 'true'

    @classmethod
    def get_headless(cls) -> bool:
        return os.getenv('HEADLESS', 'true').lower() == 'true'

    @classmethod
    def get_log_prompts(cls) -> bool:
        return os.getenv('LOG_PROMPTS', 'true').lower() == 'true'

    @classmethod
    def get_default_wait(cls) -> int:
        return int(os.getenv('DEFAULT_WAIT', '10'))
    
    @classmethod
    def get_port(cls) -> int:
        return int(os.getenv('RUNNING_PORT', '6329'))

    @classmethod
    def get_max_failures(cls) -> int:
        return int(os.getenv('MAX_FAILURES', '100'))
    
    @classmethod
    def get_allow_conclude(cls) -> bool:
        return os.getenv('ALLOW_CONCLUDE', 'true').lower() == 'true'

    @classmethod
    def get_max_prompt_tokens(cls) -> int:
        return int(os.getenv('MAX_PROMPT_TOKENS', '131000'))

    @classmethod
    def get_max_diff_lines(cls) -> int:
        return int(os.getenv('MAX_DIFF_LINES', '10'))