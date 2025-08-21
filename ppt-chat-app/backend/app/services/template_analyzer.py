"""
Template Analyzer Service
Analyzes PowerPoint templates to extract layouts, placeholders, themes, and brand assets
"""

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE, PP_PLACEHOLDER
from pptx.util import Inches
from pathlib import Path
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime
import colorsys
import numpy as np

from app.models import (
    TemplateProfile, SlideLayoutSignature, PlaceholderInfo,
    PlaceholderType, ThemeInfo, BrandAsset
)

# Import new analysis modules
from ..analysis.archetypes import (
    nearest_archetype, shape_from_dict, ShapeSig, align_to_archetype
)
from ..analysis.safety_map import (
    make_safety_mask, compute_shape_safety_scores, encode_mask_to_string
)
from ..utils.geometry import emu_to_px
from ..config import settings

logger = logging.getLogger(__name__)

class TemplateAnalyzer:
    """Analyzes PowerPoint templates to extract structural information"""
    
    def __init__(self):
        self.placeholder_type_mapping = {
            PP_PLACEHOLDER.TITLE: PlaceholderType.TITLE,
            PP_PLACEHOLDER.BODY: PlaceholderType.BODY,
            PP_PLACEHOLDER.CHART: PlaceholderType.CHART,
            PP_PLACEHOLDER.TABLE: PlaceholderType.TABLE,
            PP_PLACEHOLDER.PICTURE: PlaceholderType.PICTURE,
            PP_PLACEHOLDER.SUBTITLE: PlaceholderType.SUBTITLE,
            PP_PLACEHOLDER.FOOTER: PlaceholderType.FOOTER,
            PP_PLACEHOLDER.HEADER: PlaceholderType.HEADER,
            PP_PLACEHOLDER.DATE: PlaceholderType.DATE,
            PP_PLACEHOLDER.SLIDE_NUMBER: PlaceholderType.SLIDE_NUMBER,
            # PP_PLACEHOLDER.CONTENT doesn't exist in python-pptx
            PP_PLACEHOLDER.OBJECT: PlaceholderType.CONTENT,  # Generic content
            PP_PLACEHOLDER.MEDIA_CLIP: PlaceholderType.PICTURE,  # Treat as picture
            PP_PLACEHOLDER.VERTICAL_BODY: PlaceholderType.BODY,
            PP_PLACEHOLDER.VERTICAL_OBJECT: PlaceholderType.CONTENT,
            PP_PLACEHOLDER.VERTICAL_TITLE: PlaceholderType.TITLE,
        }
    
    async def analyze_template(self, template_path: Path, template_id: str) -> TemplateProfile:
        """
        Analyze a PowerPoint template and extract its profile
        
        Args:
            template_path: Path to the template file
            template_id: Unique identifier for the template
            
        Returns:
            TemplateProfile with all extracted information
        """
        try:
            logger.info(f"Analyzing template: {template_path}")
            prs = Presentation(str(template_path))
            
            # Extract layout signatures
            layout_catalog = self._extract_layouts(prs)
            
            # Extract theme information
            theme = self._extract_theme(prs)
            
            # Extract brand assets
            brand_assets = self._extract_brand_assets(prs)
            
            # Get presentation dimensions
            slide_width = prs.slide_width / Inches(1)
            slide_height = prs.slide_height / Inches(1)
            
            profile = TemplateProfile(
                template_id=template_id,
                layout_catalog=layout_catalog,
                theme=theme,
                brand_assets=brand_assets,
                slide_width=slide_width,
                slide_height=slide_height,
                analyzed_at=datetime.now()
            )
            
            logger.info(f"Template analysis complete: {len(layout_catalog)} layouts found")
            return profile
            
        except Exception as e:
            logger.error(f"Error analyzing template: {str(e)}")
            raise
    
    def _extract_layouts(self, presentation: Presentation) -> List[SlideLayoutSignature]:
        """Extract all slide layouts and their placeholders"""
        layouts = []
        
        # Get slide dimensions for normalization
        slide_width_emu = presentation.slide_width
        slide_height_emu = presentation.slide_height
        slide_width_px = emu_to_px(slide_width_emu, settings.VISION_IMAGE_DPI)
        slide_height_px = emu_to_px(slide_height_emu, settings.VISION_IMAGE_DPI)
        
        for idx, layout in enumerate(presentation.slide_layouts):
            placeholders = []
            shape_sigs = []  # For archetype detection
            
            for placeholder in layout.placeholders:
                placeholder_type = self._get_placeholder_type(placeholder)
                
                # Get dimensions if available
                width = height = left = top = None
                bbox_norm = None
                bbox_px = None
                
                try:
                    if hasattr(placeholder, 'width'):
                        width = placeholder.width / Inches(1)
                    if hasattr(placeholder, 'height'):
                        height = placeholder.height / Inches(1)
                    if hasattr(placeholder, 'left'):
                        left = placeholder.left / Inches(1)
                    if hasattr(placeholder, 'top'):
                        top = placeholder.top / Inches(1)
                    
                    # Compute normalized bbox (0..1)
                    if all(v is not None for v in [left, top, width, height]):
                        left_norm = placeholder.left / slide_width_emu
                        top_norm = placeholder.top / slide_height_emu
                        width_norm = placeholder.width / slide_width_emu
                        height_norm = placeholder.height / slide_height_emu
                        bbox_norm = (left_norm, top_norm, width_norm, height_norm)
                        
                        # Also compute pixel bbox
                        bbox_px = {
                            "left": emu_to_px(placeholder.left, settings.VISION_IMAGE_DPI),
                            "top": emu_to_px(placeholder.top, settings.VISION_IMAGE_DPI),
                            "width": emu_to_px(placeholder.width, settings.VISION_IMAGE_DPI),
                            "height": emu_to_px(placeholder.height, settings.VISION_IMAGE_DPI)
                        }
                        
                        # Create shape signature for archetype detection
                        shape_sig = ShapeSig(
                            kind=placeholder_type.value,  # Convert enum to string
                            role=placeholder.name,
                            bbox_norm=bbox_norm
                        )
                        shape_sigs.append(shape_sig)
                except:
                    pass
                
                # Determine orientation for vertical title/body placeholders
                is_vertical = False
                try:
                    if width and height and height > 0 and width / height < 0.4:
                        # Very tall and narrow placeholder → treat as vertical
                        is_vertical = True
                except Exception:
                    pass

                placeholder_info = PlaceholderInfo(
                    idx=placeholder.placeholder_format.idx,
                    type=placeholder_type,
                    name=placeholder.name,
                    is_vertical=is_vertical,
                    width=width,
                    height=height,
                    left=left,
                    top=top,
                    bbox_norm=bbox_norm,  # Add normalized bbox
                    bbox_px=bbox_px  # Add pixel bbox
                )
                placeholders.append(placeholder_info)
            
            # Detect archetype if enabled
            archetype_hint = None
            if settings.ARCHETYPE_ALIGNMENT_ENABLED and shape_sigs:
                archetype_hint = nearest_archetype(shape_sigs)
                logger.debug(f"Layout {idx} detected archetype: {archetype_hint}")
            
            # Create layout signature
            layout_sig = SlideLayoutSignature(
                layout_id=idx,
                name=layout.name,
                placeholders=placeholders,
                notes=self._get_layout_description(layout.name, placeholders),
                archetype_hint=archetype_hint,  # Add archetype
                slide_width=slide_width_px,
                slide_height=slide_height_px
            )
            layouts.append(layout_sig)
            
            logger.debug(f"Layout {idx} '{layout.name}': {len(placeholders)} placeholders, archetype: {archetype_hint}")
        
        return layouts
    
    def _get_placeholder_type(self, placeholder) -> PlaceholderType:
        """Determine the type of a placeholder"""
        try:
            if hasattr(placeholder, 'placeholder_format'):
                ph_type = placeholder.placeholder_format.type
                return self.placeholder_type_mapping.get(ph_type, PlaceholderType.CONTENT)
        except:
            pass
        return PlaceholderType.CONTENT
    
    def _get_layout_description(self, layout_name: str, placeholders: List[PlaceholderInfo]) -> str:
        """Generate a description of what the layout is good for"""
        title_count = sum(1 for p in placeholders if p.type == PlaceholderType.TITLE)
        body_count = sum(1 for p in placeholders if p.type == PlaceholderType.BODY)
        picture_count = sum(1 for p in placeholders if p.type == PlaceholderType.PICTURE)
        table_count = sum(1 for p in placeholders if p.type == PlaceholderType.TABLE)
        chart_count = sum(1 for p in placeholders if p.type == PlaceholderType.CHART)
        
        descriptions = []
        if title_count > 0:
            descriptions.append(f"{title_count} title")
        if body_count > 0:
            descriptions.append(f"{body_count} body")
        if picture_count > 0:
            descriptions.append(f"{picture_count} picture")
        if table_count > 0:
            descriptions.append(f"{table_count} table")
        if chart_count > 0:
            descriptions.append(f"{chart_count} chart")
        
        if descriptions:
            return f"Layout with {', '.join(descriptions)}"
        return "Custom layout"
    
    def _extract_theme(self, presentation: Presentation) -> ThemeInfo:
        """Extract theme information from the presentation"""
        theme = ThemeInfo()
        
        try:
            # First, try to extract fonts from actual slides (more reliable)
            title_font = None
            body_font = None
            title_size = None
            body_size = None
            
            # Slides collection doesn't support slicing; iterate by index
            for i in range(min(5, len(presentation.slides))):
                slide = presentation.slides[i]
                for shape in slide.shapes:
                    if hasattr(shape, 'text_frame') and shape.text_frame and shape.text:
                        for paragraph in shape.text_frame.paragraphs:
                            if paragraph.text and paragraph.runs:
                                run = paragraph.runs[0]
                                if run.font.name:
                                    # Guess if it's title or body based on size
                                    if run.font.size and run.font.size.pt > 24:
                                        title_font = run.font.name
                                        title_size = int(run.font.size.pt)
                                    else:
                                        body_font = run.font.name
                                        body_size = int(run.font.size.pt) if run.font.size else 18
                                    
                if title_font and body_font:
                    break
            
            # Use discovered fonts or fall back to master theme
            if title_font or body_font:
                theme.font_scheme['major'] = title_font or body_font or 'Calibri'
                theme.font_scheme['minor'] = body_font or title_font or 'Calibri'
                if title_size:
                    theme.default_font_size = title_size
            else:
                # Fall back to master theme
                master = None
                if presentation.slide_masters:
                    master = presentation.slide_masters[0]
                    # Extract font scheme
                    if hasattr(master, 'theme') and hasattr(master.theme, 'font_scheme'):
                        font_scheme = master.theme.font_scheme
                        if hasattr(font_scheme, 'major_font'):
                            theme.font_scheme['major'] = str(font_scheme.major_font.latin.typeface)
                        if hasattr(font_scheme, 'minor_font'):
                            theme.font_scheme['minor'] = str(font_scheme.minor_font.latin.typeface)
                    # Extract color scheme
                    if hasattr(master, 'theme') and hasattr(master.theme, 'color_scheme'):
                        color_scheme = master.theme.color_scheme
                        theme.color_scheme = self._extract_color_scheme(color_scheme)
                
                # Try to get default font size from title placeholder
                for layout in presentation.slide_layouts:
                    for placeholder in layout.placeholders:
                        if placeholder.placeholder_format.type == PP_PLACEHOLDER.TITLE:
                            if hasattr(placeholder, 'text_frame'):
                                for paragraph in placeholder.text_frame.paragraphs:
                                    if paragraph.font.size:
                                        theme.default_font_size = int(paragraph.font.size.pt)
                                        break
                            if theme.default_font_size:
                                break
                    if theme.default_font_size:
                        break
        except Exception as e:
            logger.warning(f"Could not fully extract theme: {str(e)}")
        
        # Set defaults if not found
        if not theme.font_scheme:
            theme.font_scheme = {'major': 'Calibri', 'minor': 'Calibri'}
        if not theme.default_font_size:
            theme.default_font_size = 18
        
        return theme
    
    def _extract_color_scheme(self, color_scheme) -> Dict[str, str]:
        """Extract color scheme to hex values"""
        colors = {}
        color_attrs = [
            'accent1', 'accent2', 'accent3', 'accent4', 'accent5', 'accent6',
            'background1', 'background2', 'text1', 'text2', 'hyperlink', 'followed_hyperlink'
        ]
        
        for attr in color_attrs:
            try:
                if hasattr(color_scheme, attr):
                    color = getattr(color_scheme, attr)
                    if hasattr(color, 'rgb'):
                        rgb = color.rgb
                        if rgb:
                            colors[attr] = f"#{rgb.hex}"
            except:
                pass
        
        return colors
    
    def _extract_brand_assets(self, presentation: Presentation) -> List[BrandAsset]:
        """Extract potential brand assets like logos that appear consistently"""
        brand_assets = []
        shape_positions = {}  # Track shapes that appear in multiple slides
        
        try:
            # Analyze existing slides for repeated elements
            for slide_idx, slide in enumerate(presentation.slides):
                for shape in slide.shapes:
                    # Look for images or shapes that might be logos
                    if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
                        # Create a position key
                        pos_key = self._get_position_key(shape)
                        if pos_key not in shape_positions:
                            shape_positions[pos_key] = []
                        shape_positions[pos_key].append(slide_idx)
            
            # Identify shapes that appear in multiple slides as potential brand assets
            for pos_key, slide_indices in shape_positions.items():
                if len(slide_indices) >= 2:  # Appears in at least 2 slides
                    # Parse position from key
                    left, top = pos_key.split(',')
                    brand_asset = BrandAsset(
                        type="logo",  # Assume it's a logo if it repeats
                        slide_indices=slide_indices,
                        position={'left': float(left), 'top': float(top)}
                    )
                    brand_assets.append(brand_asset)
        except Exception as e:
            logger.warning(f"Could not extract brand assets: {str(e)}")
        
        return brand_assets
    
    def _get_position_key(self, shape) -> str:
        """Get a position key for a shape (rounded to nearest 0.5 inch)"""
        try:
            left = round(shape.left / Inches(1) * 2) / 2  # Round to nearest 0.5
            top = round(shape.top / Inches(1) * 2) / 2
            return f"{left},{top}"
        except:
            return "0,0"

# Create singleton instance
template_analyzer = TemplateAnalyzer()