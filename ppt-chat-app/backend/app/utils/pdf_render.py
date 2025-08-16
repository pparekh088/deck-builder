"""
PDF rendering utilities for PowerPoint measurement and validation
"""

import subprocess
import tempfile
import os
import logging
from typing import List, Dict, Tuple, Optional, Any
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None
    logging.warning("PyMuPDF not installed. PDF measurement features will be disabled.")

logger = logging.getLogger(__name__)


def pptx_to_pdf_bytes(pptx_path: str, soffice_path: str = "soffice") -> bytes:
    """
    Convert PPTX file to PDF using LibreOffice
    
    Args:
        pptx_path: Path to the PPTX file
        soffice_path: Path to LibreOffice executable (default: "soffice")
    
    Returns:
        PDF file content as bytes
    
    Raises:
        RuntimeError: If conversion fails
    """
    if not os.path.exists(pptx_path):
        raise FileNotFoundError(f"PPTX file not found: {pptx_path}")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Convert to PDF
        try:
            result = subprocess.run(
                [
                    soffice_path,
                    "--headless",
                    "--convert-to", "pdf",
                    "--outdir", temp_dir,
                    pptx_path
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # Find the output PDF
            pptx_name = Path(pptx_path).stem
            pdf_path = os.path.join(temp_dir, f"{pptx_name}.pdf")
            
            if not os.path.exists(pdf_path):
                raise RuntimeError(f"PDF output not found at {pdf_path}")
            
            with open(pdf_path, "rb") as f:
                return f.read()
                
        except subprocess.CalledProcessError as e:
            logger.error(f"LibreOffice conversion failed: {e.stderr}")
            raise RuntimeError(f"Failed to convert PPTX to PDF: {e.stderr}")
        except subprocess.TimeoutExpired:
            raise RuntimeError("PDF conversion timed out after 30 seconds")


def pdf_text_boxes(
    pdf_bytes: bytes, 
    page_index: int = 0
) -> Tuple[List[Dict[str, Any]], Tuple[float, float]]:
    """
    Extract text boxes with bounding boxes from a PDF page
    
    Args:
        pdf_bytes: PDF file content as bytes
        page_index: Zero-based page index
    
    Returns:
        Tuple of (text_boxes, page_size)
        - text_boxes: List of dicts with 'bbox' (x0,y0,x1,y1) and 'text'
        - page_size: (width, height) in points
    """
    if fitz is None:
        logger.warning("PyMuPDF not available, returning empty boxes")
        return [], (0, 0)
    
    try:
        # Open PDF from bytes
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        if page_index >= len(doc):
            raise ValueError(f"Page index {page_index} out of range (document has {len(doc)} pages)")
        
        page = doc.load_page(page_index)
        boxes = []
        
        # Extract text blocks with positions
        blocks = page.get_text("blocks")
        
        for block in blocks:
            # Block format: (x0, y0, x1, y1, text, block_no, block_type)
            if len(block) >= 5:
                x0, y0, x1, y1, text = block[:5]
                # Clean up text
                text = text.strip() if isinstance(text, str) else ""
                if text:
                    boxes.append({
                        "bbox": (x0, y0, x1, y1),
                        "text": text,
                        "width": x1 - x0,
                        "height": y1 - y0
                    })
        
        # Get page dimensions
        page_rect = page.rect
        page_size = (page_rect.width, page_rect.height)
        
        doc.close()
        return boxes, page_size
        
    except Exception as e:
        logger.error(f"Failed to extract text boxes from PDF: {e}")
        return [], (0, 0)


def estimate_text_overflow(
    shape_bbox: Dict[str, float],
    text_boxes: List[Dict[str, Any]],
    tolerance: float = 5.0
) -> float:
    """
    Estimate text overflow ratio for a shape
    
    Args:
        shape_bbox: Shape bounding box with 'left', 'top', 'width', 'height' in points
        text_boxes: List of text boxes from PDF
        tolerance: Pixel tolerance for boundary checking
    
    Returns:
        Overflow ratio (0.0 = no overflow, 1.0 = complete overflow)
    """
    if not text_boxes:
        return 0.0
    
    shape_left = shape_bbox['left']
    shape_top = shape_bbox['top']
    shape_right = shape_left + shape_bbox['width']
    shape_bottom = shape_top + shape_bbox['height']
    
    total_text_area = 0.0
    overflow_area = 0.0
    
    for box in text_boxes:
        bbox = box['bbox']
        text_left, text_top, text_right, text_bottom = bbox
        
        # Calculate text box area
        text_width = text_right - text_left
        text_height = text_bottom - text_top
        text_area = text_width * text_height
        total_text_area += text_area
        
        # Check if text box is within shape (with tolerance)
        if (text_left < shape_left - tolerance or
            text_top < shape_top - tolerance or
            text_right > shape_right + tolerance or
            text_bottom > shape_bottom + tolerance):
            
            # Calculate overflow amount
            overflow_left = max(0, shape_left - text_left - tolerance)
            overflow_top = max(0, shape_top - text_top - tolerance)
            overflow_right = max(0, text_right - shape_right - tolerance)
            overflow_bottom = max(0, text_bottom - shape_bottom - tolerance)
            
            # Approximate overflow area
            overflow_width = overflow_left + overflow_right
            overflow_height = overflow_top + overflow_bottom
            
            # Calculate the portion that overflows
            if overflow_width > 0 or overflow_height > 0:
                overflow_ratio_w = min(1.0, overflow_width / text_width) if text_width > 0 else 0
                overflow_ratio_h = min(1.0, overflow_height / text_height) if text_height > 0 else 0
                overflow_ratio = max(overflow_ratio_w, overflow_ratio_h)
                overflow_area += text_area * overflow_ratio
    
    if total_text_area == 0:
        return 0.0
    
    return min(1.0, overflow_area / total_text_area)


def convert_pdf_bbox_to_px(
    bbox: Tuple[float, float, float, float],
    dpi: int = 192
) -> Dict[str, int]:
    """
    Convert PDF bbox (in points) to pixels
    
    Args:
        bbox: (x0, y0, x1, y1) in points
        dpi: DPI for conversion
    
    Returns:
        Dict with 'left', 'top', 'width', 'height' in pixels
    """
    # 1 point = 1/72 inch
    points_per_inch = 72
    scale = dpi / points_per_inch
    
    x0, y0, x1, y1 = bbox
    return {
        "left": int(x0 * scale),
        "top": int(y0 * scale),
        "width": int((x1 - x0) * scale),
        "height": int((y1 - y0) * scale)
    }