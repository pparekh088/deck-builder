"""
Simple Slide Tools for Agentic System using MCP Server
Clean, focused tools for slide manipulation via MCP
"""

import logging
import json
import asyncio
from typing import List, Optional
from pathlib import Path
from app.services.openai_service import openai_service
from app.services.mcp_client import mcp_client

logger = logging.getLogger(__name__)

class SimpleSlideTools:
    """Simple, reliable tools for slide manipulation using MCP"""
    
    def __init__(self):
        self._ensure_mcp_connection()
    
    def _ensure_mcp_connection(self):
        """Ensure MCP client is connected"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(mcp_client.connect())
            loop.close()
        except Exception as e:
            logger.warning(f"Failed to connect to MCP server: {e}")
    
    async def _ensure_mcp_connected_async(self):
        """Ensure MCP client is connected (async version)"""
        if not mcp_client.http_client:
            await mcp_client.connect()
    
    def edit_slide_content(
        self, 
        presentation_path: Path, 
        slide_number: int, 
        new_title: Optional[str] = None,
        add_bullets: Optional[List[str]] = None,
        replace_bullets: Optional[List[str]] = None
    ) -> str:
        """Edit content of an existing slide using MCP"""
        try:
            logger.info(f"Editing slide {slide_number}: title={new_title}, add_bullets={add_bullets}, replace_bullets={replace_bullets}")
            
            # Run async version in sync context
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    self._edit_slide_content_async(
                        presentation_path, slide_number, new_title, add_bullets, replace_bullets
                    )
                )
                return result
            finally:
                loop.close()
                
        except Exception as e:
            logger.error(f"Error editing slide: {e}")
            return f"Error editing slide: {str(e)}"
    
    async def _edit_slide_content_async(
        self,
        presentation_path: Path,
        slide_number: int,
        new_title: Optional[str],
        add_bullets: Optional[List[str]],
        replace_bullets: Optional[List[str]]
    ) -> str:
        """Async version of edit_slide_content using MCP"""
        await self._ensure_mcp_connected_async()
        
        # Open the presentation
        presentation_id = await mcp_client.open_presentation(str(presentation_path))
        
        # Get slide info to check if it exists
        slides = await mcp_client.list_slides()
        if slide_number < 1 or slide_number > len(slides):
            return f"Error: Invalid slide number {slide_number}"
        
        slide_index = slide_number - 1  # Convert to 0-based index
        
        # Update title if provided
        if new_title:
            await mcp_client.add_text_to_slide(
                slide_index=slide_index,
                text=new_title,
                placeholder_index=0  # Title placeholder
            )
        
        # Handle bullet points
        if replace_bullets is not None:
            # Replace all content with new bullets
            await mcp_client.add_bullet_points(
                slide_index=slide_index,
                bullet_points=replace_bullets,
                placeholder_index=1  # Content placeholder
            )
        elif add_bullets:
            # Get existing content first
            slide_info = await mcp_client.get_slide_info(slide_index)
            existing_bullets = slide_info.get('content', [])
            
            # Combine existing and new bullets
            all_bullets = existing_bullets + add_bullets
            
            # Update with combined content
            await mcp_client.add_bullet_points(
                slide_index=slide_index,
                bullet_points=all_bullets,
                placeholder_index=1
            )
        
        # Save the presentation
        await mcp_client.save_presentation(str(presentation_path), presentation_id)
        
        return f"Successfully edited slide {slide_number}"
    
    async def add_new_slide(
        self,
        presentation_path: Path,
        title: str,
        bullets: List[str],
        position: Optional[int] = None
    ) -> str:
        """Add a new slide to the presentation using MCP"""
        try:
            await self._ensure_mcp_connected_async()
            
            if not presentation_path.exists():
                return f"Error: Presentation file not found at {presentation_path}"
            
            logger.info(f"Loading presentation from {presentation_path}")
            
            # Open the presentation
            presentation_id = await mcp_client.open_presentation(str(presentation_path))
            
            # Get current slides count
            slides = await mcp_client.list_slides()
            logger.info(f"Presentation loaded, has {len(slides)} slides")
            
            # Find best matching slide for template (simplified for MCP)
            # We'll use a standard title and content layout
            layout_index = await self._find_best_layout_index(presentation_id, title, bullets)
            
            # Add new slide
            result = await mcp_client.add_slide(layout_index=layout_index, position=position)
            new_slide_index = result.get('slide_index', len(slides))
            
            logger.info(f"New slide added at index {new_slide_index}")
            
            # Add title
            if title:
                await mcp_client.add_text_to_slide(
                    slide_index=new_slide_index,
                    text=title,
                    placeholder_index=0  # Title placeholder
                )
            
            # Add bullets
            if bullets:
                await mcp_client.add_bullet_points(
                    slide_index=new_slide_index,
                    bullet_points=bullets,
                    placeholder_index=1  # Content placeholder
                )
            
            # Save the presentation
            await mcp_client.save_presentation(str(presentation_path), presentation_id)
            
            logger.info("Presentation saved successfully")
            return f"Successfully added slide: {title}"
            
        except Exception as e:
            logger.error(f"Error adding slide: {e}")
            return f"Error adding slide: {str(e)}"
    
    async def _find_best_layout_index(self, presentation_id: str, title: str, bullets: List[str]) -> int:
        """Find the best layout index for the new slide"""
        # For MCP, we'll use standard layouts
        # Layout indices typically are:
        # 0: Title slide
        # 1: Title and Content (most common)
        # 2: Section Header
        # 3: Two Content
        # 4: Comparison
        # 5: Title Only
        # 6: Blank
        
        # Default to Title and Content layout
        if title and bullets:
            return 1  # Title and Content
        elif title and not bullets:
            return 5  # Title Only
        elif not title and bullets:
            return 1  # Still use Title and Content, just leave title empty
        else:
            return 6  # Blank
    
    def delete_slide(self, presentation_path: Path, slide_number: int) -> str:
        """Delete a slide from the presentation using MCP"""
        try:
            # Run async version in sync context
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    self._delete_slide_async(presentation_path, slide_number)
                )
                return result
            finally:
                loop.close()
                
        except Exception as e:
            logger.error(f"Error deleting slide: {e}")
            return f"Error deleting slide: {str(e)}"
    
    async def _delete_slide_async(self, presentation_path: Path, slide_number: int) -> str:
        """Async version of delete_slide using MCP"""
        await self._ensure_mcp_connected_async()
        
        # Open the presentation
        presentation_id = await mcp_client.open_presentation(str(presentation_path))
        
        # Get slides to validate slide number
        slides = await mcp_client.list_slides()
        if slide_number < 1 or slide_number > len(slides):
            return f"Error: Invalid slide number {slide_number}"
        
        # Delete the slide (convert to 0-based index)
        await mcp_client.delete_slide(slide_number - 1)
        
        # Save the presentation
        await mcp_client.save_presentation(str(presentation_path), presentation_id)
        
        return f"Successfully deleted slide {slide_number}"
    
    def create_presentation(self, template_path: Path, output_path: Path, user_request: str) -> str:
        """Create a new presentation from template based on user request using MCP"""
        try:
            # Run async version in sync context
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    self._create_presentation_async(template_path, output_path, user_request)
                )
                return result
            finally:
                loop.close()
                
        except Exception as e:
            logger.error(f"Error creating presentation: {e}")
            return f"Error creating presentation: {str(e)}"
    
    async def _create_presentation_async(self, template_path: Path, output_path: Path, user_request: str) -> str:
        """Async version of create_presentation using MCP"""
        await self._ensure_mcp_connected_async()
        
        if not template_path.exists():
            return f"Error: Template file not found at {template_path}"
        
        # Create presentation from template
        if template_path.exists():
            presentation_id = await mcp_client.create_presentation(str(template_path))
        else:
            presentation_id = await mcp_client.create_presentation()
        
        # Save to output path
        await mcp_client.save_presentation(str(output_path), presentation_id)
        
        logger.info(f"Created new presentation from template at {output_path}")
        return f"Successfully created new presentation from template. You can now make follow-up requests to modify specific slides."

# Create singleton
simple_slide_tools = SimpleSlideTools()
