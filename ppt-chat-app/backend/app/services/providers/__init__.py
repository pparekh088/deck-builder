"""
LLM Provider Factory
Supports Azure OpenAI, OpenAI, and Stub providers for testing
"""

import os
from typing import Any, Optional
from .azure_openai import AzureOpenAIProvider
from .openai import OpenAIProvider
from .stub import StubLLMProvider


def get_llm_provider() -> Any:
    """
    Get the appropriate LLM provider based on environment configuration
    
    Returns:
        LLM provider instance (Azure OpenAI, OpenAI, or Stub)
    """
    # Check for Azure OpenAI credentials
    if os.getenv("AZURE_OPENAI_API_KEY") and os.getenv("AZURE_OPENAI_ENDPOINT"):
        return AzureOpenAIProvider()
    
    # Check for standard OpenAI credentials
    if os.getenv("OPENAI_API_KEY"):
        return OpenAIProvider()
    
    # Fallback to stub provider for testing
    return StubLLMProvider()


__all__ = [
    'get_llm_provider',
    'AzureOpenAIProvider',
    'OpenAIProvider',
    'StubLLMProvider'
]