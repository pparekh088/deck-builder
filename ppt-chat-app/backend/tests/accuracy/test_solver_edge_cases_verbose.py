"""
Verbose edge case tests for ILP solver with detailed diagnostics
"""

import pytest
from app.services.solver_ilp import (
    solve_assignment, default_weight_fn, default_compat_fn,
    SolverInfeasibleError
)


class TestSolverEdgeCasesVerbose:
    """Test edge cases with verbose diagnostics"""
    
    @pytest.mark.parametrize("test_case,content_items,shape_items,expected_status,expected_mapping", [
        # Case 1: Empty content
        (
            "empty_content",
            [],  # No content
            [{"sid": "s1", "ph_type": "TITLE", "place_ok": True}],
            "Empty input",
            {}
        ),
        # Case 2: No compatible shapes for required content
        (
            "no_compatible_required",
            [{"id": "chart1", "type": "CHART", "required": True}],
            [{"sid": "s1", "ph_type": "TITLE", "place_ok": True}],  # TITLE incompatible with CHART
            "infeasible",
            None  # Expect exception
        ),
        # Case 3: Tie-break scenario
        (
            "tie_break",
            [{"id": "title", "type": "TITLE", "required": True}],
            [
                {"sid": "s1", "ph_type": "TITLE", "place_ok": True, "priority": 2},
                {"sid": "s2", "ph_type": "TITLE", "place_ok": True, "priority": 1}  # Lower priority = better
            ],
            "Optimal",
            {"title": "s2"}  # Should pick s2 due to better priority
        ),
        # Case 4: place_content=False shapes must not be used
        (
            "place_content_false",
            [{"id": "body", "type": "BODY", "required": True}],
            [
                {"sid": "s1", "ph_type": "BODY", "place_ok": False},  # Not placeable
                {"sid": "s2", "ph_type": "BODY", "place_ok": True}    # Placeable
            ],
            "Optimal",
            {"body": "s2"}  # Must pick s2
        ),
        # Case 5: Chart/Table strict compatibility
        (
            "strict_compat",
            [
                {"id": "chart", "type": "CHART", "required": True},
                {"id": "text", "type": "BODY", "required": True}
            ],
            [
                {"sid": "s1", "ph_type": "TITLE", "place_ok": True},     # Incompatible with CHART
                {"sid": "s2", "ph_type": "CHART", "place_ok": True},     # Compatible with CHART
                {"sid": "s3", "ph_type": "TEXTBOX", "place_ok": True}    # Compatible with BODY
            ],
            "Optimal",
            {"chart": "s2", "text": "s3"}
        )
    ])
    def test_edge_cases(self, test_case, content_items, shape_items, expected_status, expected_mapping):
        """Test various edge cases with verbose output"""
        print(f"\n=== Testing: {test_case} ===")
        
        if expected_mapping is None:
            # Expect infeasible error
            with pytest.raises(SolverInfeasibleError) as exc_info:
                mapping, debug_info = solve_assignment(
                    content_items, shape_items,
                    default_weight_fn, default_compat_fn,
                    debug=True
                )
            
            # Print debug info from exception
            debug_info = exc_info.value.debug_info
            self._print_debug_info(test_case, debug_info)
            assert "infeasible" in expected_status.lower()
            
        else:
            # Normal case
            mapping, debug_info = solve_assignment(
                content_items, shape_items,
                default_weight_fn, default_compat_fn,
                debug=True
            )
            
            # Print verbose diagnostics
            self._print_debug_info(test_case, debug_info)
            
            # Verify results
            assert debug_info["status"] == expected_status, \
                f"Expected status {expected_status}, got {debug_info['status']}"
            assert mapping == expected_mapping, \
                f"Expected mapping {expected_mapping}, got {mapping}"
    
    def _print_debug_info(self, test_case: str, debug_info: dict):
        """Print detailed debug information"""
        print(f"\n--- Debug Info for {test_case} ---")
        print(f"Status: {debug_info['status']}")
        print(f"Objective Value: {debug_info['objective_value']:.3f}")
        print(f"Total Content: {debug_info['total_content']}")
        print(f"Total Shapes: {debug_info['total_shapes']}")
        
        if debug_info['valid_pairs']:
            print("\nValid Pairs (content -> shape: weight):")
            for pair in debug_info['valid_pairs']:
                print(f"  {pair['content']} -> {pair['shape']}: {pair['weight']:.2f}")
        
        if debug_info['incompatibility_reasons']:
            print("\nIncompatibility Reasons:")
            for (c_id, s_id), reason in debug_info['incompatibility_reasons'].items():
                print(f"  {c_id} -> {s_id}: {reason}")
        
        if debug_info['binding_constraints']:
            print(f"\nBinding Constraints: {debug_info['binding_constraints']}")
        
        print("-" * 40)
    
    def test_multiple_required_insufficient_shapes(self):
        """Test when there are more required items than compatible shapes"""
        content_items = [
            {"id": "title1", "type": "TITLE", "required": True},
            {"id": "title2", "type": "TITLE", "required": True},
            {"id": "title3", "type": "TITLE", "required": True}
        ]
        
        shape_items = [
            {"sid": "s1", "ph_type": "TITLE", "place_ok": True},
            {"sid": "s2", "ph_type": "TITLE", "place_ok": True}
            # Only 2 TITLE shapes for 3 required titles
        ]
        
        with pytest.raises(SolverInfeasibleError) as exc_info:
            mapping, debug_info = solve_assignment(
                content_items, shape_items,
                default_weight_fn, default_compat_fn,
                debug=True
            )
        
        debug_info = exc_info.value.debug_info
        print("\n=== Insufficient Shapes Test ===")
        self._print_debug_info("insufficient_shapes", debug_info)
        
        # Verify the problem was detected as infeasible
        assert "infeasible" in str(exc_info.value).lower()
    
    def test_safety_penalty_affects_selection(self):
        """Test that safety penalties properly influence selection"""
        content_items = [
            {"id": "body", "type": "BODY", "required": True}
        ]
        
        shape_items = [
            {"sid": "unsafe", "ph_type": "BODY", "place_ok": True, "safety_penalty": 0.9},
            {"sid": "safe", "ph_type": "BODY", "place_ok": True, "safety_penalty": 0.0}
        ]
        
        mapping, debug_info = solve_assignment(
            content_items, shape_items,
            default_weight_fn, default_compat_fn,
            debug=True
        )
        
        print("\n=== Safety Penalty Test ===")
        self._print_debug_info("safety_penalty", debug_info)
        
        # Should pick the safe shape
        assert mapping["body"] == "safe", "Should select shape with lower safety penalty"
        
        # Verify weights reflect penalties
        unsafe_weight = debug_info["pair_weights"][("body", "unsafe")]
        safe_weight = debug_info["pair_weights"][("body", "safe")]
        assert safe_weight > unsafe_weight, "Safe shape should have higher weight"
    
    def test_optional_vs_required_content(self):
        """Test mixing optional and required content"""
        content_items = [
            {"id": "req_title", "type": "TITLE", "required": True},
            {"id": "opt_subtitle", "type": "SUBTITLE", "required": False},
            {"id": "req_body", "type": "BODY", "required": True}
        ]
        
        shape_items = [
            {"sid": "s1", "ph_type": "TITLE", "place_ok": True},
            {"sid": "s2", "ph_type": "BODY", "place_ok": True}
            # No SUBTITLE shape available
        ]
        
        mapping, debug_info = solve_assignment(
            content_items, shape_items,
            default_weight_fn, default_compat_fn,
            debug=True
        )
        
        print("\n=== Optional vs Required Test ===")
        self._print_debug_info("optional_required", debug_info)
        
        # Required items must be mapped
        assert "req_title" in mapping, "Required title must be mapped"
        assert "req_body" in mapping, "Required body must be mapped"
        
        # Optional subtitle should not be mapped (no compatible shape)
        assert "opt_subtitle" not in mapping, "Optional subtitle should not be mapped"
        
        # Verify status is still optimal
        assert debug_info["status"] == "Optimal"