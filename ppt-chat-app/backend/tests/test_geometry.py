"""
Unit tests for geometry utilities
"""

import pytest
from app.utils.geometry import (
    calculate_iou, emu_to_px, px_to_emu, 
    bbox_emu_to_px, find_best_iou_match,
    bbox_center, bbox_area, is_bbox_inside, merge_bboxes
)

class TestEMUConversion:
    """Test EMU to pixel conversion and vice versa"""
    
    def test_emu_to_px_default_dpi(self):
        """Test EMU to pixel conversion with default DPI"""
        emu = 914400  # 1 inch in EMU
        px = emu_to_px(emu, dpi=192)
        assert px == 192  # 1 inch at 192 DPI = 192 pixels
    
    def test_px_to_emu_default_dpi(self):
        """Test pixel to EMU conversion"""
        px = 192
        emu = px_to_emu(px, dpi=192)
        assert emu == 914400  # 192 pixels at 192 DPI = 1 inch = 914400 EMU
    
    def test_bbox_conversion(self):
        """Test bounding box conversion"""
        bbox_emu = {
            'left': 914400,
            'top': 914400,
            'width': 1828800,  # 2 inches
            'height': 914400   # 1 inch
        }
        
        bbox_px = bbox_emu_to_px(bbox_emu, dpi=192)
        
        assert bbox_px['left'] == 192
        assert bbox_px['top'] == 192
        assert bbox_px['width'] == 384  # 2 inches at 192 DPI
        assert bbox_px['height'] == 192

class TestIoU:
    """Test Intersection over Union calculations"""
    
    def test_iou_perfect_overlap(self):
        """Test IoU for perfectly overlapping boxes"""
        bbox1 = {'left': 10, 'top': 10, 'width': 20, 'height': 20}
        bbox2 = {'left': 10, 'top': 10, 'width': 20, 'height': 20}
        
        iou = calculate_iou(bbox1, bbox2)
        assert iou == 1.0
    
    def test_iou_no_overlap(self):
        """Test IoU for non-overlapping boxes"""
        bbox1 = {'left': 0, 'top': 0, 'width': 10, 'height': 10}
        bbox2 = {'left': 20, 'top': 20, 'width': 10, 'height': 10}
        
        iou = calculate_iou(bbox1, bbox2)
        assert iou == 0.0
    
    def test_iou_partial_overlap(self):
        """Test IoU for partially overlapping boxes"""
        bbox1 = {'left': 0, 'top': 0, 'width': 20, 'height': 20}
        bbox2 = {'left': 10, 'top': 10, 'width': 20, 'height': 20}
        
        iou = calculate_iou(bbox1, bbox2)
        
        # Intersection: 10x10 = 100
        # Union: 400 + 400 - 100 = 700
        # IoU: 100/700 ≈ 0.143
        assert abs(iou - 0.143) < 0.01
    
    def test_iou_50_percent_overlap(self):
        """Test IoU for 50% overlap"""
        bbox1 = {'left': 0, 'top': 0, 'width': 20, 'height': 20}
        bbox2 = {'left': 10, 'top': 0, 'width': 20, 'height': 20}
        
        iou = calculate_iou(bbox1, bbox2)
        
        # Intersection: 10x20 = 200
        # Union: 400 + 400 - 200 = 600
        # IoU: 200/600 = 0.333
        assert abs(iou - 0.333) < 0.01
    
    def test_iou_contained_box(self):
        """Test IoU when one box is contained in another"""
        bbox1 = {'left': 0, 'top': 0, 'width': 100, 'height': 100}
        bbox2 = {'left': 25, 'top': 25, 'width': 50, 'height': 50}
        
        iou = calculate_iou(bbox1, bbox2)
        
        # Intersection: 50x50 = 2500
        # Union: 10000 + 2500 - 2500 = 10000
        # IoU: 2500/10000 = 0.25
        assert iou == 0.25

class TestIoUMatching:
    """Test IoU-based matching"""
    
    def test_find_best_match(self):
        """Test finding best IoU match"""
        target = {'left': 10, 'top': 10, 'width': 20, 'height': 20}
        
        candidates = [
            ('shape1', {'left': 0, 'top': 0, 'width': 10, 'height': 10}),    # No overlap
            ('shape2', {'left': 5, 'top': 5, 'width': 20, 'height': 20}),    # Some overlap
            ('shape3', {'left': 10, 'top': 10, 'width': 20, 'height': 20}), # Perfect match
        ]
        
        best_id = find_best_iou_match(target, candidates, min_iou=0.5)
        assert best_id == 'shape3'
    
    def test_no_match_below_threshold(self):
        """Test no match when all IoUs below threshold"""
        target = {'left': 100, 'top': 100, 'width': 20, 'height': 20}
        
        candidates = [
            ('shape1', {'left': 0, 'top': 0, 'width': 10, 'height': 10}),
            ('shape2', {'left': 200, 'top': 200, 'width': 20, 'height': 20}),
        ]
        
        best_id = find_best_iou_match(target, candidates, min_iou=0.5)
        assert best_id is None

class TestBboxUtilities:
    """Test other bounding box utilities"""
    
    def test_bbox_center(self):
        """Test finding bbox center"""
        bbox = {'left': 10, 'top': 20, 'width': 30, 'height': 40}
        cx, cy = bbox_center(bbox)
        
        assert cx == 25  # 10 + 30/2
        assert cy == 40  # 20 + 40/2
    
    def test_bbox_area(self):
        """Test calculating bbox area"""
        bbox = {'left': 0, 'top': 0, 'width': 10, 'height': 20}
        area = bbox_area(bbox)
        assert area == 200
    
    def test_is_bbox_inside(self):
        """Test checking if bbox is inside another"""
        outer = {'left': 0, 'top': 0, 'width': 100, 'height': 100}
        inner = {'left': 10, 'top': 10, 'width': 20, 'height': 20}
        outside = {'left': 90, 'top': 90, 'width': 20, 'height': 20}
        
        assert is_bbox_inside(inner, outer) is True
        assert is_bbox_inside(outside, outer) is False
        assert is_bbox_inside(outer, inner) is False
    
    def test_merge_bboxes(self):
        """Test merging multiple bboxes"""
        bboxes = [
            {'left': 10, 'top': 10, 'width': 20, 'height': 20},
            {'left': 50, 'top': 50, 'width': 30, 'height': 30},
            {'left': 0, 'top': 40, 'width': 10, 'height': 10}
        ]
        
        merged = merge_bboxes(bboxes)
        
        assert merged['left'] == 0    # Minimum left
        assert merged['top'] == 10    # Minimum top
        assert merged['width'] == 80  # From 0 to 80 (50+30)
        assert merged['height'] == 70 # From 10 to 80 (50+30)
    
    def test_merge_empty_bboxes(self):
        """Test merging empty list of bboxes"""
        merged = merge_bboxes([])
        assert merged == {'left': 0, 'top': 0, 'width': 0, 'height': 0}

if __name__ == "__main__":
    pytest.main([__file__, "-v"])