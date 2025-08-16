"""
Unit tests for archetype detection and alignment
"""

import pytest
import numpy as np
from app.analysis.archetypes import (
    ShapeSig, LayoutSig, nearest_archetype, 
    layout_vector, shape_from_dict, align_to_archetype
)


class TestArchetypes:
    """Test archetype functionality"""
    
    def test_shape_sig_creation(self):
        """Test ShapeSig creation and vector conversion"""
        shape = ShapeSig(
            kind="TITLE",
            role="Main Title",
            bbox_norm=(0.1, 0.1, 0.8, 0.2)
        )
        
        vector = shape.to_vector()
        assert len(vector) == 5
        assert vector[0] == 0.5  # center x
        assert vector[1] == 0.2  # center y
        assert vector[2] == 0.8  # width
        assert vector[3] == 0.2  # height
        assert vector[4] == 1    # TITLE type ID
    
    def test_nearest_archetype_title_slide(self):
        """Test detection of title slide archetype"""
        shapes = [
            ShapeSig("TITLE", "Title", (0.1, 0.2, 0.8, 0.15)),
            ShapeSig("SUBTITLE", "Subtitle", (0.2, 0.4, 0.6, 0.1))
        ]
        
        archetype = nearest_archetype(shapes)
        assert archetype == "TitleSlide"
    
    def test_nearest_archetype_title_body(self):
        """Test detection of title-body archetype"""
        shapes = [
            ShapeSig("TITLE", "Title", (0.08, 0.08, 0.84, 0.15)),
            ShapeSig("BODY", "Content", (0.1, 0.3, 0.8, 0.55))
        ]
        
        archetype = nearest_archetype(shapes)
        assert archetype == "TitleBody"
    
    def test_nearest_archetype_two_column(self):
        """Test detection of two-column archetype"""
        shapes = [
            ShapeSig("TITLE", "Title", (0.08, 0.08, 0.84, 0.12)),
            ShapeSig("BODY", "Left", (0.08, 0.25, 0.4, 0.6)),
            ShapeSig("BODY", "Right", (0.52, 0.25, 0.4, 0.6))
        ]
        
        archetype = nearest_archetype(shapes)
        assert archetype == "TwoColumn"
    
    def test_nearest_archetype_unknown(self):
        """Test unknown archetype for non-matching layouts"""
        shapes = [
            ShapeSig("TEXTBOX", "Random", (0.3, 0.3, 0.2, 0.2)),
            ShapeSig("TEXTBOX", "Random2", (0.6, 0.6, 0.15, 0.15))
        ]
        
        archetype = nearest_archetype(shapes, threshold=1.0)
        assert archetype == "Unknown"
    
    def test_layout_vector_sorting(self):
        """Test that layout vector sorts shapes by area"""
        shapes = [
            ShapeSig("BODY", "Small", (0.1, 0.1, 0.2, 0.2)),  # area = 0.04
            ShapeSig("TITLE", "Large", (0.1, 0.1, 0.8, 0.3)), # area = 0.24
            ShapeSig("SUBTITLE", "Medium", (0.1, 0.1, 0.4, 0.25))  # area = 0.1
        ]
        
        vector = layout_vector(shapes, max_shapes=3)
        # First 5 elements should be the largest shape (TITLE)
        assert vector[4] == 1  # TITLE type ID
    
    def test_shape_from_dict(self):
        """Test creating ShapeSig from dictionary"""
        shape_dict = {
            "ph_type": "TITLE",
            "role": "Main Title",
            "bbox_px": {"left": 100, "top": 100, "width": 800, "height": 200},
            "slide_width": 1920,
            "slide_height": 1080
        }
        
        shape_sig = shape_from_dict(shape_dict)
        assert shape_sig.kind == "TITLE"
        assert shape_sig.role == "Main Title"
        # Check normalized bbox
        assert abs(shape_sig.bbox_norm[0] - 100/1920) < 0.01
        assert abs(shape_sig.bbox_norm[2] - 800/1920) < 0.01
    
    def test_align_to_archetype(self):
        """Test alignment to canonical archetype"""
        layout_shapes = [
            {
                "id": "shape_1",
                "ph_type": "TITLE",
                "bbox_norm": (0.1, 0.15, 0.8, 0.2)
            },
            {
                "id": "shape_2",
                "ph_type": "SUBTITLE",
                "bbox_norm": (0.2, 0.4, 0.6, 0.12)
            }
        ]
        
        alignment = align_to_archetype(layout_shapes, "TitleSlide")
        
        assert alignment["archetype"] == "TitleSlide"
        assert alignment["aligned"] == True
        assert alignment["score"] > 0.5
        assert "shape_1" in alignment["mapping"]
        assert alignment["mapping"]["shape_1"]["canonical_role"] == "Title"
    
    def test_align_to_archetype_poor_match(self):
        """Test alignment with poor match"""
        layout_shapes = [
            {
                "id": "shape_1",
                "ph_type": "BODY",
                "bbox_norm": (0.5, 0.5, 0.2, 0.2)
            }
        ]
        
        alignment = align_to_archetype(layout_shapes, "TitleSlide")
        
        assert alignment["archetype"] == "TitleSlide"
        assert alignment["aligned"] == False
        assert alignment["score"] < 0.5
    
    def test_layout_vector_padding(self):
        """Test that layout vector pads to fixed size"""
        shapes = [
            ShapeSig("TITLE", "Title", (0.1, 0.1, 0.8, 0.2))
        ]
        
        vector = layout_vector(shapes, max_shapes=8)
        assert len(vector) == 8 * 5  # 8 shapes * 5 features each
        
        # Check that padding is zeros
        assert vector[5] == 0  # First element of second (padded) shape
        assert vector[-1] == 0  # Last element should be zero