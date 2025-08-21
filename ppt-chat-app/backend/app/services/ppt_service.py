"""
PowerPoint Service using MCP Server Integration
Replaces direct python-pptx manipulation with MCP server calls
"""

import os
import uuid
import asyncio
from typing import Optional, List, Tuple
import logging
from pathlib import Path
import re
from app.config import settings
from app.models import SlidePreview
from app.services.mcp_client import mcp_client

logger = logging.getLogger(__name__)

class PowerPointService:
    def __init__(self):
        self.templates_dir = Path(settings.templates_dir)
        self.uploads_dir = Path(settings.upload_dir)
        self.previews_dir = self.uploads_dir / "previews"
        
        # Ensure directories exist
        self.templates_dir.mkdir(exist_ok=True)
        self.uploads_dir.mkdir(exist_ok=True)
        self.previews_dir.mkdir(exist_ok=True)
        
        # Initialize MCP connection on startup
        self._ensure_mcp_connection()
    
    def _ensure_mcp_connection(self):
        """Ensure MCP client is connected"""
        try:
            # Run async connection in sync context
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(mcp_client.connect())
            loop.close()
        except Exception as e:
            logger.warning(f"Failed to connect to MCP server: {e}")
            # Continue without MCP - will try to reconnect on each operation
    
    async def _ensure_mcp_connected_async(self):
        """Ensure MCP client is connected (async version)"""
        if not mcp_client.http_client:
            await mcp_client.connect()
    
    def save_template(self, file_content: bytes, filename: str, session_id: str) -> str:
        """Save uploaded template and return template ID"""
        try:
            template_id = f"{session_id}_{uuid.uuid4().hex[:8]}"
            template_path = self.templates_dir / f"{template_id}.pptx"
            
            with open(template_path, 'wb') as f:
                f.write(file_content)
            
            # Verify it's a valid PowerPoint file using MCP
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self._verify_template_async(str(template_path)))
            finally:
                loop.close()
            
            return template_id
        except Exception as e:
            logger.error(f"Error saving template: {str(e)}")
            raise ValueError(f"Invalid PowerPoint template: {str(e)}")
    
    async def _verify_template_async(self, template_path: str):
        """Verify template is valid by opening it with MCP"""
        await self._ensure_mcp_connected_async()
        await mcp_client.open_presentation(template_path)
    

    
    def markdown_to_pptx(
        self, 
        markdown: str, 
        template_id: Optional[str] = None,
        session_id: str = ""
    ) -> Tuple[str, List[SlidePreview]]:
        """
        Convert markdown to PowerPoint using template if provided
        Returns: (pptx_path, slide_previews)
        """
        try:
            # Run async version in sync context
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    self._markdown_to_pptx_async(markdown, template_id, session_id)
                )
                return result
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"Error converting markdown to PPTX: {str(e)}")
            raise
    
    async def _markdown_to_pptx_async(
        self,
        markdown: str,
        template_id: Optional[str] = None,
        session_id: str = ""
    ) -> Tuple[str, List[SlidePreview]]:
        """Async version of markdown to PPTX conversion using MCP"""
        await self._ensure_mcp_connected_async()
        
        # Create or open presentation
        if template_id:
            template_path = self.templates_dir / f"{template_id}.pptx"
            if template_path.exists():
                presentation_id = await mcp_client.open_presentation(str(template_path))
                # Clear existing slides if needed
                slides = await mcp_client.list_slides()
                for i in range(len(slides) - 1, -1, -1):
                    await mcp_client.delete_slide(i)
            else:
                presentation_id = await mcp_client.create_presentation()
        else:
            presentation_id = await mcp_client.create_presentation()
        
        # Parse markdown and create slides
        slides_data = self._parse_markdown(markdown)
        slide_previews = []
        
        for idx, slide_data in enumerate(slides_data):
            # Add slide using MCP
            await mcp_client.add_slide(layout_index=1)  # Use title and content layout
            
            # Add title
            if slide_data.get('title'):
                await mcp_client.add_text_to_slide(
                    slide_index=idx,
                    text=slide_data['title'],
                    placeholder_index=0  # Title placeholder
                )
            
            # Add bullets
            if slide_data.get('bullets'):
                await mcp_client.add_bullet_points(
                    slide_index=idx,
                    bullet_points=slide_data['bullets'],
                    placeholder_index=1  # Content placeholder
                )
            
            # Create preview data
            preview = SlidePreview(
                slide_number=idx + 1,
                title=slide_data.get('title', f'Slide {idx + 1}'),
                content='\n'.join(slide_data.get('bullets', [])),
                image_url=None
            )
            slide_previews.append(preview)
        
        # Save the presentation
        output_filename = f"{session_id}_{uuid.uuid4().hex[:8]}.pptx"
        output_path = self.uploads_dir / output_filename
        await mcp_client.save_presentation(str(output_path), presentation_id)
        
        return str(output_path), slide_previews
    
    def parse_markdown_to_slides(self, markdown: str) -> List[SlidePreview]:
        """Parse markdown and return lightweight slide previews without writing a file"""
        try:
            slides_data = self._parse_markdown(markdown or "")
            previews: List[SlidePreview] = []
            for idx, slide_data in enumerate(slides_data):
                previews.append(
                    SlidePreview(
                        slide_number=idx + 1,
                        title=slide_data.get('title', f'Slide {idx + 1}'),
                        content='\n'.join(slide_data.get('bullets', [])),
                        image_url=None
                    )
                )
            return previews
        except Exception as e:
            logger.error(f"Error parsing markdown to slides: {str(e)}")
            return []

    def generate_presentation(
        self,
        markdown: str,
        template_id: Optional[str],
        session_id: str
    ) -> str:
        """Create a PPTX for the session and place it at uploads/{session_id}_presentation.pptx

        Returns absolute output path.
        """
        try:
            tmp_path, _ = self.markdown_to_pptx(markdown, template_id, session_id)
            target_path = self.uploads_dir / f"{session_id}_presentation.pptx"
            # Overwrite if exists
            try:
                if Path(tmp_path) != target_path:
                    # Replace target with tmp file contents
                    Path(target_path).unlink(missing_ok=True)
                    Path(tmp_path).rename(target_path)
                else:
                    # Already at target
                    pass
            except Exception:
                # Fallback to copy contents
                with open(tmp_path, 'rb') as src, open(target_path, 'wb') as dst:
                    dst.write(src.read())
                Path(tmp_path).unlink(missing_ok=True)
            return str(target_path)
        except Exception as e:
            logger.error(f"Error generating presentation: {str(e)}")
            raise
    
    def _parse_markdown(self, markdown: str) -> List[dict]:
        """Parse markdown into slide data structures"""
        slides = []
        current_slide = None
        
        lines = markdown.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            
            # Check for title (# heading)
            if line.startswith('# '):
                if current_slide:
                    slides.append(current_slide)
                current_slide = {
                    'title': line[2:].strip(),
                    'subtitle': '',
                    'bullets': []
                }
            # Check for subtitle (## heading)
            elif line.startswith('## ') and current_slide:
                current_slide['subtitle'] = line[3:].strip()
            # Check for bullet points
            elif (line.startswith('- ') or line.startswith('* ')) and current_slide:
                current_slide['bullets'].append(line[2:].strip())
            # Add to current content if exists
            elif line and current_slide and not line.startswith('#'):
                if current_slide['bullets']:
                    current_slide['bullets'][-1] += ' ' + line
        
        # Add the last slide
        if current_slide:
            slides.append(current_slide)
        
        # If no slides were created, create a default one
        if not slides:
            slides.append({
                'title': 'Presentation',
                'subtitle': '',
                'bullets': markdown.split('\n') if markdown else ['Add content here']
            })
        
        return slides
    

    
    def _generate_slide_previews(self, pptx_path: str, session_id: str) -> List[str]:
        """Generate preview images for slides"""
        # This is a placeholder - actual implementation would require
        # additional libraries like python-pptx2img or unoconv
        # For now, we'll return empty list
        return []
    
    def get_presentation_path(self, session_id: str) -> Optional[str]:
        """Get the most recent presentation file for a session"""
        try:
            session_files = list(self.uploads_dir.glob(f"{session_id}_*.pptx"))
            if session_files:
                # Return the most recent file
                return str(max(session_files, key=os.path.getctime))
            return None
        except Exception as e:
            logger.error(f"Error getting presentation path: {str(e)}")
            return None

# Singleton instance
ppt_service = PowerPointService()