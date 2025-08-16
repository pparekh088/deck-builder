"""
Azure OpenAI Provider
"""

import os
import json
from typing import Dict, Any, List, Optional
from openai import AzureOpenAI
import logging

logger = logging.getLogger(__name__)


class AzureOpenAIProvider:
    """Azure OpenAI provider for LLM operations"""
    
    def __init__(self):
        self.client = AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
        )
        self.deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini")
        logger.info(f"Initialized Azure OpenAI provider with deployment: {self.deployment}")
    
    async def generate_presentation_content(
        self,
        prompt: str,
        chat_history: List[Dict[str, str]] = None,
        current_markdown: str = None
    ) -> tuple[str, str]:
        """Generate presentation content using Azure OpenAI"""
        
        messages = [
            {"role": "system", "content": "You are a presentation expert. Generate structured content for PowerPoint presentations."}
        ]
        
        if chat_history:
            for msg in chat_history:
                messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
        
        messages.append({"role": "user", "content": prompt})
        
        response = self.client.chat.completions.create(
            model=self.deployment,
            messages=messages,
            temperature=0.7,
            max_tokens=2000
        )
        
        content = response.choices[0].message.content
        
        # Parse markdown from response
        markdown = self._extract_markdown(content)
        
        return content, markdown
    
    def _extract_markdown(self, content: str) -> str:
        """Extract markdown from response content"""
        # Simple extraction - look for markdown blocks
        lines = content.split('\n')
        markdown_lines = []
        in_slide = False
        
        for line in lines:
            if line.startswith('## Slide'):
                in_slide = True
                markdown_lines.append(line)
            elif in_slide:
                if line.startswith('## ') and not line.startswith('## Slide'):
                    in_slide = False
                else:
                    markdown_lines.append(line)
        
        return '\n'.join(markdown_lines) if markdown_lines else content
    
    async def analyze_with_vision(
        self,
        image_data: bytes,
        prompt: str = "Analyze this slide layout"
    ) -> Dict[str, Any]:
        """Analyze image using Azure OpenAI vision capabilities"""
        
        # For vision, we'd use a vision-capable deployment
        # This is a simplified version
        response = self.client.chat.completions.create(
            model=self.deployment,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        # Image would be included here in actual implementation
                    ]
                }
            ],
            max_tokens=500
        )
        
        # Parse JSON response
        try:
            result = json.loads(response.choices[0].message.content)
        except:
            result = {
                "labels": [],
                "description": response.choices[0].message.content
            }
        
        return result