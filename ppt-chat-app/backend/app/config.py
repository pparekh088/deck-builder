from pydantic_settings import BaseSettings
from typing import List, Optional
from pydantic import field_validator
import os

class Settings(BaseSettings):
    # Azure OpenAI Configuration
    azure_openai_api_key: str = ""
    azure_openai_endpoint: str = ""
    azure_openai_deployment_name: str = "gpt-4-turbo"
    azure_openai_api_version: str = "2024-02-01"
    
    # Vision Model Configuration
    HYBRID_VISION_ENABLED: bool = True
    VISION_PROVIDER: str = "openai"  # openai|azure|stub
    VISION_MODEL: str = "gpt-4o-mini"  # or azure deployment name for vision
    VISION_IMAGE_DPI: int = 192
    LIBREOFFICE_PATH: str = "soffice"
    
    # Accuracy++ Features
    ACCURATE_SOLVER_ENABLED: bool = True
    RENDER_MEASURE_ENABLED: bool = True
    ARCHETYPE_ALIGNMENT_ENABLED: bool = True
    SAFETY_MAP_ENABLED: bool = True
    
    # Rendering Configuration
    PDF_RASTER_DPI: int = 192
    MIN_FONT_SIZE: int = 10  # Minimum font size for overflow fixes
    MAX_FONT_SIZE: int = 44  # Maximum font size for overflow fixes
    OVERFLOW_THRESHOLD: float = 0.1  # Threshold for detecting overflow
    
    # Solver Configuration
    SOLVER_TIMEOUT: int = 10  # Timeout in seconds for ILP solver
    SOLVER_MSG: bool = False  # Show solver messages
    
    # Application Settings
    secret_key: str = "your-secret-key-here"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # Redis Configuration
    redis_url: str = "redis://localhost:6379"
    redis_password: Optional[str] = None
    redis_db: int = 0
    redis_decode_responses: bool = True
    
    # CORS Settings
    cors_origins: str = "http://localhost:5174,http://localhost:3000"
    
    # File Upload Settings
    max_file_size: int = 10485760  # 10MB
    upload_dir: str = "uploads"
    templates_dir: str = "templates"
    
    class Config:
        env_file = ".env"
        case_sensitive = False
    
    def get_cors_origins(self) -> List[str]:
        """Convert comma-separated CORS origins string to list"""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
    
    def get_redis_url(self) -> str:
        """Build Redis URL with authentication if password is provided"""
        if self.redis_password:
            # Parse the base URL and add authentication
            if "://" in self.redis_url:
                protocol, rest = self.redis_url.split("://", 1)
                # Remove any existing auth from URL
                if "@" in rest:
                    rest = rest.split("@", 1)[1]
                return f"{protocol}://:{self.redis_password}@{rest}/{self.redis_db}"
            else:
                return f"redis://:{self.redis_password}@{self.redis_url}/{self.redis_db}"
        else:
            # Add DB number to URL if not present
            if self.redis_url.endswith("/"):
                return f"{self.redis_url}{self.redis_db}"
            elif "/" not in self.redis_url.split("://", 1)[1]:
                return f"{self.redis_url}/{self.redis_db}"
            else:
                return self.redis_url

settings = Settings()

# Create directories if they don't exist
os.makedirs(settings.upload_dir, exist_ok=True)
os.makedirs(settings.templates_dir, exist_ok=True)
os.makedirs(f"{settings.upload_dir}/previews", exist_ok=True)