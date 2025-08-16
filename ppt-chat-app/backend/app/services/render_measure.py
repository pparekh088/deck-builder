"""
3-pass rendering service with measurement and overflow correction
"""

import logging
import tempfile
import os
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from pptx import Presentation
from pptx.util import Pt
from pptx.enum.text import PP_PARAGRAPH_ALIGNMENT
import copy

from ..utils.pdf_render import (
    pptx_to_pdf_bytes,
    pdf_text_boxes,
    estimate_text_overflow,
    convert_pdf_bbox_to_px
)
from ..utils.geometry import emu_to_px, px_to_emu
from ..config import settings

logger = logging.getLogger(__name__)


class RenderMeasureService:
    """Service for 3-pass rendering with measurement and overflow correction"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the render measure service
        
        Args:
            config: Optional configuration overrides
        """
        self.config = config or {}
        self.min_font_size = self.config.get('min_font_size', settings.MIN_FONT_SIZE)
        self.max_font_size = self.config.get('max_font_size', settings.MAX_FONT_SIZE)
        self.overflow_threshold = self.config.get('overflow_threshold', settings.OVERFLOW_THRESHOLD)
        self.libreoffice_path = self.config.get('libreoffice_path', settings.LIBREOFFICE_PATH)
        self.pdf_dpi = self.config.get('pdf_dpi', settings.PDF_RASTER_DPI)
    
    def three_pass_render(
        self,
        prs: Presentation,
        placements: List[Dict[str, Any]],
        slide_index_map: Dict[int, Any],
        output_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Perform 3-pass rendering with measurement and correction
        
        Pass 1: Initial render (already done)
        Pass 2: Measure via PDF export
        Pass 3: Fix overflows and re-render
        
        Args:
            prs: PowerPoint presentation object
            placements: List of content placements with slide/shape info
            slide_index_map: Mapping of slide indices to metadata
            output_path: Optional path to save corrected presentation
        
        Returns:
            Report dictionary with corrections made
        """
        if not settings.RENDER_MEASURE_ENABLED:
            logger.info("Render measurement disabled, skipping 3-pass render")
            return {"status": "skipped", "reason": "disabled"}
        
        report = {
            "status": "success",
            "passes": [],
            "corrections": [],
            "slides_split": [],
            "fonts_adjusted": []
        }
        
        try:
            # Pass 1: Initial render (assume already done)
            report["passes"].append({
                "pass": 1,
                "action": "initial_render",
                "placements": len(placements)
            })
            
            # Pass 2: Measure via PDF
            measurements = self._measure_pass(prs, placements)
            report["passes"].append({
                "pass": 2,
                "action": "measure",
                "overflows_detected": len(measurements["overflows"])
            })
            
            if not measurements["overflows"]:
                logger.info("No overflows detected, skipping correction pass")
                return report
            
            # Pass 3: Fix overflows
            corrections = self._correction_pass(prs, measurements["overflows"], placements)
            report["passes"].append({
                "pass": 3,
                "action": "correct",
                "corrections_made": len(corrections)
            })
            
            report["corrections"] = corrections
            report["fonts_adjusted"] = [c for c in corrections if c["type"] == "font_resize"]
            report["slides_split"] = [c for c in corrections if c["type"] == "slide_split"]
            
            # Save corrected presentation if path provided
            if output_path:
                prs.save(output_path)
                report["output_path"] = output_path
            
            return report
            
        except Exception as e:
            logger.error(f"Three-pass render failed: {e}")
            report["status"] = "error"
            report["error"] = str(e)
            return report
    
    def _measure_pass(
        self,
        prs: Presentation,
        placements: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Measure text overflow via PDF export
        
        Args:
            prs: PowerPoint presentation
            placements: List of placements to check
        
        Returns:
            Measurement results with overflow information
        """
        measurements = {
            "overflows": [],
            "slide_measurements": {}
        }
        
        try:
            # Save presentation to temp file
            with tempfile.NamedTemporaryFile(suffix='.pptx', delete=False) as tmp:
                tmp_path = tmp.name
                prs.save(tmp_path)
            
            # Convert to PDF
            pdf_bytes = pptx_to_pdf_bytes(tmp_path, self.libreoffice_path)
            
            # Clean up temp file
            os.unlink(tmp_path)
            
            # Analyze each slide
            for slide_idx, slide in enumerate(prs.slides):
                # Extract text boxes from PDF
                text_boxes, page_size = pdf_text_boxes(pdf_bytes, slide_idx)
                
                if not text_boxes:
                    continue
                
                # Find placements for this slide
                slide_placements = [
                    p for p in placements 
                    if p.get("slide_index") == slide_idx
                ]
                
                slide_measurements = {
                    "slide_index": slide_idx,
                    "text_boxes": len(text_boxes),
                    "shape_overflows": []
                }
                
                # Check each placement for overflow
                for placement in slide_placements:
                    shape_id = placement.get("shape_id")
                    if not shape_id:
                        continue
                    
                    # Find the shape in the slide
                    shape = self._find_shape_by_id(slide, shape_id)
                    if not shape or not hasattr(shape, 'text_frame'):
                        continue
                    
                    # Get shape bbox in PDF coordinates
                    shape_bbox = self._get_shape_bbox_pts(shape)
                    
                    # Estimate overflow
                    overflow_ratio = estimate_text_overflow(
                        shape_bbox,
                        text_boxes,
                        tolerance=5.0
                    )
                    
                    if overflow_ratio > self.overflow_threshold:
                        overflow_info = {
                            "slide_index": slide_idx,
                            "shape_id": shape_id,
                            "content_id": placement.get("content_id"),
                            "overflow_ratio": overflow_ratio,
                            "shape_bbox": shape_bbox,
                            "current_font_size": self._get_shape_font_size(shape)
                        }
                        measurements["overflows"].append(overflow_info)
                        slide_measurements["shape_overflows"].append(overflow_info)
                
                measurements["slide_measurements"][slide_idx] = slide_measurements
            
            logger.info(f"Measurement pass complete: {len(measurements['overflows'])} overflows detected")
            return measurements
            
        except Exception as e:
            logger.error(f"Measurement pass failed: {e}")
            return measurements
    
    def _correction_pass(
        self,
        prs: Presentation,
        overflows: List[Dict[str, Any]],
        placements: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Correct detected overflows
        
        Args:
            prs: PowerPoint presentation
            overflows: List of overflow detections
            placements: Original placements
        
        Returns:
            List of corrections made
        """
        corrections = []
        
        for overflow in overflows:
            slide_idx = overflow["slide_index"]
            shape_id = overflow["shape_id"]
            overflow_ratio = overflow["overflow_ratio"]
            
            slide = prs.slides[slide_idx]
            shape = self._find_shape_by_id(slide, shape_id)
            
            if not shape or not hasattr(shape, 'text_frame'):
                continue
            
            # Determine correction strategy
            if overflow_ratio < 0.3:
                # Small overflow: reduce font size
                correction = self._reduce_font_size(shape, overflow)
                if correction:
                    corrections.append(correction)
            
            elif overflow_ratio < 0.6:
                # Medium overflow: reduce font and adjust spacing
                correction = self._reduce_font_and_spacing(shape, overflow)
                if correction:
                    corrections.append(correction)
            
            else:
                # Large overflow: split to continuation slide
                correction = self._split_to_continuation(
                    prs, slide, shape, overflow, placements
                )
                if correction:
                    corrections.append(correction)
        
        logger.info(f"Correction pass complete: {len(corrections)} corrections made")
        return corrections
    
    def _reduce_font_size(
        self,
        shape,
        overflow: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Reduce font size to fix overflow
        
        Args:
            shape: PowerPoint shape object
            overflow: Overflow information
        
        Returns:
            Correction record or None
        """
        try:
            current_size = overflow.get("current_font_size", 12)
            overflow_ratio = overflow["overflow_ratio"]
            
            # Calculate new font size
            reduction_factor = 1.0 - (overflow_ratio * 0.3)  # Reduce by up to 30%
            new_size = max(
                self.min_font_size,
                int(current_size * reduction_factor)
            )
            
            if new_size >= current_size:
                return None
            
            # Apply font size change
            for paragraph in shape.text_frame.paragraphs:
                for run in paragraph.runs:
                    run.font.size = Pt(new_size)
            
            logger.debug(f"Reduced font size from {current_size} to {new_size}")
            
            return {
                "type": "font_resize",
                "slide_index": overflow["slide_index"],
                "shape_id": overflow["shape_id"],
                "old_size": current_size,
                "new_size": new_size,
                "reduction_percent": (1 - new_size/current_size) * 100
            }
            
        except Exception as e:
            logger.error(f"Failed to reduce font size: {e}")
            return None
    
    def _reduce_font_and_spacing(
        self,
        shape,
        overflow: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Reduce font size and adjust line spacing
        
        Args:
            shape: PowerPoint shape object
            overflow: Overflow information
        
        Returns:
            Correction record or None
        """
        try:
            # First reduce font size
            font_correction = self._reduce_font_size(shape, overflow)
            
            # Then adjust line spacing
            for paragraph in shape.text_frame.paragraphs:
                paragraph.line_spacing = 0.9  # Reduce to 90% spacing
            
            # Adjust margins
            shape.text_frame.margin_left = Pt(3)
            shape.text_frame.margin_right = Pt(3)
            shape.text_frame.margin_top = Pt(3)
            shape.text_frame.margin_bottom = Pt(3)
            
            correction = font_correction or {
                "type": "spacing_adjust",
                "slide_index": overflow["slide_index"],
                "shape_id": overflow["shape_id"]
            }
            
            correction["spacing_adjusted"] = True
            return correction
            
        except Exception as e:
            logger.error(f"Failed to adjust font and spacing: {e}")
            return None
    
    def _split_to_continuation(
        self,
        prs: Presentation,
        slide,
        shape,
        overflow: Dict[str, Any],
        placements: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Split overflowing content to a continuation slide
        
        Args:
            prs: Presentation object
            slide: Current slide
            shape: Overflowing shape
            overflow: Overflow information
            placements: Original placements
        
        Returns:
            Correction record or None
        """
        try:
            # Get the text content
            text_lines = []
            for paragraph in shape.text_frame.paragraphs:
                text_lines.append(paragraph.text)
            
            if len(text_lines) < 2:
                # Not enough content to split
                return self._reduce_font_and_spacing(shape, overflow)
            
            # Calculate split point (keep 60% on original slide)
            split_point = max(1, int(len(text_lines) * 0.6))
            
            # Keep first part in original shape
            shape.text_frame.clear()
            for i, line in enumerate(text_lines[:split_point]):
                p = shape.text_frame.add_paragraph() if i > 0 else shape.text_frame.paragraphs[0]
                p.text = line
            
            # Create continuation slide
            slide_layout = slide.slide_layout
            new_slide = prs.slides.add_slide(slide_layout)
            
            # Find corresponding shape in new slide
            new_shape = None
            for s in new_slide.shapes:
                if hasattr(s, 'text_frame') and s.left == shape.left and s.top == shape.top:
                    new_shape = s
                    break
            
            if new_shape:
                # Add continuation text
                new_shape.text_frame.clear()
                for i, line in enumerate(text_lines[split_point:]):
                    p = new_shape.text_frame.add_paragraph() if i > 0 else new_shape.text_frame.paragraphs[0]
                    p.text = line
                
                # Add continuation indicator
                title_shape = self._find_title_shape(new_slide)
                if title_shape:
                    title_shape.text = title_shape.text + " (continued)"
            
            logger.info(f"Split slide {overflow['slide_index']} content to continuation slide")
            
            return {
                "type": "slide_split",
                "original_slide": overflow["slide_index"],
                "continuation_slide": len(prs.slides) - 1,
                "shape_id": overflow["shape_id"],
                "lines_original": split_point,
                "lines_continuation": len(text_lines) - split_point
            }
            
        except Exception as e:
            logger.error(f"Failed to split to continuation slide: {e}")
            return None
    
    def _find_shape_by_id(self, slide, shape_id: str):
        """Find a shape in a slide by its ID"""
        for shape in slide.shapes:
            if hasattr(shape, 'shape_id') and str(shape.shape_id) == str(shape_id):
                return shape
            # Also check by index if shape_id is numeric
            try:
                idx = int(shape_id)
                if idx < len(slide.shapes):
                    return slide.shapes[idx]
            except (ValueError, IndexError):
                pass
        return None
    
    def _find_title_shape(self, slide):
        """Find the title shape in a slide"""
        for shape in slide.shapes:
            if shape.is_placeholder and hasattr(shape, 'placeholder_format'):
                if shape.placeholder_format.type == 1:  # Title placeholder
                    return shape
        return None
    
    def _get_shape_bbox_pts(self, shape) -> Dict[str, float]:
        """Get shape bounding box in points (for PDF comparison)"""
        # Convert EMU to points (1 point = 12700 EMU)
        left_pt = shape.left / 12700
        top_pt = shape.top / 12700
        width_pt = shape.width / 12700
        height_pt = shape.height / 12700
        
        return {
            "left": left_pt,
            "top": top_pt,
            "width": width_pt,
            "height": height_pt
        }
    
    def _get_shape_font_size(self, shape) -> int:
        """Get the predominant font size in a shape"""
        try:
            if hasattr(shape, 'text_frame'):
                for paragraph in shape.text_frame.paragraphs:
                    for run in paragraph.runs:
                        if run.font.size:
                            return run.font.size.pt
            return 12  # Default
        except:
            return 12


def create_render_measure_service(config: Optional[Dict[str, Any]] = None) -> RenderMeasureService:
    """
    Factory function to create a render measure service
    
    Args:
        config: Optional configuration
    
    Returns:
        RenderMeasureService instance
    """
    return RenderMeasureService(config)