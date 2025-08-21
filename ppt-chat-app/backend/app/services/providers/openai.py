"""
Standard OpenAI Provider
"""

import os
import json
from typing import Dict, Any, List, Optional
from openai import OpenAI
import logging

logger = logging.getLogger(__name__)


class OpenAIProvider:
    """Standard OpenAI provider for LLM operations"""
    
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        logger.info(f"Initialized OpenAI provider with model: {self.model}")
    
    async def generate_presentation_content(
        self,
        prompt: str,
        chat_history: List[Dict[str, str]] = None,
        current_markdown: str = None
    ) -> tuple[str, str]:
        """Generate presentation content using OpenAI"""
        
        messages = [
            {"role": "system", "content": "You are a presentation expert. Generate structured content for PowerPoint presentations in markdown format."}
        ]
        
        if chat_history:
            for msg in chat_history:
                messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
        
        messages.append({"role": "user", "content": prompt})
        
        response = self.client.chat.completions.create(
            model=self.model,
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
        """Analyze image using OpenAI vision capabilities"""
        
        # For vision-capable models
        response = self.client.chat.completions.create(
            model="gpt-4-vision-preview",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        # Image would be included here
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