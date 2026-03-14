import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Application configuration"""

    @classmethod
    def use_local_model(cls) -> bool:
        """Whether to use local model or Azure Foundry"""
        return os.getenv('USE_LOCAL_MODEL', 'true').lower() == 'true'

    @classmethod
    def get_model_path(cls) -> str:
        """Path to local model file"""
        return os.getenv('MODEL_PATH', 'models/llama-2-7b-chat.ggmlv3.q4_0.bin')

    @classmethod
    def get_model_context(cls) -> int:
        """Context size for the model"""
        return int(os.getenv('MODEL_CONTEXT', '2048'))

    @classmethod
    def get_model_threads(cls) -> int:
        """Number of threads for the model"""
        return int(os.getenv('MODEL_THREADS', '4'))

    @classmethod
    def get_model_batch(cls) -> int:
        """Batch size for the model"""
        return int(os.getenv('MODEL_BATCH', '8'))

    @classmethod
    def get_model_gpu_layers(cls) -> int:
        """Number of GPU layers to use"""
        return int(os.getenv('MODEL_GPU_LAYERS', '0'))

    @classmethod
    def get_endpoint(cls) -> str:
        """Azure Foundry endpoint"""
        return os.getenv('AZURE_ENDPOINT', '')

    @classmethod
    def get_api_key(cls) -> str:
        """Azure Foundry API key"""
        return os.getenv('AZURE_API_KEY', '')

    @classmethod
    def get_model_name(cls) -> str:
        """Azure Foundry model name"""
        return os.getenv('AZURE_MODEL_NAME', 'gpt-35-turbo')

    @classmethod
    def get_output_tokens(cls) -> int:
        """Maximum output tokens"""
        return int(os.getenv('OUTPUT_TOKENS', '1024'))

    @classmethod
    def get_temperature(cls) -> float:
        """Temperature for local model"""
        return float(os.getenv('TEMPERATURE', '0.7'))

    @classmethod
    def get_top_p(cls) -> float:
        """Top_p for local model"""
        return float(os.getenv('TOP_P', '0.9'))

    @classmethod
    def get_top_k(cls) -> int:
        """Top_k for local model"""
        return int(os.getenv('TOP_K', '40'))

    @classmethod
    def get_min_p(cls) -> float:
        """Min_p for local model"""
        return float(os.getenv('MIN_P', '0.05'))

    @classmethod
    def get_smtp_host(cls) -> str:
        """SMTP host for email notifications"""
        return os.getenv('SMTP_HOST', '')

    @classmethod
    def get_smtp_port(cls) -> int:
        """SMTP port for email notifications"""
        return int(os.getenv('SMTP_PORT', '587'))

    @classmethod
    def get_smtp_user(cls) -> str:
        """SMTP username for email notifications"""
        return os.getenv('SMTP_USER', '')

    @classmethod
    def get_smtp_password(cls) -> str:
        """SMTP password for email notifications"""
        return os.getenv('SMTP_PASSWORD', '')

    @classmethod
    def get_smtp_from(cls) -> str:
        """From email address for notifications"""
        return os.getenv('SMTP_FROM', 'bot@yourdomain.com')

    @classmethod
    def get_bug_notification_emails(cls) -> str:
        """Comma-separated list of email addresses for bug notifications"""
        return os.getenv('BUG_NOTIFICATION_EMAILS', '')

    @classmethod
    def get_allowed_origins(cls) -> str:
        """Allowed origins for CORS"""
        return os.getenv('ALLOWED_ORIGINS', '*')

    @classmethod
    def get_debug(cls) -> bool:
        """Debug mode"""
        return os.getenv('DEBUG', 'false').lower() == 'true'