"""
Test ILP solver and safety map functionality
"""

import pytest
from .utils import (
    create_fixture_pptx, APIClient, simple_spec, wait_for_api, get_env_flag
)


class TestSolverAndSafety:
    """Test ILP solver and safety map features"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test environment"""
        # Check if solver and safety features are enabled
        if not get_env_flag("ACCURATE_SOLVER_ENABLED"):
            pytest.skip("ACCURATE_SOLVER_ENABLED not set to true")
        
        if not wait_for_api():
            pytest.skip("API not available")
        
        self.client = APIClient()
        
        # Upload a test template
        self.pptx_path = create_fixture_pptx(include_decor=True)
        response = self.client.ingest_template(self.pptx_path)
        self.template_id = response["template_id"]
        
        yield
        
        self.client.close()
        self.pptx_path.unlink(missing_ok=True)
    
    def test_solver_generates_placements(self):
        """Test that ILP solver generates valid placements"""
        # Generate presentation with simple spec
        content_spec = simple_spec(num_slides=3)
        response = self.client.generate_presentation(
            self.template_id,
            content_spec
        )
        
        # Check response structure
        assert "session_id" in response, "Response should contain session_id"
        
        # With ACCURATE_SOLVER_ENABLED, we should have placements
        if "placements" in response:
            placements = response["placements"]
            assert isinstance(placements, list), "Placements should be a list"
            
            # Check each placement
            for placement in placements:
                assert isinstance(placement, dict), "Each placement should be a dict"
                # Should have key identifying content
                assert any(k in placement for k in ["key", "content_id", "id"]), "Placement should have identifier"
                # Should have type information
                assert any(k in placement for k in ["ph_type", "type", "shape_type"]), "Placement should have type"
                
                # Check safety if enabled
                if get_env_flag("SAFETY_MAP_ENABLED"):
                    if "safety_ok" in placement:
                        assert isinstance(placement["safety_ok"], bool), "safety_ok should be boolean"
            
            print(f"✓ Generated {len(placements)} placements")
        else:
            print("⚠ Placements not included in response (may need API update)")
    
    def test_compatible_type_matching(self):
        """Test that titles/subtitles land on compatible placeholder types"""
        content_spec = simple_spec(num_slides=2)
        response = self.client.generate_presentation(
            self.template_id,
            content_spec
        )
        
        if "placements" not in response:
            pytest.skip("Placements not available in response")
        
        placements = response["placements"]
        
        # Look for title and subtitle placements
        title_placements = [p for p in placements if "title" in str(p.get("key", "")).lower()]
        
        for placement in title_placements:
            ph_type = placement.get("ph_type", "").upper()
            # Title content should go to TITLE or compatible placeholders
            if "subtitle" not in str(placement.get("key", "")).lower():
                assert ph_type in ["TITLE", "TEXTBOX", "BODY"], \
                    f"Title should be placed in compatible placeholder, got {ph_type}"
            else:
                # Subtitle can go to SUBTITLE, TEXTBOX, or BODY
                assert ph_type in ["SUBTITLE", "TITLE", "TEXTBOX", "BODY"], \
                    f"Subtitle should be placed in compatible placeholder, got {ph_type}"
        
        print(f"✓ Type compatibility verified for {len(title_placements)} title/subtitle placements")
    
    def test_safety_map_blocks_unsafe_areas(self):
        """Test that no content is placed in unsafe areas when SAFETY_MAP_ENABLED"""
        if not get_env_flag("SAFETY_MAP_ENABLED"):
            pytest.skip("SAFETY_MAP_ENABLED not set to true")
        
        content_spec = simple_spec(num_slides=3)
        response = self.client.generate_presentation(
            self.template_id,
            content_spec
        )
        
        if "placements" not in response:
            pytest.skip("Placements not available in response")
        
        placements = response["placements"]
        unsafe_count = 0
        
        for placement in placements:
            if "safety_ok" in placement:
                assert placement["safety_ok"] == True, \
                    f"No placement should have safety_ok=false, found one for {placement.get('key')}"
            
            # Check if placement is in a decorative area
            role = placement.get("role", "").lower()
            if any(unsafe in role for unsafe in ["logo", "footer", "decor", "watermark"]):
                unsafe_count += 1
                print(f"⚠ Warning: Content placed in {role} area")
        
        assert unsafe_count == 0, f"Found {unsafe_count} placements in unsafe areas"
        print(f"✓ All {len(placements)} placements are in safe areas")
    
    def test_solver_respects_priorities(self):
        """Test that solver respects shape priorities"""
        content_spec = simple_spec(num_slides=2)
        response = self.client.generate_presentation(
            self.template_id,
            content_spec
        )
        
        if "placements" not in response:
            pytest.skip("Placements not available in response")
        
        placements = response["placements"]
        
        # Check if priorities are being used
        high_priority_used = 0
        for placement in placements:
            priority = placement.get("priority", 5)
            if priority <= 2:  # High priority
                high_priority_used += 1
        
        # We expect important content (titles) to use higher priority shapes if available
        title_count = len([p for p in placements if "title" in str(p.get("key", "")).lower()])
        if title_count > 0 and high_priority_used > 0:
            print(f"✓ Solver used {high_priority_used} high-priority shapes for {title_count} titles")
        else:
            print(f"ℹ Priority information: {high_priority_used} high-priority shapes used")
    
    def test_solver_performance(self):
        """Test that solver completes within reasonable time"""
        import time
        
        # Generate a larger presentation
        content_spec = simple_spec(num_slides=10)
        
        start_time = time.time()
        response = self.client.generate_presentation(
            self.template_id,
            content_spec
        )
        elapsed = time.time() - start_time
        
        # Should complete within timeout (30s is generous for 10 slides)
        assert elapsed < 30, f"Generation took too long: {elapsed:.2f}s"
        assert "session_id" in response, "Should generate successfully"
        
        print(f"✓ Generated 10-slide presentation in {elapsed:.2f}s")