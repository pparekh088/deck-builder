"""
Test feature flag fallback behavior
"""

import pytest
import os
from .utils import (
    create_fixture_pptx, APIClient, simple_spec, wait_for_api, get_env_flag
)


class TestFeatureFlagsFallback:
    """Test that system works with features disabled"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test environment"""
        # This test should only run when solver is disabled
        if get_env_flag("ACCURATE_SOLVER_ENABLED"):
            pytest.skip("Test only runs with ACCURATE_SOLVER_ENABLED=false")
        
        if not wait_for_api():
            pytest.skip("API not available")
        
        self.client = APIClient()
        
        # Upload a test template
        self.pptx_path = create_fixture_pptx()
        response = self.client.ingest_template(self.pptx_path)
        self.template_id = response["template_id"]
        
        yield
        
        self.client.close()
        self.pptx_path.unlink(missing_ok=True)
    
    def test_legacy_path_generates_deck(self):
        """Test that legacy path still generates a deck"""
        # Generate presentation with simple spec
        content_spec = simple_spec(num_slides=3)
        response = self.client.generate_presentation(
            self.template_id,
            content_spec
        )
        
        # Should still generate successfully
        assert "session_id" in response, "Response should contain session_id"
        assert response["session_id"], "session_id should not be empty"
        
        print(f"✓ Legacy path generated deck with session: {response['session_id']}")
        
        # Check if we're using greedy algorithm (no placements expected)
        if "placements" in response:
            print(f"ℹ Legacy path still provides placements: {len(response['placements'])} items")
        else:
            print(f"✓ Legacy path doesn't include placements (expected)")
    
    def test_all_features_disabled(self):
        """Test with all accuracy features disabled"""
        # Check current state of feature flags
        features = {
            "HYBRID_VISION_ENABLED": get_env_flag("HYBRID_VISION_ENABLED"),
            "ACCURATE_SOLVER_ENABLED": get_env_flag("ACCURATE_SOLVER_ENABLED"),
            "RENDER_MEASURE_ENABLED": get_env_flag("RENDER_MEASURE_ENABLED"),
            "ARCHETYPE_ALIGNMENT_ENABLED": get_env_flag("ARCHETYPE_ALIGNMENT_ENABLED"),
            "SAFETY_MAP_ENABLED": get_env_flag("SAFETY_MAP_ENABLED")
        }
        
        print("Feature flags status:")
        for flag, enabled in features.items():
            status = "✓ ON" if enabled else "✗ OFF"
            print(f"  {flag}: {status}")
        
        # Generate presentation
        content_spec = simple_spec(num_slides=2)
        response = self.client.generate_presentation(
            self.template_id,
            content_spec
        )
        
        assert "session_id" in response, "Should generate even with features off"
        
        # Check what's NOT in the response when features are off
        if not features["ACCURATE_SOLVER_ENABLED"]:
            # Placements might not be included
            if "placements" not in response:
                print("✓ No placements without solver (expected)")
        
        if not features["RENDER_MEASURE_ENABLED"]:
            # Render metrics might not be included
            if "render_metrics" not in response:
                print("✓ No render metrics without measurement (expected)")
            elif response.get("render_metrics", {}).get("font_shrink_events", 0) == 0:
                print("✓ No font corrections without measurement")
    
    def test_partial_features_enabled(self):
        """Test with some features enabled"""
        # Test profile generation
        profile = self.client.get_template_profile(self.template_id)
        
        assert "layouts" in profile, "Profile should still have layouts"
        
        # Check what features are reflected in the profile
        if get_env_flag("ARCHETYPE_ALIGNMENT_ENABLED"):
            has_archetype = any(
                "archetype_hint" in layout 
                for layout in profile["layouts"]
            )
            if has_archetype:
                print("✓ Archetype detection working independently")
        
        if get_env_flag("SAFETY_MAP_ENABLED"):
            has_safety = any(
                any("safety_penalty" in shape for shape in layout.get("shapes", []))
                for layout in profile["layouts"]
            )
            if has_safety:
                print("✓ Safety map working independently")
    
    def test_performance_without_solver(self):
        """Test that legacy path is still performant"""
        import time
        
        # Generate a larger presentation
        content_spec = simple_spec(num_slides=10)
        
        start_time = time.time()
        response = self.client.generate_presentation(
            self.template_id,
            content_spec
        )
        elapsed = time.time() - start_time
        
        # Legacy path should be faster (no solver overhead)
        assert elapsed < 15, f"Legacy generation took too long: {elapsed:.2f}s"
        assert "session_id" in response, "Should generate successfully"
        
        print(f"✓ Legacy path generated 10 slides in {elapsed:.2f}s")
    
    def test_backward_compatibility(self):
        """Test that API maintains backward compatibility"""
        # Use minimal request format
        minimal_request = {
            "template_id": self.template_id,
            "slides": [
                {
                    "title": "Test Slide",
                    "bullets": ["Point 1", "Point 2"]
                }
            ]
        }
        
        # Should work with minimal request
        response = self.client.generate_presentation(
            minimal_request["template_id"],
            minimal_request["slides"]
        )
        
        assert "session_id" in response, "Minimal request should work"
        print(f"✓ Backward compatible with minimal requests")