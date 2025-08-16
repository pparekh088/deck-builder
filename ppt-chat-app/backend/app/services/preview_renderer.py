"""
Preview Renderer Service
Renders PowerPoint layouts as wireframe images for vision analysis
"""

import asyncio
import subprocess
import tempfile
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from PIL import Image, ImageDraw, ImageFont
import io
import base64

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.util import Inches

from app.models.vision import LayoutPreviewMetadata
from app.utils.geometry import get_shape_bbox_px, emu_to_px
from app.config import settings

logger = logging.getLogger(__name__)

class PreviewRenderer:
    """Renders PowerPoint layouts as preview images"""
    
    def __init__(self):
        self.dpi = getattr(settings, 'VISION_IMAGE_DPI', 192)
        self.libreoffice_path = getattr(settings, 'LIBREOFFICE_PATH', 'soffice')
        self.use_libreoffice = self._check_libreoffice_available()
        
    def _check_libreoffice_available(self) -> bool:
        """Check if LibreOffice is available for rendering"""
        try:
            result = subprocess.run(
                [self.libreoffice_path, '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                logger.info(f"LibreOffice available: {result.stdout.strip()}")
                return True
        except (subprocess.SubprocessError, FileNotFoundError):
            pass
        logger.warning("LibreOffice not available, using fallback renderer")
        return False
    
    async def render_layout_previews(
        self, 
        pptx_bytes: bytes,
        template_id: str
    ) -> Dict[Tuple[int, int], Dict]:
        """
        Render all layouts in a template as preview images
        
        Args:
            pptx_bytes: PPTX file content
            template_id: Template identifier
            
        Returns:
            Dict mapping (master_idx, layout_idx) to preview data
        """
        previews = {}
        
        try:
            # Save bytes to temporary file
            with tempfile.NamedTemporaryFile(suffix='.pptx', delete=False) as tmp_file:
                tmp_file.write(pptx_bytes)
                tmp_path = Path(tmp_file.name)
            
            # Load presentation
            prs = Presentation(str(tmp_path))
            
            # Get slide dimensions
            slide_width_emu = int(prs.slide_width)
            slide_height_emu = int(prs.slide_height)
            
            # Render each layout
            for master_idx, master in enumerate(prs.slide_masters):
                for layout_idx, layout in enumerate(master.slide_layouts):
                    if self.use_libreoffice:
                        preview_data = await self._render_with_libreoffice(
                            tmp_path, master_idx, layout_idx, prs
                        )
                    else:
                        preview_data = self._render_wireframe(
                            layout, master_idx, layout_idx,
                            slide_width_emu, slide_height_emu
                        )
                    
                    previews[(master_idx, layout_idx)] = preview_data
                    
        except Exception as e:
            logger.error(f"Error rendering previews: {str(e)}")
            raise
        finally:
            # Clean up temp file
            if tmp_path.exists():
                tmp_path.unlink()
        
        return previews
    
    def _render_wireframe(
        self,
        layout,
        master_idx: int,
        layout_idx: int,
        slide_width_emu: int,
        slide_height_emu: int
    ) -> Dict:
        """
        Render a simple wireframe representation of a layout
        
        Args:
            layout: PowerPoint layout object
            master_idx: Master slide index
            layout_idx: Layout index
            slide_width_emu: Slide width in EMU
            slide_height_emu: Slide height in EMU
            
        Returns:
            Dict with image data and metadata
        """
        # Calculate pixel dimensions
        width_px = emu_to_px(slide_width_emu, self.dpi)
        height_px = emu_to_px(slide_height_emu, self.dpi)
        
        # Create blank image
        img = Image.new('RGB', (width_px, height_px), 'white')
        draw = ImageDraw.Draw(img)
        
        # Draw placeholders as rectangles
        for placeholder in layout.placeholders:
            try:
                bbox = get_shape_bbox_px(placeholder, self.dpi)
                
                # Draw rectangle with different colors for different types
                color = self._get_placeholder_color(placeholder)
                draw.rectangle(
                    [(bbox['left'], bbox['top']), 
                     (bbox['left'] + bbox['width'], bbox['top'] + bbox['height'])],
                    outline=color,
                    width=2
                )
                
                # Add placeholder type text
                if hasattr(placeholder, 'name'):
                    try:
                        # Try to use a basic font
                        font = ImageFont.load_default()
                        text = placeholder.name[:20]  # Truncate long names
                        draw.text(
                            (bbox['left'] + 5, bbox['top'] + 5),
                            text,
                            fill=color,
                            font=font
                        )
                    except:
                        pass
                        
            except Exception as e:
                logger.warning(f"Could not draw placeholder: {str(e)}")
        
        # Convert to base64
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        image_data = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        # Create metadata
        metadata = LayoutPreviewMetadata(
            master_idx=master_idx,
            layout_idx=layout_idx,
            width_px=width_px,
            height_px=height_px,
            dpi=self.dpi,
            slide_width_emu=slide_width_emu,
            slide_height_emu=slide_height_emu
        )
        
        return {
            'image_data': image_data,
            'image_pil': img,  # Keep PIL image for vision processing
            'metadata': metadata
        }
    
    def _get_placeholder_color(self, placeholder) -> str:
        """Get color for placeholder based on type"""
        from pptx.enum.shapes import PP_PLACEHOLDER
        
        try:
            ph_type = placeholder.placeholder_format.type
            color_map = {
                PP_PLACEHOLDER.TITLE: '#FF6B6B',       # Red
                PP_PLACEHOLDER.BODY: '#4ECDC4',        # Teal
                PP_PLACEHOLDER.PICTURE: '#95E77E',     # Green
                PP_PLACEHOLDER.TABLE: '#FFE66D',       # Yellow
                PP_PLACEHOLDER.CHART: '#A8E6CF',       # Light Green
                PP_PLACEHOLDER.SUBTITLE: '#FFB6C1',    # Pink
                PP_PLACEHOLDER.FOOTER: '#C0C0C0',      # Gray
            }
            return color_map.get(ph_type, '#808080')  # Default gray
        except:
            return '#808080'
    
    async def _render_with_libreoffice(
        self,
        pptx_path: Path,
        master_idx: int,
        layout_idx: int,
        presentation: Presentation
    ) -> Dict:
        """
        Render layout using LibreOffice (more accurate but requires LibreOffice)
        
        Args:
            pptx_path: Path to PPTX file
            master_idx: Master slide index
            layout_idx: Layout index
            presentation: Presentation object
            
        Returns:
            Dict with image data and metadata
        """
        try:
            # Create a temporary presentation with just this layout
            temp_prs = Presentation()
            
            # Copy slide master and layout
            # Note: This is simplified - full implementation would need proper copying
            slide = temp_prs.slides.add_slide(presentation.slide_layouts[layout_idx])
            
            # Save temporary presentation
            with tempfile.NamedTemporaryFile(suffix='.pptx', delete=False) as tmp:
                temp_prs.save(tmp.name)
                temp_pptx = Path(tmp.name)
            
            # Convert to PDF using LibreOffice
            with tempfile.TemporaryDirectory() as tmp_dir:
                cmd = [
                    self.libreoffice_path,
                    '--headless',
                    '--convert-to', 'pdf',
                    '--outdir', tmp_dir,
                    str(temp_pptx)
                ]
                
                result = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                await result.communicate()
                
                if result.returncode != 0:
                    raise Exception("LibreOffice conversion failed")
                
                # Find the PDF file
                pdf_files = list(Path(tmp_dir).glob('*.pdf'))
                if not pdf_files:
                    raise Exception("No PDF generated")
                
                # Convert PDF to PNG (would need pdf2image or similar)
                # For now, fallback to wireframe
                return self._render_wireframe(
                    presentation.slide_layouts[layout_idx],
                    master_idx, layout_idx,
                    int(presentation.slide_width),
                    int(presentation.slide_height)
                )
                
        except Exception as e:
            logger.warning(f"LibreOffice rendering failed: {str(e)}, using wireframe")
            return self._render_wireframe(
                presentation.slide_layouts[layout_idx],
                master_idx, layout_idx,
                int(presentation.slide_width),
                int(presentation.slide_height)
            )
        finally:
            # Clean up temp files
            if temp_pptx.exists():
                temp_pptx.unlink()
    
    def get_shape_candidates(self, layout) -> List[Dict]:
        """
        Extract shape candidates with bounding boxes for vision analysis
        
        Args:
            layout: PowerPoint layout object
            
        Returns:
            List of shape dictionaries with id and bbox
        """
        shapes = []
        
        for idx, placeholder in enumerate(layout.placeholders):
            try:
                bbox_px = get_shape_bbox_px(placeholder, self.dpi)
                shape_id = f"shape_{idx}"
                
                shapes.append({
                    'id': shape_id,
                    'left': bbox_px['left'],
                    'top': bbox_px['top'],
                    'width': bbox_px['width'],
                    'height': bbox_px['height'],
                    'original_idx': placeholder.placeholder_format.idx,
                    'name': placeholder.name if hasattr(placeholder, 'name') else None
                })
            except Exception as e:
                logger.warning(f"Could not extract shape bbox: {str(e)}")
        
        return shapes

# Create singleton instance
preview_renderer = PreviewRenderer()