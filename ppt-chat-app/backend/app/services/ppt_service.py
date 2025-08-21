from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN
from PIL import Image
import os
import uuid
from typing import Optional, List, Tuple
import logging
from pathlib import Path
import re
from app.config import settings
from app.models import SlidePreview

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
    
    def save_template(self, file_content: bytes, filename: str, session_id: str) -> str:
        """Save uploaded template and return template ID"""
        try:
            template_id = f"{session_id}_{uuid.uuid4().hex[:8]}"
            template_path = self.templates_dir / f"{template_id}.pptx"
            
            with open(template_path, 'wb') as f:
                f.write(file_content)
            
            # Verify it's a valid PowerPoint file
            prs = Presentation(str(template_path))
            
            # Generate thumbnail from first slide
            thumbnail_path = self._generate_template_thumbnail(prs, template_id)
            
            return template_id
        except Exception as e:
            logger.error(f"Error saving template: {str(e)}")
            raise ValueError(f"Invalid PowerPoint template: {str(e)}")
    
    def _generate_template_thumbnail(self, presentation: Presentation, template_id: str) -> Optional[str]:
        """Generate a thumbnail from the template's first slide"""
        try:
            # For now, we'll return None as generating actual thumbnails requires
            # additional libraries like python-pptx2img or COM automation
            # This is a placeholder for the actual implementation
            return None
        except Exception as e:
            logger.error(f"Error generating thumbnail: {str(e)}")
            return None
    
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
            # Load template or create new presentation
            if template_id:
                template_path = self.templates_dir / f"{template_id}.pptx"
                if template_path.exists():
                    prs = Presentation(str(template_path))
                    # Clear ALL existing slides - we'll use layouts from the template
                    while len(prs.slides) > 0:
                        rId = prs.slides._sldIdLst[0].rId
                        prs.part.drop_rel(rId)
                        del prs.slides._sldIdLst[0]
                else:
                    prs = Presentation()
            else:
                prs = Presentation()
            
            # Parse markdown and create slides
            slides_data = self._parse_markdown(markdown)
            slide_previews = []
            
            for idx, slide_data in enumerate(slides_data):
                slide = self._create_slide(prs, slide_data, template_id is not None)
                
                # Create preview data
                preview = SlidePreview(
                    slide_number=idx + 1,
                    title=slide_data.get('title', f'Slide {idx + 1}'),
                    content='\n'.join(slide_data.get('bullets', [])),
                    image_url=None  # Will be generated if needed
                )
                slide_previews.append(preview)
            
            # Save the presentation
            output_filename = f"{session_id}_{uuid.uuid4().hex[:8]}.pptx"
            output_path = self.uploads_dir / output_filename
            prs.save(str(output_path))
            
            # Generate slide preview images
            self._generate_slide_previews(str(output_path), session_id)
            
            return str(output_path), slide_previews
            
        except Exception as e:
            logger.error(f"Error converting markdown to PPTX: {str(e)}")
            raise
    
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
    
    def _create_slide(self, presentation: Presentation, slide_data: dict, use_template: bool) -> object:
        """Create a slide with the given data"""
        try:
            if use_template:
                # Use a layout from the template (prefer title and content layout)
                # Try to find a title and content layout, fallback to first available
                slide_layout = None
                for layout in presentation.slide_layouts:
                    # Check if layout has both title and content placeholders
                    has_title = any(ph.placeholder_format.type == 1 for ph in layout.placeholders)
                    has_content = any(ph.placeholder_format.type in [7, 2] for ph in layout.placeholders)
                    if has_title and has_content:
                        slide_layout = layout
                        break
                
                # Fallback to first layout if no title+content found
                if not slide_layout:
                    slide_layout = presentation.slide_layouts[0]
            else:
                # Use default title and content layout
                slide_layout = presentation.slide_layouts[1] if len(presentation.slide_layouts) > 1 else presentation.slide_layouts[0]
            
            slide = presentation.slides.add_slide(slide_layout)
            
            # Set title
            if slide.shapes.title:
                slide.shapes.title.text = slide_data.get('title', '')
            
            # Set content
            for shape in slide.shapes:
                if not shape.has_text_frame:
                    continue
                if shape == slide.shapes.title:
                    continue
                    
                text_frame = shape.text_frame
                text_frame.clear()
                
                # Add subtitle if exists
                if slide_data.get('subtitle'):
                    p = text_frame.add_paragraph()
                    p.text = slide_data['subtitle']
                    p.font.bold = True
                    p.font.size = Pt(20)
                    text_frame.add_paragraph()  # Add spacing
                
                # Add bullet points
                for bullet in slide_data.get('bullets', []):
                    p = text_frame.add_paragraph()
                    p.text = bullet
                    p.level = 0
                    p.font.size = Pt(18)
                
                break  # Only fill the first content placeholder
            
            return slide
            
        except Exception as e:
            logger.error(f"Error creating slide: {str(e)}")
            # Fallback to basic slide creation
            slide_layout = presentation.slide_layouts[5]  # Blank layout
            slide = presentation.slides.add_slide(slide_layout)
            
            # Add title manually
            left = Inches(0.5)
            top = Inches(0.5)
            width = Inches(9)
            height = Inches(1)
            
            title_box = slide.shapes.add_textbox(left, top, width, height)
            title_frame = title_box.text_frame
            title_frame.text = slide_data.get('title', '')
            title_frame.paragraphs[0].font.size = Pt(32)
            title_frame.paragraphs[0].font.bold = True
            
            # Add content
            content_top = Inches(2)
            content_height = Inches(4.5)
            
            content_box = slide.shapes.add_textbox(left, content_top, width, content_height)
            content_frame = content_box.text_frame
            
            for bullet in slide_data.get('bullets', []):
                p = content_frame.add_paragraph()
                p.text = f"• {bullet}"
                p.font.size = Pt(18)
            
            return slide
    
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