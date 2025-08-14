from pydantic_settings import BaseSettings
from typing import List
import os

class Settings(BaseSettings):
    # Azure OpenAI Configuration
    azure_openai_api_key: str = ""
    azure_openai_endpoint: str = ""
    azure_openai_deployment_name: str = "gpt-4-turbo"
    azure_openai_api_version: str = "2024-02-01"
    
    # Application Settings
    secret_key: str = "your-secret-key-here"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # Redis Configuration
    redis_url: str = "redis://localhost:6379"
    
    # CORS Settings
    cors_origins: List[str] = ["http://localhost:5173", "http://localhost:3000"]
    
    # File Upload Settings
    max_file_size: int = 10485760  # 10MB
    upload_dir: str = "uploads"
    templates_dir: str = "templates"
    
    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()

# Create directories if they don't exist
os.makedirs(settings.upload_dir, exist_ok=True)
os.makedirs(settings.templates_dir, exist_ok=True)
os.makedirs(f"{settings.upload_dir}/previews", exist_ok=True)