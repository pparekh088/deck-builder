"""
Unit tests for safety map functionality
"""

import pytest
import numpy as np
from app.analysis.safety_map import (
    make_safety_mask, overlap_penalty, compute_shape_safety_scores,
    encode_mask_to_string, decode_mask_from_string, create_safety_report
)


class TestSafetyMap:
    """Test safety map functionality"""
    
    def test_make_safety_mask_basic(self):
        """Test basic safety mask creation"""
        labels = [
            {
                "role": "Logo",
                "place_content": False,
                "bbox_px": {"left": 0, "top": 0, "width": 100, "height": 50}
            },
            {
                "role": "Title",
                "place_content": True,
                "bbox_px": {"left": 200, "top": 100, "width": 400, "height": 100}
            }
        ]
        
        mask = make_safety_mask(None, labels, 800, 600)
        
        # Logo area should be unsafe (0)
        assert mask[25, 50] == 0
        
        # Title area should be safe (1)
        assert mask[150, 400] == 1
        
        # Other areas should be safe
        assert mask[500, 700] == 1
    
    def test_make_safety_mask_decorative_elements(self):
        """Test that decorative elements are marked unsafe"""
        labels = [
            {"role": "Decor", "place_content": True, 
             "bbox_px": {"left": 0, "top": 0, "width": 100, "height": 100}},
            {"role": "Footer", "place_content": True,
             "bbox_px": {"left": 0, "top": 500, "width": 800, "height": 100}},
            {"role": "Watermark", "place_content": True,
             "bbox_px": {"left": 700, "top": 0, "width": 100, "height": 600}}
        ]
        
        mask = make_safety_mask(None, labels, 800, 600)
        
        # All decorative areas should be unsafe
        assert mask[50, 50] == 0    # Decor
        assert mask[550, 400] == 0  # Footer
        assert mask[300, 750] == 0  # Watermark
    
    def test_overlap_penalty_calculation(self):
        """Test overlap penalty calculation"""
        mask = np.ones((600, 800), dtype=np.uint8)
        # Create unsafe zone
        mask[100:200, 100:300] = 0
        
        # Shape completely in safe zone
        penalty1 = overlap_penalty(
            {"left": 400, "top": 300, "width": 100, "height": 100},
            mask
        )
        assert penalty1 == 0.0
        
        # Shape completely in unsafe zone
        penalty2 = overlap_penalty(
            {"left": 150, "top": 150, "width": 50, "height": 30},
            mask
        )
        assert penalty2 == 1.0
        
        # Shape partially overlapping unsafe zone
        penalty3 = overlap_penalty(
            {"left": 250, "top": 150, "width": 100, "height": 100},
            mask
        )
        assert 0 < penalty3 < 1.0
    
    def test_compute_shape_safety_scores(self):
        """Test computing safety scores for multiple shapes"""
        mask = np.ones((600, 800), dtype=np.uint8)
        mask[0:100, 0:800] = 0  # Top banner unsafe
        
        shapes = [
            {"id": "s1", "bbox_px": {"left": 100, "top": 50, "width": 200, "height": 100}},
            {"id": "s2", "bbox_px": {"left": 100, "top": 200, "width": 200, "height": 100}},
            {"id": "s3", "bbox_px": {"left": 100, "top": 10, "width": 200, "height": 50}}
        ]
        
        scored_shapes = compute_shape_safety_scores(shapes, mask)
        
        # s1 partially overlaps unsafe zone
        assert 0 < scored_shapes[0]["safety_penalty"] < 1.0
        
        # s2 is completely safe
        assert scored_shapes[1]["safety_penalty"] == 0.0
        
        # s3 is mostly unsafe
        assert scored_shapes[2]["safety_penalty"] > 0.5
        assert scored_shapes[2]["place_ok"] == False  # Should be marked unplaceable
    
    def test_mask_encoding_decoding(self):
        """Test mask serialization and deserialization"""
        original = np.random.randint(0, 2, (100, 150), dtype=np.uint8)
        
        encoded = encode_mask_to_string(original)
        assert isinstance(encoded, str)
        assert len(encoded) > 0
        
        decoded = decode_mask_from_string(encoded)
        assert decoded is not None
        assert decoded.shape == original.shape
        assert np.array_equal(decoded, original)
    
    def test_mask_encoding_empty(self):
        """Test encoding empty mask"""
        encoded = encode_mask_to_string(None)
        assert encoded == ""
        
        decoded = decode_mask_from_string("")
        assert decoded is None
    
    def test_create_safety_report(self):
        """Test safety report generation"""
        mask = np.ones((600, 800), dtype=np.uint8)
        mask[0:200, 0:800] = 0  # Large unsafe area
        
        shapes = [
            {"id": "s1", "role": "Title", "safety_penalty": 0.0, "place_ok": True},
            {"id": "s2", "role": "Logo", "safety_penalty": 0.9, "place_ok": False},
            {"id": "s3", "role": "Body", "safety_penalty": 0.3, "place_ok": True},
            {"id": "s4", "role": "Footer", "safety_penalty": 1.0, "place_ok": False}
        ]
        
        report = create_safety_report(shapes, mask)
        
        assert report["total_shapes"] == 4
        assert report["unsafe_shapes"] == 2  # s2 and s4
        assert report["blocked_shapes"] == 2  # s2 and s4
        assert report["unsafe_coverage_ratio"] > 0.3
        
        # Check role penalties
        assert "Logo" in report["role_penalties"]
        assert report["role_penalties"]["Logo"]["avg_penalty"] == 0.9
        
        # Should have recommendations
        assert len(report["recommendations"]) > 0
    
    def test_safety_penalty_with_scale(self):
        """Test penalty calculation with custom scale"""
        mask = np.ones((100, 100), dtype=np.uint8)
        mask[40:60, 40:60] = 0  # Center unsafe
        
        bbox = {"left": 40, "top": 40, "width": 20, "height": 20}
        
        # Default scale
        penalty1 = overlap_penalty(bbox, mask, penalty_scale=1.0)
        
        # Double scale
        penalty2 = overlap_penalty(bbox, mask, penalty_scale=2.0)
        
        assert penalty2 == min(1.0, penalty1 * 2.0)
    
    def test_boundary_conditions(self):
        """Test handling of boundary conditions"""
        mask = np.ones((100, 100), dtype=np.uint8)
        
        # Shape outside mask bounds
        penalty = overlap_penalty(
            {"left": 150, "top": 150, "width": 50, "height": 50},
            mask
        )
        assert penalty == 0.0
        
        # Shape partially outside bounds
        penalty = overlap_penalty(
            {"left": 80, "top": 80, "width": 40, "height": 40},
            mask
        )
        assert penalty == 0.0  # The part within bounds is safe