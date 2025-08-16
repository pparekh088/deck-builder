"""
Geometry utilities for PowerPoint shape calculations
"""

from typing import Dict, Tuple, Optional, List
from pptx.util import Emu, Inches

# Constants
EMU_PER_INCH = 914400
EMU_PER_CM = 360000
EMU_PER_PT = 12700

def emu_to_px(emu_value: int, dpi: int = 192) -> int:
    """Convert EMU (English Metric Units) to pixels"""
    inches = emu_value / EMU_PER_INCH
    return int(inches * dpi)

def px_to_emu(px_value: int, dpi: int = 192) -> int:
    """Convert pixels to EMU"""
    inches = px_value / dpi
    return int(inches * EMU_PER_INCH)

def inches_to_emu(inches: float) -> int:
    """Convert inches to EMU"""
    return int(inches * EMU_PER_INCH)

def emu_to_inches(emu_value: int) -> float:
    """Convert EMU to inches"""
    return emu_value / EMU_PER_INCH

def calculate_iou(bbox1: Dict[str, float], bbox2: Dict[str, float]) -> float:
    """
    Calculate Intersection over Union (IoU) for two bounding boxes
    
    Args:
        bbox1: Dict with keys 'left', 'top', 'width', 'height'
        bbox2: Dict with keys 'left', 'top', 'width', 'height'
    
    Returns:
        IoU score between 0 and 1
    """
    # Convert to corner coordinates
    x1_min = bbox1['left']
    y1_min = bbox1['top']
    x1_max = x1_min + bbox1['width']
    y1_max = y1_min + bbox1['height']
    
    x2_min = bbox2['left']
    y2_min = bbox2['top']
    x2_max = x2_min + bbox2['width']
    y2_max = y2_min + bbox2['height']
    
    # Calculate intersection area
    intersect_xmin = max(x1_min, x2_min)
    intersect_ymin = max(y1_min, y2_min)
    intersect_xmax = min(x1_max, x2_max)
    intersect_ymax = min(y1_max, y2_max)
    
    if intersect_xmax < intersect_xmin or intersect_ymax < intersect_ymin:
        return 0.0
    
    intersect_area = (intersect_xmax - intersect_xmin) * (intersect_ymax - intersect_ymin)
    
    # Calculate union area
    area1 = bbox1['width'] * bbox1['height']
    area2 = bbox2['width'] * bbox2['height']
    union_area = area1 + area2 - intersect_area
    
    if union_area == 0:
        return 0.0
    
    return intersect_area / union_area

def bbox_emu_to_px(bbox_emu: Dict[str, int], dpi: int = 192) -> Dict[str, int]:
    """Convert bounding box from EMU to pixels"""
    return {
        'left': emu_to_px(bbox_emu['left'], dpi),
        'top': emu_to_px(bbox_emu['top'], dpi),
        'width': emu_to_px(bbox_emu['width'], dpi),
        'height': emu_to_px(bbox_emu['height'], dpi)
    }

def bbox_px_to_emu(bbox_px: Dict[str, int], dpi: int = 192) -> Dict[str, int]:
    """Convert bounding box from pixels to EMU"""
    return {
        'left': px_to_emu(bbox_px['left'], dpi),
        'top': px_to_emu(bbox_px['top'], dpi),
        'width': px_to_emu(bbox_px['width'], dpi),
        'height': px_to_emu(bbox_px['height'], dpi)
    }

def get_shape_bbox_emu(shape) -> Dict[str, int]:
    """Extract bounding box from a PowerPoint shape in EMU units"""
    return {
        'left': int(shape.left),
        'top': int(shape.top),
        'width': int(shape.width),
        'height': int(shape.height)
    }

def get_shape_bbox_px(shape, dpi: int = 192) -> Dict[str, int]:
    """Extract bounding box from a PowerPoint shape in pixels"""
    bbox_emu = get_shape_bbox_emu(shape)
    return bbox_emu_to_px(bbox_emu, dpi)

def find_best_iou_match(
    target_bbox: Dict[str, float], 
    candidate_bboxes: List[Tuple[str, Dict[str, float]]], 
    min_iou: float = 0.5
) -> Optional[str]:
    """
    Find the best matching bounding box based on IoU
    
    Args:
        target_bbox: Target bounding box
        candidate_bboxes: List of (id, bbox) tuples
        min_iou: Minimum IoU threshold for a match
    
    Returns:
        ID of the best matching bbox, or None if no match above threshold
    """
    best_id = None
    best_iou = min_iou
    
    for candidate_id, candidate_bbox in candidate_bboxes:
        iou = calculate_iou(target_bbox, candidate_bbox)
        if iou > best_iou:
            best_iou = iou
            best_id = candidate_id
    
    return best_id

def bbox_center(bbox: Dict[str, float]) -> Tuple[float, float]:
    """Get the center point of a bounding box"""
    cx = bbox['left'] + bbox['width'] / 2
    cy = bbox['top'] + bbox['height'] / 2
    return cx, cy

def bbox_area(bbox: Dict[str, float]) -> float:
    """Calculate the area of a bounding box"""
    return bbox['width'] * bbox['height']

def is_bbox_inside(inner: Dict[str, float], outer: Dict[str, float]) -> bool:
    """Check if inner bbox is completely inside outer bbox"""
    return (inner['left'] >= outer['left'] and
            inner['top'] >= outer['top'] and
            inner['left'] + inner['width'] <= outer['left'] + outer['width'] and
            inner['top'] + inner['height'] <= outer['top'] + outer['height'])

def merge_bboxes(bboxes: List[Dict[str, float]]) -> Dict[str, float]:
    """Merge multiple bboxes into a single encompassing bbox"""
    if not bboxes:
        return {'left': 0, 'top': 0, 'width': 0, 'height': 0}
    
    min_left = min(b['left'] for b in bboxes)
    min_top = min(b['top'] for b in bboxes)
    max_right = max(b['left'] + b['width'] for b in bboxes)
    max_bottom = max(b['top'] + b['height'] for b in bboxes)
    
    return {
        'left': min_left,
        'top': min_top,
        'width': max_right - min_left,
        'height': max_bottom - min_top
    }