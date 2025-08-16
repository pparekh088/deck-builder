"""
Unit tests for ILP solver
"""

import pytest
from app.services.solver_ilp import (
    solve_assignment,
    default_weight_fn,
    default_compat_fn,
    choose_layout_and_mapping,
    estimate_overflow_risk
)


class TestILPSolver:
    """Test ILP solver functionality"""
    
    def test_solve_assignment_basic(self):
        """Test basic assignment solving"""
        content_items = [
            {"id": "title", "type": "TITLE", "required": True},
            {"id": "body", "type": "BODY", "required": True}
        ]
        
        shape_items = [
            {"sid": "s1", "ph_type": "TITLE", "place_ok": True},
            {"sid": "s2", "ph_type": "BODY", "place_ok": True}
        ]
        
        def weight_fn(c, s):
            if c["type"] == s["ph_type"]:
                return 1.0
            return 0.0
        
        def compat_fn(c, s):
            return c["type"] == s["ph_type"]
        
        mapping = solve_assignment(
            content_items, shape_items, weight_fn, compat_fn
        )
        
        assert mapping["title"] == "s1"
        assert mapping["body"] == "s2"
    
    def test_solve_assignment_with_constraints(self):
        """Test assignment with compatibility constraints"""
        content_items = [
            {"id": "chart", "type": "CHART", "required": True},
            {"id": "text", "type": "BODY", "required": True}
        ]
        
        shape_items = [
            {"sid": "s1", "ph_type": "BODY", "place_ok": True},
            {"sid": "s2", "ph_type": "CHART", "place_ok": True}
        ]
        
        mapping = solve_assignment(
            content_items, shape_items, 
            default_weight_fn, default_compat_fn
        )
        
        assert mapping["chart"] == "s2"
        assert mapping["text"] == "s1"
    
    def test_solve_assignment_with_safety_penalty(self):
        """Test that safety penalties affect assignment"""
        content_items = [
            {"id": "title", "type": "TITLE", "required": True}
        ]
        
        shape_items = [
            {"sid": "s1", "ph_type": "TITLE", "place_ok": True, "safety_penalty": 0.8},
            {"sid": "s2", "ph_type": "TITLE", "place_ok": True, "safety_penalty": 0.1}
        ]
        
        mapping = solve_assignment(
            content_items, shape_items,
            default_weight_fn, default_compat_fn
        )
        
        # Should prefer s2 due to lower safety penalty
        assert mapping["title"] == "s2"
    
    def test_solve_assignment_with_tags(self):
        """Test that designer tags have highest priority"""
        content_items = [
            {"id": "bullets", "type": "BODY", "required": True}
        ]
        
        shape_items = [
            {"sid": "s1", "ph_type": "BODY", "place_ok": True, "tags": []},
            {"sid": "s2", "ph_type": "TEXTBOX", "place_ok": True, "tags": ["slot:bullets"]}
        ]
        
        mapping = solve_assignment(
            content_items, shape_items,
            default_weight_fn, default_compat_fn
        )
        
        # Should prefer s2 due to tag match despite type mismatch
        assert mapping["bullets"] == "s2"
    
    def test_overflow_risk_estimation(self):
        """Test overflow risk calculation"""
        # Small content in large shape
        risk1 = estimate_overflow_risk(
            {"type": "BODY", "size_hint": "S"},
            {"bbox_px": {"left": 0, "top": 0, "width": 800, "height": 600},
             "slide_width": 1920, "slide_height": 1080}
        )
        assert risk1 < 0.2
        
        # Large content in small shape
        risk2 = estimate_overflow_risk(
            {"type": "BODY", "size_hint": "XL"},
            {"bbox_px": {"left": 0, "top": 0, "width": 200, "height": 100},
             "slide_width": 1920, "slide_height": 1080}
        )
        assert risk2 > 0.5
    
    def test_choose_layout_and_mapping(self):
        """Test complete layout selection and mapping"""
        layouts = [
            {
                "name": "Title Slide",
                "layout_id": 0,
                "shapes": [
                    {"sid": "s1", "ph_type": "TITLE", "place_ok": True,
                     "bbox_px": {"left": 100, "top": 100, "width": 800, "height": 100}},
                    {"sid": "s2", "ph_type": "SUBTITLE", "place_ok": True,
                     "bbox_px": {"left": 100, "top": 300, "width": 800, "height": 100}}
                ]
            },
            {
                "name": "Content Slide",
                "layout_id": 1,
                "shapes": [
                    {"sid": "s3", "ph_type": "TITLE", "place_ok": True,
                     "bbox_px": {"left": 100, "top": 50, "width": 800, "height": 80}},
                    {"sid": "s4", "ph_type": "BODY", "place_ok": True,
                     "bbox_px": {"left": 100, "top": 200, "width": 800, "height": 400}}
                ]
            }
        ]
        
        content_spec = [
            {"id": "title", "type": "TITLE", "required": True},
            {"id": "bullets", "type": "BODY", "required": True}
        ]
        
        layout, mapping = choose_layout_and_mapping(layouts, content_spec)
        
        # Should choose Content Slide since it has both TITLE and BODY
        assert layout["layout_id"] == 1
        assert mapping["title"] == "s3"
        assert mapping["bullets"] == "s4"
    
    def test_empty_inputs(self):
        """Test handling of empty inputs"""
        # Empty content
        mapping = solve_assignment(
            [], 
            [{"sid": "s1", "ph_type": "TITLE"}],
            default_weight_fn, default_compat_fn
        )
        assert mapping == {}
        
        # Empty shapes
        mapping = solve_assignment(
            [{"id": "c1", "type": "TITLE"}],
            [],
            default_weight_fn, default_compat_fn
        )
        assert mapping == {}
    
    def test_infeasible_problem(self):
        """Test handling of infeasible problems"""
        content_items = [
            {"id": "chart", "type": "CHART", "required": True},
            {"id": "table", "type": "TABLE", "required": True}
        ]
        
        shape_items = [
            {"sid": "s1", "ph_type": "TITLE", "place_ok": True}  # No compatible shapes
        ]
        
        mapping = solve_assignment(
            content_items, shape_items,
            default_weight_fn, default_compat_fn
        )
        
        # Should return empty mapping for infeasible problem
        assert mapping == {}