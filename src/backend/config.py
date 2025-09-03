# src/backend/config.py
import logging
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging based on environment variable
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, log_level),
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class Config:
    def __init__(self):
        # File upload configuration
        self.ALLOWED_EXTENSIONS = os.getenv(
            "ALLOWED_EXTENSIONS", "pdf").split(",")
        self.MAX_FILE_SIZE = int(
            os.getenv("MAX_FILE_SIZE", 2 * 1024 * 1024))  # 2MB
        
        # Flask/FastAPI Configuration
        self.HOST = os.getenv("HOST", "0.0.0.0")
        self.PORT = int(os.getenv("PORT", 8010))
        self.DEBUG = os.getenv("DEBUG", "False").lower() == "true"
        self.ENDPOINT = os.getenv("ENDPOINT", f"http://localhost:{self.PORT}")
        
        # Database configuration - FIXED PostgreSQL port
        self.DATABASE_USER = os.getenv("DATABASE_USER")
        self.DATABASE_PASSWORD = os.getenv("DATABASE_PASSWORD")
        self.DATABASE_HOST = os.getenv("DATABASE_HOST")
        self.DATABASE_PORT = os.getenv("DATABASE_PORT", "5432")  # FIXED: PostgreSQL port
        self.DATABASE_NAME = os.getenv("DATABASE_NAME")
        
        # Pinecone configuration
        self.PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
        self.PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX", "pdf-assistant-index")
        self.PINECONE_CLOUD = os.getenv("PINECONE_CLOUD", "aws")
        self.PINECONE_REGION = os.getenv("PINECONE_REGION", "us-east-1")
        self.PINECONE_DIMENSION = 768
        
        # Google AI configuration - ADDED validation
        self.GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
        
        # Debug logging for troubleshooting
        print(f"DEBUG - DATABASE_HOST: {self.DATABASE_HOST}")
        print(f"DEBUG - DATABASE_PORT: {self.DATABASE_PORT}")
        print(f"DEBUG - DATABASE_USER: {self.DATABASE_USER}")
        print(f"DEBUG - DATABASE_NAME: {self.DATABASE_NAME}")
        print(f"DEBUG - GEMINI_API_KEY exists: {bool(self.GEMINI_API_KEY)}")
        print(f"DEBUG - GEMINI_API_KEY length: {len(self.GEMINI_API_KEY) if self.GEMINI_API_KEY else 0}")
        if self.GEMINI_API_KEY:
            print(f"DEBUG - GEMINI_API_KEY starts with: {self.GEMINI_API_KEY[:10]}...")

        logger.info("Configuration loaded successfully")

    def validate_database_config(self):
        """Validate database configuration when needed."""
        if not self.DATABASE_PORT or not self.DATABASE_PORT.isdigit():
            logger.error(f"Invalid DATABASE_PORT: {self.DATABASE_PORT}")
            raise ValueError(f"DATABASE_PORT must be a valid integer, got: {self.DATABASE_PORT}")
        
        if not all([self.DATABASE_USER, self.DATABASE_PASSWORD, 
                   self.DATABASE_HOST, self.DATABASE_NAME]):
            missing = [key for key, val in {
                'DATABASE_USER': self.DATABASE_USER,
                'DATABASE_PASSWORD': self.DATABASE_PASSWORD,
                'DATABASE_HOST': self.DATABASE_HOST,
                'DATABASE_NAME': self.DATABASE_NAME
            }.items() if not val]
            logger.error(f"Missing required database environment variables: {missing}")
            raise ValueError(f"Missing required database environment variables: {missing}")

    def validate_pinecone_config(self):
        """Validate Pinecone configuration when needed."""
        if not self.PINECONE_API_KEY or not self.PINECONE_API_KEY.strip():
            logger.error("PINECONE_API_KEY environment variable is not set or empty")
            raise ValueError("PINECONE_API_KEY is required and cannot be empty")

    def validate_gemini_config(self):
        """Validate Gemini configuration when needed."""
        if not self.GEMINI_API_KEY or not self.GEMINI_API_KEY.strip():
            logger.error("GEMINI_API_KEY environment variable is not set or empty")
            raise ValueError("GEMINI_API_KEY is required and cannot be empty")
        
        # Additional validation for Gemini API key format
        if not self.GEMINI_API_KEY.startswith('AIza'):
            logger.warning("GEMINI_API_KEY doesn't start with 'AIza' - this may not be a valid Google AI API key")
        
        if len(self.GEMINI_API_KEY) < 30:
            logger.warning("GEMINI_API_KEY seems too short - typical keys are 39+ characters")

    @staticmethod
    def validate_required_env_vars():
        """Validate all required environment variables for ChatbotAgent."""
        config_instance = Config()
        config_instance.validate_pinecone_config()
        config_instance.validate_gemini_config()

    @property
    def database_url(self):
        """Get database URL, validating config first."""
        self.validate_database_config()
        return (
            f"postgresql+psycopg2://{self.DATABASE_USER}:{self.DATABASE_PASSWORD}"
            f"@{self.DATABASE_HOST}:{self.DATABASE_PORT}/{self.DATABASE_NAME}"
            f"?sslmode=require"
        )


# Global config instance
config = Config()