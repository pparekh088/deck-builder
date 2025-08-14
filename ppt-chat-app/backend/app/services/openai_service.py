from openai import AzureOpenAI
from typing import List, Optional
import logging
from app.config import settings
from app.models import ChatMessage, MessageRole

logger = logging.getLogger(__name__)

class OpenAIService:
    def __init__(self):
        self.client = AzureOpenAI(
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
            azure_endpoint=settings.azure_openai_endpoint
        )
        self.deployment_name = settings.azure_openai_deployment_name
        
    async def generate_presentation_content(
        self, 
        prompt: str, 
        context: Optional[List[ChatMessage]] = None,
        current_markdown: str = ""
    ) -> tuple[str, str]:
        """
        Generate presentation content based on user prompt
        Returns: (response_text, markdown_content)
        """
        try:
            system_prompt = """You are an AI assistant specialized in creating PowerPoint presentations.
            When users ask you to create or modify presentations, you should:
            1. Generate content in a clear, structured markdown format
            2. Use # for slide titles, ## for subtitles, and bullet points for content
            3. Keep slides concise and impactful
            4. Suggest appropriate content based on the topic
            5. Structure the presentation logically
            
            Format your markdown output like this:
            # Slide Title
            - Bullet point 1
            - Bullet point 2
            - Bullet point 3
            
            ## Subtitle (if needed)
            - Additional content
            
            Always maintain professional tone and ensure content is presentation-ready."""
            
            messages = [{"role": "system", "content": system_prompt}]
            
            # Add context if available
            if current_markdown:
                messages.append({
                    "role": "system", 
                    "content": f"Current presentation content:\n{current_markdown}\n\nModify or extend based on user request."
                })
            
            if context:
                for msg in context[-5:]:  # Last 5 messages for context
                    messages.append({
                        "role": msg.role.value,
                        "content": msg.content
                    })
            
            messages.append({"role": "user", "content": prompt})
            
            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=messages,
                temperature=0.7,
                max_tokens=2000
            )
            
            response_text = response.choices[0].message.content
            
            # Extract markdown content for presentation
            markdown_content = self._extract_presentation_markdown(response_text)
            
            return response_text, markdown_content
            
        except Exception as e:
            logger.error(f"Error generating presentation content: {str(e)}")
            raise
    
    def _extract_presentation_markdown(self, text: str) -> str:
        """Extract and clean markdown content suitable for presentation"""
        lines = text.split('\n')
        markdown_lines = []
        in_code_block = False
        
        for line in lines:
            # Skip code block markers
            if line.strip().startswith('```'):
                in_code_block = not in_code_block
                continue
            
            if not in_code_block:
                # Keep headers and bullet points
                if line.strip().startswith('#') or line.strip().startswith('-') or line.strip().startswith('*'):
                    markdown_lines.append(line)
                elif line.strip() and markdown_lines and not line.strip().startswith('Note:'):
                    # Keep non-empty lines that are part of content
                    markdown_lines.append(line)
        
        return '\n'.join(markdown_lines)
    
    async def refine_content(self, markdown: str, instruction: str) -> str:
        """Refine existing presentation content based on user instruction"""
        try:
            prompt = f"""Current presentation content:
            {markdown}
            
            User instruction: {instruction}
            
            Please refine or modify the presentation content according to the instruction.
            Maintain the markdown format with # for titles and - for bullet points."""
            
            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=[
                    {"role": "system", "content": "You are a presentation content editor."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=2000
            )
            
            return self._extract_presentation_markdown(response.choices[0].message.content)
            
        except Exception as e:
            logger.error(f"Error refining content: {str(e)}")
            raise

# Singleton instance
openai_service = OpenAIService()