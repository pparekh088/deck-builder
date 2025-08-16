"""
Slide Composer Service
Assembles slides from content and templates
"""

import logging
from typing import List, Dict, Optional, Any, Tuple
from pathlib import Path
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.dml.color import RGBColor
from pptx.chart.data import ChartData
from pptx.enum.chart import XL_CHART_TYPE

from app.models import (
    SlideSpec, SlideMapping, TemplateProfile, SlideComposition,
    PlaceholderType, PlaceholderInfo, ThemeInfo
)

# Import render measure service
from .render_measure import create_render_measure_service
from ..config import settings

logger = logging.getLogger(__name__)

class SlideComposer:
    """Composes PowerPoint slides using template layouts and content"""
    
    def __init__(self):
        self.max_bullets_per_placeholder = 10
        self.default_font_size = 18
        self.title_font_size = 32
    
    def compose_presentation(
        self,
        slides: List[SlideSpec],
        mappings: List[SlideMapping],
        template_profile: TemplateProfile,
        template_path: Path,
        output_path: Path
    ) -> List[SlideComposition]:
        """
        Compose a complete presentation from slide specifications
        
        Args:
            slides: List of slide specifications
            mappings: Corresponding layout mappings
            template_profile: Template profile with layout info
            template_path: Path to template file
            output_path: Path to save output presentation
            
        Returns:
            List of SlideComposition results
        """
        try:
            # Load template presentation
            prs = Presentation(str(template_path))
            
            # Clear existing slides (keep only template)
            while len(prs.slides) > 0:
                rId = prs.slides._sldIdLst[0].rId
                prs.slides._sldIdLst.remove(prs.slides._sldIdLst[0])
                del prs.slides._slideLayouts._slideLayouts[rId]
            
            compositions = []
            placements = []  # Track placements for 3-pass render
            slide_index_map = {}  # Map slide indices to metadata
            
            # Create slides based on mappings
            for idx, (slide_spec, mapping) in enumerate(zip(slides, mappings)):
                composition = self._compose_slide(
                    prs, slide_spec, mapping, template_profile
                )
                compositions.append(composition)
                
                # Track placement info for measurement
                if composition.success:
                    # Get content mapping if available
                    content_mapping = getattr(mapping, 'content_mapping', {})
                    
                    for content_id, shape_id in content_mapping.items():
                        placements.append({
                            "slide_index": idx,
                            "content_id": content_id,
                            "shape_id": shape_id,
                            "slide_spec_id": slide_spec.slide_id
                        })
                    
                    slide_index_map[idx] = {
                        "slide_spec_id": slide_spec.slide_id,
                        "layout_id": mapping.layout_id,
                        "layout_name": mapping.layout_name
                    }
            
            # Perform 3-pass rendering if enabled
            if settings.RENDER_MEASURE_ENABLED and placements:
                logger.info("Starting 3-pass render with measurement")
                render_service = create_render_measure_service()
                render_report = render_service.three_pass_render(
                    prs,
                    placements,
                    slide_index_map,
                    output_path=None  # Will save at the end
                )
                
                # Update compositions with render corrections
                if render_report.get("status") == "success":
                    corrections = render_report.get("corrections", [])
                    for correction in corrections:
                        slide_idx = correction.get("slide_index")
                        if 0 <= slide_idx < len(compositions):
                            comp = compositions[slide_idx]
                            if correction["type"] == "font_resize":
                                comp.issues.append(
                                    f"Font reduced from {correction['old_size']} to {correction['new_size']}pt"
                                )
                            elif correction["type"] == "slide_split":
                                comp.issues.append(
                                    f"Content split to continuation slide {correction['continuation_slide']}"
                                )
                    
                    logger.info(f"3-pass render complete: {len(corrections)} corrections made")
            
            # Save presentation
            prs.save(str(output_path))
            logger.info(f"Presentation saved to {output_path}")
            
            return compositions
            
        except Exception as e:
            logger.error(f"Error composing presentation: {str(e)}")
            raise
    
    def _compose_slide(
        self,
        presentation: Presentation,
        slide_spec: SlideSpec,
        mapping: SlideMapping,
        template_profile: TemplateProfile
    ) -> SlideComposition:
        """Compose a single slide"""
        
        issues = []
        overflow_text = None
        missing_placeholders = []
        
        try:
            # Get the layout
            layout = presentation.slide_layouts[mapping.layout_id]
            slide = presentation.slides.add_slide(layout)
            
            # Get layout signature for placeholder info
            layout_sig = template_profile.get_layout_by_id(mapping.layout_id)
            
            if not layout_sig:
                issues.append(f"Layout {mapping.layout_id} not found in profile")
                return SlideComposition(
                    slide_spec_id=slide_spec.slide_id,
                    layout_id=mapping.layout_id,
                    success=False,
                    issues=issues
                )
            
            # Fill placeholders
            self._fill_title(slide, slide_spec, layout_sig, template_profile.theme)
            overflow = self._fill_content(slide, slide_spec, layout_sig, template_profile.theme)
            if overflow:
                overflow_text = overflow
                issues.append("Content overflow detected")
            
            # Add visual elements if needed
            if slide_spec.needs.has_picture:
                self._add_picture(slide, layout_sig)
            
            if slide_spec.needs.has_table:
                self._add_table(slide, slide_spec.needs.has_table, layout_sig)
            
            if slide_spec.needs.has_chart:
                self._add_chart(slide, slide_spec.needs.has_chart, layout_sig)
            
            # Add speaker notes
            if slide_spec.speaker_notes:
                slide.notes_slide.notes_text_frame.text = slide_spec.speaker_notes
            
            # Apply theme
            self._apply_theme(slide, template_profile.theme)
            
            return SlideComposition(
                slide_spec_id=slide_spec.slide_id,
                layout_id=mapping.layout_id,
                success=True,
                issues=issues,
                overflow_text=overflow_text,
                missing_placeholders=missing_placeholders
            )
            
        except Exception as e:
            logger.error(f"Error composing slide {slide_spec.slide_id}: {str(e)}")
            issues.append(f"Composition error: {str(e)}")
            return SlideComposition(
                slide_spec_id=slide_spec.slide_id,
                layout_id=mapping.layout_id,
                success=False,
                issues=issues
            )
    
    def _fill_title(
        self,
        slide,
        slide_spec: SlideSpec,
        layout_sig,
        theme: ThemeInfo
    ):
        """Fill title placeholder"""
        
        # Find title placeholder
        title_placeholder = None
        for placeholder in slide.placeholders:
            try:
                if hasattr(placeholder, 'placeholder_format'):
                    # Check if it's a title placeholder
                    for layout_ph in layout_sig.placeholders:
                        if (layout_ph.type == PlaceholderType.TITLE and 
                            layout_ph.idx == placeholder.placeholder_format.idx):
                            title_placeholder = placeholder
                            break
                if title_placeholder:
                    break
            except:
                continue
        
        if title_placeholder and slide_spec.title:
            title_placeholder.text = slide_spec.title
            
            # Apply title formatting
            if hasattr(title_placeholder, 'text_frame'):
                for paragraph in title_placeholder.text_frame.paragraphs:
                    paragraph.alignment = PP_ALIGN.CENTER
                    if paragraph.font:
                        paragraph.font.size = Pt(self.title_font_size)
                        if 'major' in theme.font_scheme:
                            paragraph.font.name = theme.font_scheme['major']
    
    def _fill_content(
        self,
        slide,
        slide_spec: SlideSpec,
        layout_sig,
        theme: ThemeInfo
    ) -> Optional[str]:
        """Fill content/body placeholders, return overflow text if any"""
        
        if not slide_spec.bullets:
            return None
        
        # Find content placeholders
        content_placeholders = []
        for placeholder in slide.placeholders:
            try:
                if hasattr(placeholder, 'placeholder_format'):
                    for layout_ph in layout_sig.placeholders:
                        if (layout_ph.type in [PlaceholderType.BODY, PlaceholderType.CONTENT] and
                            layout_ph.idx == placeholder.placeholder_format.idx):
                            content_placeholders.append(placeholder)
                            break
            except:
                continue
        
        if not content_placeholders:
            # No content placeholders, try to use any text placeholder
            for placeholder in slide.placeholders:
                if hasattr(placeholder, 'text_frame'):
                    content_placeholders.append(placeholder)
                    break
        
        if not content_placeholders:
            return "\n".join(slide_spec.bullets)  # Return all as overflow
        
        # Distribute bullets across placeholders
        bullets_per_placeholder = len(slide_spec.bullets) // len(content_placeholders)
        if bullets_per_placeholder == 0:
            bullets_per_placeholder = len(slide_spec.bullets)
        
        overflow_bullets = []
        bullet_index = 0
        
        for placeholder in content_placeholders:
            if bullet_index >= len(slide_spec.bullets):
                break
            
            # Clear existing text
            placeholder.text = ""
            
            # Add bullets
            bullets_to_add = slide_spec.bullets[
                bullet_index:bullet_index + bullets_per_placeholder
            ]
            
            # Check for overflow
            if len(bullets_to_add) > self.max_bullets_per_placeholder:
                overflow_bullets.extend(bullets_to_add[self.max_bullets_per_placeholder:])
                bullets_to_add = bullets_to_add[:self.max_bullets_per_placeholder]
            
            # Add bullets to placeholder
            for i, bullet in enumerate(bullets_to_add):
                if i == 0:
                    placeholder.text = f"• {bullet}"
                else:
                    placeholder.text += f"\n• {bullet}"
            
            # Apply formatting
            if hasattr(placeholder, 'text_frame'):
                for paragraph in placeholder.text_frame.paragraphs:
                    paragraph.alignment = PP_ALIGN.LEFT
                    if paragraph.font:
                        paragraph.font.size = Pt(theme.default_font_size or self.default_font_size)
                        if 'minor' in theme.font_scheme:
                            paragraph.font.name = theme.font_scheme['minor']
            
            bullet_index += len(bullets_to_add)
        
        # Check for remaining bullets
        if bullet_index < len(slide_spec.bullets):
            overflow_bullets.extend(slide_spec.bullets[bullet_index:])
        
        if overflow_bullets:
            return "\n".join(overflow_bullets)
        
        return None
    
    def _add_picture(self, slide, layout_sig):
        """Add picture placeholder or shape"""
        
        # Find picture placeholder
        picture_placeholder = None
        for placeholder in slide.placeholders:
            try:
                if hasattr(placeholder, 'placeholder_format'):
                    for layout_ph in layout_sig.placeholders:
                        if (layout_ph.type == PlaceholderType.PICTURE and
                            layout_ph.idx == placeholder.placeholder_format.idx):
                            picture_placeholder = placeholder
                            break
                if picture_placeholder:
                    break
            except:
                continue
        
        if picture_placeholder:
            # For now, just add a placeholder shape
            # In production, you'd insert an actual image here
            try:
                # Add a rectangle as placeholder for image
                left = Inches(5)
                top = Inches(2)
                width = Inches(3)
                height = Inches(2)
                
                shape = slide.shapes.add_shape(
                    MSO_SHAPE_TYPE.RECTANGLE,
                    left, top, width, height
                )
                shape.fill.solid()
                shape.fill.fore_color.rgb = RGBColor(200, 200, 200)
                shape.text = "[Image Placeholder]"
            except:
                pass
    
    def _add_table(self, slide, table_spec: Dict[str, Any], layout_sig):
        """Add table to slide"""
        
        if not table_spec:
            return
        
        try:
            rows = table_spec.get('rows', 3)
            cols = table_spec.get('cols', 2)
            headers = table_spec.get('headers', [f"Column {i+1}" for i in range(cols)])
            
            # Find suitable placeholder or add as shape
            left = Inches(1)
            top = Inches(2)
            width = Inches(8)
            height = Inches(3)
            
            table = slide.shapes.add_table(rows, cols, left, top, width, height).table
            
            # Add headers
            for col_idx, header in enumerate(headers[:cols]):
                table.cell(0, col_idx).text = header
            
            # Add sample data
            for row_idx in range(1, rows):
                for col_idx in range(cols):
                    table.cell(row_idx, col_idx).text = f"Data {row_idx},{col_idx}"
        except Exception as e:
            logger.warning(f"Could not add table: {str(e)}")
    
    def _add_chart(self, slide, chart_spec: Dict[str, Any], layout_sig):
        """Add chart to slide"""
        
        if not chart_spec:
            return
        
        try:
            chart_type = chart_spec.get('type', 'bar')
            
            # Create chart data
            chart_data = ChartData()
            chart_data.categories = chart_spec.get('categories', ['Cat1', 'Cat2', 'Cat3'])
            
            series_data = chart_spec.get('series', [
                ('Series 1', (1, 2, 3))
            ])
            
            for series_name, values in series_data:
                chart_data.add_series(series_name, values)
            
            # Add chart
            left = Inches(1)
            top = Inches(2)
            width = Inches(8)
            height = Inches(4)
            
            chart_type_map = {
                'bar': XL_CHART_TYPE.BAR_CLUSTERED,
                'column': XL_CHART_TYPE.COLUMN_CLUSTERED,
                'line': XL_CHART_TYPE.LINE,
                'pie': XL_CHART_TYPE.PIE
            }
            
            xl_chart_type = chart_type_map.get(chart_type, XL_CHART_TYPE.BAR_CLUSTERED)
            
            chart = slide.shapes.add_chart(
                xl_chart_type, left, top, width, height, chart_data
            ).chart
            
        except Exception as e:
            logger.warning(f"Could not add chart: {str(e)}")
    
    def _apply_theme(self, slide, theme: ThemeInfo):
        """Apply theme colors and fonts to slide"""
        
        # This is a simplified version - full theme application would be more complex
        try:
            # Apply fonts to all text
            for shape in slide.shapes:
                if hasattr(shape, 'text_frame'):
                    for paragraph in shape.text_frame.paragraphs:
                        if paragraph.font:
                            # Use major font for titles, minor for body
                            if shape.shape_type == MSO_SHAPE_TYPE.PLACEHOLDER:
                                if 'title' in shape.name.lower():
                                    if 'major' in theme.font_scheme:
                                        paragraph.font.name = theme.font_scheme['major']
                                else:
                                    if 'minor' in theme.font_scheme:
                                        paragraph.font.name = theme.font_scheme['minor']
        except Exception as e:
            logger.warning(f"Could not fully apply theme: {str(e)}")
    
    def update_slide(
        self,
        presentation_path: Path,
        slide_number: int,
        slide_spec: SlideSpec,
        new_layout_id: Optional[int] = None
    ) -> SlideComposition:
        """
        Update a single slide in an existing presentation
        
        Args:
            presentation_path: Path to presentation file
            slide_number: 1-based slide number to update
            slide_spec: New slide specification
            new_layout_id: Optional new layout to use
            
        Returns:
            SlideComposition result
        """
        try:
            prs = Presentation(str(presentation_path))
            
            if slide_number < 1 or slide_number > len(prs.slides):
                return SlideComposition(
                    slide_spec_id=slide_spec.slide_id,
                    layout_id=-1,
                    success=False,
                    issues=[f"Invalid slide number: {slide_number}"]
                )
            
            # Get the slide (0-indexed)
            slide = prs.slides[slide_number - 1]
            
            # If new layout specified, recreate slide with new layout
            if new_layout_id is not None:
                # This would require recreating the slide with new layout
                # For now, just update content in existing layout
                pass
            
            # Clear and refill content
            # (Simplified - in production would preserve more formatting)
            for placeholder in slide.placeholders:
                if hasattr(placeholder, 'text'):
                    placeholder.text = ""
            
            # Refill with new content
            # (Would use full _compose_slide logic here)
            
            # Save
            prs.save(str(presentation_path))
            
            return SlideComposition(
                slide_spec_id=slide_spec.slide_id,
                layout_id=new_layout_id or 0,
                success=True
            )
            
        except Exception as e:
            logger.error(f"Error updating slide: {str(e)}")
            return SlideComposition(
                slide_spec_id=slide_spec.slide_id,
                layout_id=-1,
                success=False,
                issues=[str(e)]
            )

# Create singleton instance
slide_composer = SlideComposer()