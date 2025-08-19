"""
Slide Composer Service
Assembles slides from content and templates
"""

import logging
from typing import List, Dict, Optional, Any, Tuple
from copy import deepcopy
import io
from pathlib import Path
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE_TYPE, PP_PLACEHOLDER
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
        output_path: Path,
        mode: str = "edit"  # "edit" (in-place), "replace" (clear text and rebuild), or "delete" (remove slides)
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
            logger.info(f"Loading template from: {template_path}")
            prs = Presentation(str(template_path))
            logger.info(f"Template loaded: {len(prs.slides)} slides, {len(prs.slide_layouts)} layouts, {len(prs.slide_masters)} masters")
            
            # Pre-capture PICTURE artwork from example slides per layout (before clearing)
            # We avoid raw XML cloning to preserve media relationships.
            picture_art_by_layout: Dict[int, List[Dict[str, Any]]] = {}
            default_picture_art: List[Dict[str, Any]] = []
            default_bg_xml = None
            try:
                slide_layouts_list = list(prs.slide_layouts)
                for s_idx in range(len(prs.slides)):
                    s = prs.slides[s_idx]
                    try:
                        layout_id = slide_layouts_list.index(s.slide_layout)
                    except ValueError:
                        continue
                    pics = []
                    for shp in s.shapes:
                        try:
                            if getattr(shp, "is_placeholder", False):
                                continue
                            # Capture only pictures for reliable cloning
                            if shp.shape_type == MSO_SHAPE_TYPE.PICTURE:
                                # Resolve image blob
                                rId = shp._element.blipFill.blip.rEmbed
                                img_part = s.part.related_parts.get(rId)
                                if img_part is None:
                                    continue
                                blob = img_part.blob
                                pics.append({
                                    "blob": blob,
                                    "left": shp.left,
                                    "top": shp.top,
                                    "width": shp.width,
                                    "height": shp.height,
                                })
                        except Exception:
                            continue
                    if pics and layout_id not in picture_art_by_layout:
                        picture_art_by_layout[layout_id] = pics
                        logger.debug(f"Captured {len(pics)} pictures for layout {layout_id}")

                # Default: take artwork and background from the first template slide
                if len(prs.slides) > 0:
                    first = prs.slides[0]
                    for shp in first.shapes:
                        try:
                            if getattr(shp, "is_placeholder", False):
                                continue
                            if shp.shape_type == MSO_SHAPE_TYPE.PICTURE:
                                rId = shp._element.blipFill.blip.rEmbed
                                img_part = first.part.related_parts.get(rId)
                                if img_part is None:
                                    continue
                                blob = img_part.blob
                                default_picture_art.append({
                                    "blob": blob,
                                    "left": shp.left,
                                    "top": shp.top,
                                    "width": shp.width,
                                    "height": shp.height,
                                })
                        except Exception:
                            continue
                    
                    logger.debug(f"Captured {len(default_picture_art)} default pictures from first slide")
                    
                    try:
                        cSld = first._element.cSld
                        if hasattr(cSld, 'bg') and cSld.bg is not None:
                            default_bg_xml = deepcopy(cSld.bg)
                    except Exception:
                        default_bg_xml = None
            except Exception as _e:
                logger.debug(f"Could not pre-capture background elements: {_e}")

            # Log layout details
            for i in range(min(5, len(prs.slide_layouts))):
                layout = prs.slide_layouts[i]
                logger.debug(f"  Layout {i}: {layout.name} with {len(layout.placeholders)} placeholders")

            # New approach:
            # - replace: clear all slides, then build fresh from layouts (ensures placeholders exist)
            # - edit: compose in-place on existing slides
            template_slide_count = len(prs.slides)
            planned_slide_count = len(slides)
            
            logger.info(f"Mode={mode}: Template has {template_slide_count} slides, plan needs {planned_slide_count} slides")
            
            # Handle delete mode separately
            if mode == "delete":
                # Parse slide numbers to delete from the slides specs
                # For delete mode, slides should contain info about which slides to delete
                slides_to_delete = []
                for slide_spec in slides:
                    # Extract slide numbers from title or content
                    # E.g., "Delete slide 3" or "Remove slides 2-4"
                    import re
                    numbers = re.findall(r'\d+', slide_spec.title + ' '.join(slide_spec.bullets))
                    slides_to_delete.extend([int(n) - 1 for n in numbers])  # Convert to 0-based index
                
                slides_to_delete = sorted(set(slides_to_delete), reverse=True)  # Remove duplicates and sort descending
                
                logger.info(f"Delete mode: Removing slides {slides_to_delete}")
                
                for slide_idx in slides_to_delete:
                    if 0 <= slide_idx < len(prs.slides):
                        try:
                            rId = prs.slides._sldIdLst[slide_idx].rId
                            prs.part.drop_rel(rId)
                            del prs.slides._sldIdLst[slide_idx]
                            logger.info(f"Deleted slide {slide_idx + 1}")
                        except Exception as e:
                            logger.warning(f"Could not delete slide {slide_idx + 1}: {e}")
                
                # Save and return
                logger.info(f"Saving presentation after deletion with {len(prs.slides)} remaining slides")
                prs.save(str(output_path))
                return [SlideComposition(
                    slide_index=0,
                    success=True,
                    issues=[f"Deleted {len(slides_to_delete)} slides"]
                )]
            
            # Step 1: For replace mode, add new slides from layouts first
            if mode == "replace":
                logger.info(f"Replace mode: adding {planned_slide_count} new slides from layouts")
                # Add new slides first, then remove old ones
                # This ensures clean placeholders and proper formatting
                 
            # Step 1b (edit): If we need more slides than template has, duplicate an existing content slide
            elif mode == "edit" and planned_slide_count > template_slide_count:
                logger.info(f"Need to add {planned_slide_count - template_slide_count} slides")
                slides_to_add = planned_slide_count - template_slide_count
                
                # Find the best content slide to use as template (skip title slide)
                best_content_slide_idx = 1 if template_slide_count > 1 else 0
                
                # Look for a slide with both title and content placeholders
                for idx in range(1, min(template_slide_count, 5)):
                    slide = prs.slides[idx]
                    has_title = False
                    has_content = False
                    for shape in slide.shapes:
                        if hasattr(shape, 'is_placeholder') and shape.is_placeholder:
                            if shape.placeholder_format.type == PP_PLACEHOLDER.TITLE:
                                has_title = True
                            elif shape.placeholder_format.type in [PP_PLACEHOLDER.BODY, PP_PLACEHOLDER.OBJECT]:
                                has_content = True
                    if has_title and has_content:
                        best_content_slide_idx = idx
                        logger.debug(f"Found ideal content slide at index {idx} for duplication")
                        break
                
                for i in range(slides_to_add):
                    # Use the best content slide as template
                    source_slide = prs.slides[best_content_slide_idx]
                    
                    # Add a new slide with the same layout
                    new_slide = prs.slides.add_slide(source_slide.slide_layout)
                    
                    # Copy ALL non-placeholder shapes to preserve template design
                    for shape in source_slide.shapes:
                        try:
                            # Skip placeholders - we want them empty for new content
                            if hasattr(shape, 'is_placeholder') and shape.is_placeholder:
                                continue
                            
                            # Copy pictures (logos, backgrounds, etc.)
                            if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
                                try:
                                    rId = shape._element.blipFill.blip.rEmbed
                                    img_part = source_slide.part.related_parts.get(rId)
                                    if img_part:
                                        stream = io.BytesIO(img_part.blob)
                                        new_slide.shapes.add_picture(
                                            stream, 
                                            shape.left, 
                                            shape.top, 
                                            shape.width, 
                                            shape.height
                                        )
                                        logger.debug(f"Copied picture to new slide")
                                except Exception as e:
                                    logger.debug(f"Could not copy picture: {e}")
                            
                            # Copy text boxes that aren't placeholders (e.g., footer text, copyright)
                            elif hasattr(shape, 'text_frame') and shape.text and not shape.is_placeholder:
                                try:
                                    # This might be footer text or other template elements
                                    new_shape = new_slide.shapes.add_textbox(
                                        shape.left, shape.top, shape.width, shape.height
                                    )
                                    new_shape.text = shape.text
                                    logger.debug(f"Copied non-placeholder text: {shape.text[:30]}")
                                except Exception as e:
                                    logger.debug(f"Could not copy text box: {e}")
                                    
                        except Exception as e:
                            logger.debug(f"Could not copy shape: {e}")
                    
                    logger.info(f"Added slide {template_slide_count + i} using slide {best_content_slide_idx} as template")
            
            compositions = []
            placements = []  # Track placements for 3-pass render
            slide_index_map = {}  # Map slide indices to metadata
            
            # Step 2: Build slides
            for idx, (slide_spec, mapping) in enumerate(zip(slides, mappings)):
                if mode == "replace":
                    # For replace mode: duplicate existing template slide then clear and fill content
                    # This preserves the exact background and design
                    # For first slide, always use slide 0; for others, use appropriate content slides
                    if idx == 0:
                        template_slide_idx = 0  # Always use first template slide for first generated slide
                    else:
                        # For content slides, cycle through slides 1+ to get variety
                        template_slide_idx = 1 + ((idx - 1) % max(1, template_slide_count - 1))
                    
                    source_slide = prs.slides[template_slide_idx]
                    
                    # Add a new slide with the same layout as the source
                    new_slide = prs.slides.add_slide(source_slide.slide_layout)
                    
                    # Copy ALL shapes from source slide (including backgrounds, artwork)
                    for shape in source_slide.shapes:
                        try:
                            # Skip placeholders - we'll fill these with new content
                            if hasattr(shape, 'is_placeholder') and shape.is_placeholder:
                                continue
                                
                            # Copy non-placeholder shapes (artwork, backgrounds, logos)
                            if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
                                # Copy pictures
                                rId = shape._element.blipFill.blip.rEmbed
                                img_part = source_slide.part.related_parts.get(rId)
                                if img_part:
                                    stream = io.BytesIO(img_part.blob)
                                    new_slide.shapes.add_picture(
                                        stream, shape.left, shape.top, shape.width, shape.height
                                    )
                            elif hasattr(shape, 'text_frame') and not shape.is_placeholder:
                                # Copy non-placeholder text (footers, etc.)
                                new_shape = new_slide.shapes.add_textbox(
                                    shape.left, shape.top, shape.width, shape.height
                                )
                                new_shape.text = shape.text
                        except Exception as e:
                            logger.debug(f"Could not copy shape: {e}")
                    
                    logger.info(f"Duplicated slide {template_slide_idx} as new slide {idx}")
                    
                    # Now compose content on this duplicated slide
                    composition = self._compose_on_existing_slide(
                        prs, len(prs.slides) - 1, slide_spec, mapping, template_profile
                    )
                else:
                    # Edit mode: use existing slides when available
                    if idx < len(prs.slides):
                        composition = self._compose_on_existing_slide(
                            prs, idx, slide_spec, mapping, template_profile
                        )
                    else:
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
            
            # Step 3: For replace mode, remove original template slides (keep only duplicated ones)
            if mode == "replace":
                # Remove original template slides from the beginning
                original_slide_count = template_slide_count
                logger.info(f"Removing {original_slide_count} original template slides")
                for i in range(original_slide_count):
                    try:
                        # Always remove the first slide (indices shift as we delete)
                        rId = prs.slides._sldIdLst[0].rId
                        prs.part.drop_rel(rId)
                        del prs.slides._sldIdLst[0]
                        logger.debug(f"Removed original slide, {len(prs.slides)} slides remain")
                    except Exception as e:
                        logger.warning(f"Could not remove original slide: {e}")
                        break
            
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
            logger.info(f"Saving presentation with {len(prs.slides)} slides to {output_path}")
            prs.save(str(output_path))
            logger.info(f"Presentation saved successfully, file size: {output_path.stat().st_size / 1024 / 1024:.2f} MB")
            
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
            logger.debug(f"Composing slide '{slide_spec.title}' with layout {mapping.layout_id} ({mapping.layout_name})")
            layout = presentation.slide_layouts[mapping.layout_id]
            logger.debug(f"  Layout has {len(layout.placeholders)} placeholders")
            slide = presentation.slides.add_slide(layout)
            logger.debug(f"  Slide added, now has {len(slide.shapes)} shapes")
            
            # Ensure the slide inherits master slide background
            try:
                # Check if slide has proper background
                if hasattr(slide.background, 'fill'):
                    logger.debug(f"  Slide background type: {slide.background.fill.type}")
                    
                    # If slide background is not set properly, try to inherit from master
                    if slide.background.fill.type == 1:  # SOLID but might be default white
                        master = presentation.slide_masters[0]
                        if hasattr(master.background, 'fill'):
                            logger.debug(f"  Master background type: {master.background.fill.type}")
                            # Try to copy master background properties
                            try:
                                if hasattr(master.background.fill, 'fore_color'):
                                    slide.background.fill.solid()
                                    slide.background.fill.fore_color.rgb = master.background.fill.fore_color.rgb
                                    logger.debug("  Copied master background color to slide")
                            except Exception as e:
                                logger.debug(f"  Could not copy master background: {e}")
            except Exception as e:
                logger.debug(f"  Could not check slide background: {e}")
            
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
            logger.debug(f"  Filling placeholders for slide '{slide_spec.title}'")
            self._fill_title(slide, slide_spec, layout_sig, template_profile.theme)
            overflow = self._fill_content(slide, slide_spec, layout_sig, template_profile.theme)
            logger.debug(f"  Placeholders filled, overflow: {overflow is not None}")
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

    def _clear_slide_text(self, slide) -> None:
        """Remove text content from shapes while preserving placeholders and their structure."""
        cleared_count = 0
        try:
            for shape in slide.shapes:
                try:
                    # Only clear text content, don't clear the text_frame structure
                    if hasattr(shape, 'text_frame') and shape.text_frame:
                        # Clear paragraphs but keep the text_frame
                        for paragraph in shape.text_frame.paragraphs:
                            paragraph.text = ""
                        cleared_count += 1
                    elif hasattr(shape, 'text'):
                        # Clear direct text property
                        shape.text = ""
                        cleared_count += 1
                except Exception as e:
                    logger.debug(f"Could not clear text from shape: {e}")
                    continue
            logger.info(f"Cleared text from {cleared_count} shapes on slide (preserving placeholders)")
        except Exception as e:
            logger.warning(f"Error clearing slide text: {e}")

    def _compose_on_existing_slide(
        self,
        presentation: Presentation,
        slide_index: int,
        slide_spec: SlideSpec,
        mapping: SlideMapping,
        template_profile: TemplateProfile
    ) -> SlideComposition:
        """Fill content into an existing template slide without changing its layout.
        This preserves original artwork/background present on that slide.
        """
        issues: List[str] = []
        overflow_text: Optional[str] = None
        try:
            slide = presentation.slides[slide_index]
            # Clear all existing text content on the slide (placeholders and free text boxes)
            self._clear_slide_text(slide)
            layout_sig = template_profile.get_layout_by_id(mapping.layout_id) or template_profile.get_layout_by_id(0)
            if not layout_sig:
                layout_sig = SlideLayoutSignature(layout_id=0, name="Unknown", placeholders=[])
            logger.debug(f"Composing IN-PLACE on slide {slide_index} using mapping {mapping.layout_id} ({mapping.layout_name})")
            # Fill title/body based on placeholder matching by idx
            self._fill_title(slide, slide_spec, layout_sig, template_profile.theme)
            overflow = self._fill_content(slide, slide_spec, layout_sig, template_profile.theme)
            if overflow:
                overflow_text = overflow
                issues.append("Content overflow detected")
            # Notes
            if slide_spec.speaker_notes:
                slide.notes_slide.notes_text_frame.text = slide_spec.speaker_notes
            return SlideComposition(
                slide_spec_id=slide_spec.slide_id,
                layout_id=mapping.layout_id,
                success=True,
                issues=issues,
                overflow_text=overflow_text,
                missing_placeholders=[]
            )
        except Exception as e:
            logger.error(f"Error composing existing slide {slide_index}: {str(e)}")
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
        
        # Log available placeholders for debugging
        logger.info(f"Looking for title placeholder. Slide has {len(slide.placeholders)} placeholders")
        for idx, ph in enumerate(slide.placeholders):
            try:
                if hasattr(ph, 'placeholder_format') and ph.placeholder_format:
                    logger.info(f"  Placeholder {idx}: type={ph.placeholder_format.type}, idx={ph.placeholder_format.idx}")
            except:
                pass
        
        # 1) First try to find TITLE placeholder by type
        for ph in slide.placeholders:
            try:
                if hasattr(ph, 'placeholder_format') and ph.placeholder_format:
                    # Check for title types (PP_PLACEHOLDER.TITLE = 0, CENTER_TITLE = 3)
                    if ph.placeholder_format.type in [PP_PLACEHOLDER.TITLE, PP_PLACEHOLDER.CENTER_TITLE]:
                        title_placeholder = ph
                        logger.debug(f"Found title placeholder by type: {ph.placeholder_format.type}")
                        break
            except Exception as e:
                logger.debug(f"Error checking placeholder: {e}")
                continue
                
        # 2) Fallback to first placeholder with idx=0 (usually title)
        if not title_placeholder:
            for ph in slide.placeholders:
                try:
                    if hasattr(ph, 'placeholder_format') and ph.placeholder_format and ph.placeholder_format.idx == 0:
                        title_placeholder = ph
                        logger.debug("Found title placeholder by idx=0")
                        break
                except Exception:
                    continue
                    
        # 3) Fallback to any shape with text_frame (for templates without placeholders)
        if not title_placeholder:
            for sh in slide.shapes:
                if hasattr(sh, 'text_frame') and sh.text_frame:
                    # Use the first text shape we find
                    title_placeholder = sh
                    logger.info("Using first text shape for title (no placeholders found)")
                    break
        
        if not title_placeholder:
            logger.warning(f"No title placeholder found on slide")
        elif not slide_spec.title:
            logger.warning(f"No title text provided for slide")
        else:
            logger.info(f"Filling title: '{slide_spec.title}'")
            # Preserve template formatting by updating text through text_frame
            if hasattr(title_placeholder, 'text_frame'):
                text_frame = title_placeholder.text_frame
                # Clear existing text while preserving formatting
                text_frame.clear()
                # Add new paragraph with template's default formatting
                p = text_frame.paragraphs[0] if text_frame.paragraphs else text_frame.add_paragraph()
                p.text = slide_spec.title
                
                # Apply template theme font and ensure good contrast
                if theme and theme.font_scheme:
                    # Title uses major font
                    if 'major' in theme.font_scheme and p.runs:
                        for run in p.runs:
                            run.font.name = theme.font_scheme['major']
                            if theme.default_font_size and theme.default_font_size > 24:
                                run.font.size = Pt(theme.default_font_size)
                            # Ensure white text for good contrast on dark backgrounds
                            run.font.color.rgb = RGBColor(255, 255, 255)
            else:
                # Fallback if no text_frame
                title_placeholder.text = slide_spec.title
    
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
        
        logger.info(f"Filling content with {len(slide_spec.bullets)} bullets: {slide_spec.bullets[:2]}...")
        
        # Find content placeholders
        content_placeholders = []
        # 1) Match by idx
        for ph in slide.placeholders:
            try:
                if hasattr(ph, 'placeholder_format'):
                    for layout_ph in layout_sig.placeholders:
                        if layout_ph.type in [PlaceholderType.BODY, PlaceholderType.CONTENT] and layout_ph.idx == ph.placeholder_format.idx:
                            content_placeholders.append(ph)
                            break
            except Exception:
                continue
        # 2) Fallback to any BODY placeholder(s)
        if not content_placeholders:
            for ph in slide.placeholders:
                try:
                    if (
                        hasattr(ph, 'placeholder_format')
                        and ph.placeholder_format
                        and ph.placeholder_format.type in (
                            PP_PLACEHOLDER.BODY,
                            PP_PLACEHOLDER.OBJECT,
                            PP_PLACEHOLDER.VERTICAL_BODY,
                            PP_PLACEHOLDER.VERTICAL_OBJECT,
                        )
                    ):
                        content_placeholders.append(ph)
                except Exception:
                    continue
        
        if not content_placeholders:
            # No content placeholders, try to use any text shapes (skip the first one which is likely title)
            text_shapes = []
            for shape in slide.shapes:
                if hasattr(shape, 'text_frame') and shape.text_frame:
                    text_shapes.append(shape)
            
            # Use shapes after the first one for content (first is likely title)
            if len(text_shapes) > 1:
                content_placeholders.extend(text_shapes[1:])
                logger.info(f"Using {len(text_shapes)-1} text shapes for content (no placeholders found)")
            elif len(text_shapes) == 1:
                # Only one text shape, use it for both title and content
                content_placeholders.append(text_shapes[0])
                logger.info("Using single text shape for content")
        
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
            
            # Preserve template formatting
            if hasattr(placeholder, 'text_frame'):
                text_frame = placeholder.text_frame
                # Clear while preserving formatting
                text_frame.clear()
            else:
                text_frame = None
            
            # Add bullets
            bullets_to_add = slide_spec.bullets[
                bullet_index:bullet_index + bullets_per_placeholder
            ]
            
            # Check for overflow
            if len(bullets_to_add) > self.max_bullets_per_placeholder:
                overflow_bullets.extend(bullets_to_add[self.max_bullets_per_placeholder:])
                bullets_to_add = bullets_to_add[:self.max_bullets_per_placeholder]
            
            if text_frame is not None:
                # Add bullets as paragraphs to preserve formatting
                for i, bullet in enumerate(bullets_to_add):
                    if i == 0 and text_frame.paragraphs:
                        p = text_frame.paragraphs[0]
                    else:
                        p = text_frame.add_paragraph()
                    p.text = f"• {bullet}"
                    p.level = 0
                    if theme and theme.font_scheme and 'minor' in theme.font_scheme and p.runs:
                        for run in p.runs:
                            run.font.name = theme.font_scheme['minor']
                            if theme.default_font_size and theme.default_font_size <= 24:
                                run.font.size = Pt(theme.default_font_size)
                            # Ensure white text for good contrast on dark backgrounds
                            run.font.color.rgb = RGBColor(255, 255, 255)
            else:
                placeholder.text = "\n".join(f"• {b}" for b in bullets_to_add)
            
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
        """Preserve original template theme; no overrides here."""
        return
    
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