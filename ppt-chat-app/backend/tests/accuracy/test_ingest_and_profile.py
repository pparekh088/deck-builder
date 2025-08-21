"""
Test template ingestion and profile generation
"""

import pytest
from pathlib import Path
from .utils import (
    create_fixture_pptx, APIClient, wait_for_api, get_env_flag
)


class TestIngestAndProfile:
    """Test template ingestion and profile generation"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test environment"""
        # Wait for API to be available
        if not wait_for_api():
            pytest.skip("API not available")
        
        self.client = APIClient()
        yield
        self.client.close()
    
    def test_upload_fixture_deck(self):
        """Upload a fixture deck and verify profile"""
        # Create fixture PPTX
        pptx_path = create_fixture_pptx(include_decor=True, include_two_column=True)
        
        try:
            # Upload template
            response = self.client.ingest_template(pptx_path)
            assert "template_id" in response, "Response should contain template_id"
            template_id = response["template_id"]
            assert template_id, "template_id should not be empty"
            
            # Fetch profile
            profile = self.client.get_template_profile(template_id)
            assert "layouts" in profile, "Profile should contain layouts"
            assert isinstance(profile["layouts"], list), "Layouts should be a list"
            assert len(profile["layouts"]) > 0, "Should have at least one layout"
            
            # Check for shapes in layouts
            has_shapes = False
            for layout in profile["layouts"]:
                assert "shapes" in layout, f"Layout should have shapes"
                if len(layout.get("shapes", [])) > 0:
                    has_shapes = True
            assert has_shapes, "At least one layout should have shapes"
            
            # If HYBRID_VISION_ENABLED, check for vision labels
            if get_env_flag("HYBRID_VISION_ENABLED"):
                has_vision_labels = False
                for layout in profile["layouts"]:
                    for shape in layout.get("shapes", []):
                        if "vision" in shape or "vision_role" in shape or "place_content" in shape:
                            has_vision_labels = True
                            break
                    if has_vision_labels:
                        break
                
                assert has_vision_labels, "With HYBRID_VISION_ENABLED=true, at least one shape should have vision labels"
            
            # If ARCHETYPE_ALIGNMENT_ENABLED, check for archetype hints
            if get_env_flag("ARCHETYPE_ALIGNMENT_ENABLED"):
                has_archetype = False
                for layout in profile["layouts"]:
                    if "archetype_hint" in layout and layout["archetype_hint"]:
                        has_archetype = True
                        print(f"Found archetype: {layout['archetype_hint']} in layout {layout.get('name', 'unnamed')}")
                        break
                
                assert has_archetype, "With ARCHETYPE_ALIGNMENT_ENABLED=true, at least one layout should have archetype_hint"
            
            print(f"✓ Successfully uploaded template: {template_id}")
            print(f"✓ Profile contains {len(profile['layouts'])} layouts")
            
        finally:
            # Clean up
            pptx_path.unlink(missing_ok=True)
    
    def test_profile_structure(self):
        """Test the structure of the template profile"""
        # Create and upload fixture
        pptx_path = create_fixture_pptx()
        
        try:
            response = self.client.ingest_template(pptx_path)
            template_id = response["template_id"]
            profile = self.client.get_template_profile(template_id)
            
            # Check profile structure
            assert "template_id" in profile or template_id, "Profile should reference template"
            assert "layouts" in profile, "Profile should have layouts"
            
            # Check layout structure
            for layout in profile["layouts"]:
                assert "layout_id" in layout or "id" in layout, "Layout should have ID"
                assert "name" in layout, "Layout should have name"
                assert "shapes" in layout, "Layout should have shapes"
                
                # Check shape structure
                for shape in layout["shapes"]:
                    # Should have some identifier
                    assert any(k in shape for k in ["id", "shape_id", "idx"]), "Shape should have identifier"
                    # Should have type information
                    assert any(k in shape for k in ["ph_type", "type", "placeholder_type"]), "Shape should have type"
                    
                    # If safety map enabled, check for safety info
                    if get_env_flag("SAFETY_MAP_ENABLED"):
                        if "safety_penalty" in shape:
                            assert isinstance(shape["safety_penalty"], (int, float)), "Safety penalty should be numeric"
                            assert 0 <= shape["safety_penalty"] <= 1, "Safety penalty should be between 0 and 1"
            
            print(f"✓ Profile structure validated successfully")
            
        finally:
            pptx_path.unlink(missing_ok=True)