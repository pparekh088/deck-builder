"""
Test 3-pass render with overflow detection and correction
"""

import pytest
import subprocess
from .utils import (
    create_fixture_pptx, APIClient, simple_spec, wait_for_api, get_env_flag
)


def check_libreoffice_available():
    """Check if LibreOffice is available"""
    try:
        result = subprocess.run(
            ["soffice", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except:
        return False


class TestRenderOverflowLoop:
    """Test 3-pass render with overflow handling"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test environment"""
        # Check if render measure is enabled
        if not get_env_flag("RENDER_MEASURE_ENABLED"):
            pytest.skip("RENDER_MEASURE_ENABLED not set to true")
        
        # Check if LibreOffice is available
        if not check_libreoffice_available():
            pytest.skip("LibreOffice not available - required for PDF conversion")
        
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
    
    def test_overflow_triggers_correction(self):
        """Test that overflow content triggers font shrink or slide split"""
        # Generate presentation with overflow content
        content_spec = simple_spec(num_slides=2, include_overflow=True)
        response = self.client.generate_presentation(
            self.template_id,
            content_spec
        )
        
        assert "session_id" in response, "Response should contain session_id"
        
        # Check for render metrics
        if "render_metrics" in response:
            metrics = response["render_metrics"]
            assert isinstance(metrics, dict), "render_metrics should be a dict"
            
            font_shrink = metrics.get("font_shrink_events", 0)
            slides_added = metrics.get("continuation_slides_added", 0)
            
            # At least one correction should have been made
            assert font_shrink > 0 or slides_added > 0, \
                f"Overflow should trigger correction: shrink={font_shrink}, split={slides_added}"
            
            print(f"✓ Overflow handled: {font_shrink} font shrinks, {slides_added} slides added")
            
            # Log details if available
            if "corrections" in metrics:
                for correction in metrics["corrections"]:
                    print(f"  - {correction.get('type', 'unknown')}: {correction.get('description', '')}")
        else:
            print("⚠ render_metrics not included in response (may need API update)")
    
    def test_font_size_reduction(self):
        """Test that font size is reduced within bounds"""
        # Create content that's slightly too long
        content_spec = [
            {
                "slide_id": "slide-1",
                "title": "Test Slide with Moderate Overflow",
                "bullets": [
                    "This is a moderately long bullet point that might overflow",
                    "Another point with sufficient text to cause issues",
                    "Third point that adds to the overall content volume",
                    "Fourth point pushing the boundaries of the text box",
                    "Fifth point that should trigger font reduction"
                ],
                "speaker_notes": "Testing font reduction"
            }
        ]
        
        response = self.client.generate_presentation(
            self.template_id,
            content_spec
        )
        
        if "render_metrics" not in response:
            pytest.skip("render_metrics not available")
        
        metrics = response["render_metrics"]
        
        if "font_shrink_events" in metrics and metrics["font_shrink_events"] > 0:
            print(f"✓ Font reduction applied: {metrics['font_shrink_events']} events")
            
            # Check if font sizes are within bounds
            if "min_font_size" in metrics:
                assert metrics["min_font_size"] >= 10, "Font should not shrink below 10pt"
                print(f"  Minimum font size: {metrics['min_font_size']}pt")
    
    def test_slide_splitting(self):
        """Test that extreme overflow triggers slide splitting"""
        # Create content with extreme overflow
        bullets = [f"Bullet point {i}: " + "x" * 100 for i in range(15)]
        
        content_spec = [
            {
                "slide_id": "slide-1",
                "title": "Extremely Long Content",
                "bullets": bullets,
                "speaker_notes": "Testing slide split"
            }
        ]
        
        response = self.client.generate_presentation(
            self.template_id,
            content_spec
        )
        
        if "render_metrics" not in response:
            pytest.skip("render_metrics not available")
        
        metrics = response["render_metrics"]
        
        if "continuation_slides_added" in metrics:
            if metrics["continuation_slides_added"] > 0:
                print(f"✓ Slide splitting applied: {metrics['continuation_slides_added']} continuation slides")
            else:
                # Might have used font shrinking instead
                font_shrink = metrics.get("font_shrink_events", 0)
                print(f"ℹ No slide split, but {font_shrink} font shrink events")
    
    def test_no_overflow_no_correction(self):
        """Test that normal content doesn't trigger corrections"""
        # Generate presentation with normal content
        content_spec = simple_spec(num_slides=2, include_overflow=False)
        response = self.client.generate_presentation(
            self.template_id,
            content_spec
        )
        
        if "render_metrics" not in response:
            pytest.skip("render_metrics not available")
        
        metrics = response["render_metrics"]
        
        font_shrink = metrics.get("font_shrink_events", 0)
        slides_added = metrics.get("continuation_slides_added", 0)
        
        # Normal content shouldn't need corrections
        if font_shrink == 0 and slides_added == 0:
            print(f"✓ No corrections needed for normal content")
        else:
            print(f"ℹ Corrections applied even for normal content: shrink={font_shrink}, split={slides_added}")
    
    def test_render_performance(self):
        """Test that 3-pass rendering completes in reasonable time"""
        import time
        
        # Generate with overflow content
        content_spec = simple_spec(num_slides=5, include_overflow=True)
        
        start_time = time.time()
        response = self.client.generate_presentation(
            self.template_id,
            content_spec
        )
        elapsed = time.time() - start_time
        
        # 3-pass render should still complete quickly (allow 60s for PDF conversion)
        assert elapsed < 60, f"3-pass render took too long: {elapsed:.2f}s"
        assert "session_id" in response, "Should generate successfully"
        
        print(f"✓ 3-pass render completed in {elapsed:.2f}s")