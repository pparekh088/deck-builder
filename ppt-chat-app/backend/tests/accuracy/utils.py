"""
Test utilities for accuracy validation suite
"""

import os
import tempfile
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
import httpx
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN
from pptx.dml.color import RGBColor


def create_fixture_pptx(
    output_path: Optional[Path] = None,
    include_decor: bool = True,
    include_two_column: bool = True
) -> Path:
    """
    Generate a small fixture PPTX with optional decor band and two-column layout
    
    Args:
        output_path: Where to save the PPTX (uses temp if None)
        include_decor: Add decorative header/footer bands
        include_two_column: Add a two-column layout
    
    Returns:
        Path to the created PPTX file
    """
    prs = Presentation()
    
    # Set slide size (16:9)
    prs.slide_width = Inches(10)
    prs.slide_height = Inches(5.625)
    
    # Layout 0: Title Slide
    title_layout = prs.slide_layouts[0]
    slide1 = prs.slides.add_slide(title_layout)
    title = slide1.shapes.title
    subtitle = slide1.placeholders[1]
    title.text = "Test Presentation"
    subtitle.text = "Accuracy++ Validation"
    
    # Add decorative band if requested
    if include_decor:
        # Add header band (decorative)
        left = Inches(0)
        top = Inches(0)
        width = prs.slide_width
        height = Inches(0.5)
        shape = slide1.shapes.add_shape(
            1,  # Rectangle
            left, top, width, height
        )
        shape.fill.solid()
        shape.fill.fore_color.rgb = RGBColor(0, 51, 102)  # Dark blue
        shape.line.fill.background()
        
        # Add logo placeholder in corner
        logo_left = prs.slide_width - Inches(1.5)
        logo_top = Inches(0.1)
        logo_width = Inches(1.2)
        logo_height = Inches(0.3)
        logo = slide1.shapes.add_textbox(logo_left, logo_top, logo_width, logo_height)
        logo.text_frame.text = "LOGO"
        logo.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER
        
        # Add footer band
        footer_top = prs.slide_height - Inches(0.4)
        footer_height = Inches(0.4)
        footer = slide1.shapes.add_shape(
            1,  # Rectangle
            left, footer_top, width, footer_height
        )
        footer.fill.solid()
        footer.fill.fore_color.rgb = RGBColor(200, 200, 200)  # Light gray
        footer.line.fill.background()
    
    # Layout 1: Title and Content
    content_layout = prs.slide_layouts[1] if len(prs.slide_layouts) > 1 else prs.slide_layouts[0]
    slide2 = prs.slides.add_slide(content_layout)
    title = slide2.shapes.title
    title.text = "Content Slide"
    
    # Add bullet points
    if len(slide2.placeholders) > 1:
        body = slide2.placeholders[1]
        tf = body.text_frame
        tf.text = "First bullet point"
        p = tf.add_paragraph()
        p.text = "Second bullet point"
        p.level = 0
        p = tf.add_paragraph()
        p.text = "Third bullet point with more text"
        p.level = 0
    
    # Add two-column layout if requested
    if include_two_column and len(prs.slide_layouts) > 2:
        # Try to use comparison layout or create custom
        two_col_layout = prs.slide_layouts[3] if len(prs.slide_layouts) > 3 else content_layout
        slide3 = prs.slides.add_slide(two_col_layout)
        title = slide3.shapes.title
        title.text = "Two Column Layout"
        
        # Add left column
        left_col = slide3.shapes.add_textbox(
            Inches(0.5), Inches(1.5), Inches(4), Inches(3)
        )
        left_col.text_frame.text = "Left column content"
        
        # Add right column
        right_col = slide3.shapes.add_textbox(
            Inches(5.5), Inches(1.5), Inches(4), Inches(3)
        )
        right_col.text_frame.text = "Right column content"
    
    # Save to file
    if output_path is None:
        temp_file = tempfile.NamedTemporaryFile(suffix='.pptx', delete=False)
        output_path = Path(temp_file.name)
        temp_file.close()
    
    prs.save(str(output_path))
    return output_path


class APIClient:
    """HTTP client for testing the API endpoints"""
    
    def __init__(self, base_url: str = "http://localhost:8006", timeout: int = 30):
        self.base_url = base_url
        self.timeout = timeout
        self.client = httpx.Client(timeout=timeout)
    
    def ingest_template(self, pptx_path: Path) -> Dict[str, Any]:
        """
        Upload a template for ingestion
        
        Args:
            pptx_path: Path to PPTX file
        
        Returns:
            Response with template_id
        """
        with open(pptx_path, 'rb') as f:
            files = {'file': (pptx_path.name, f, 'application/vnd.openxmlformats-officedocument.presentationml.presentation')}
            response = self.client.post(
                f"{self.base_url}/api/template/ingest",
                files=files
            )
            response.raise_for_status()
            return response.json()
    
    def get_template_profile(self, template_id: str) -> Dict[str, Any]:
        """
        Fetch template profile
        
        Args:
            template_id: Template ID from ingestion
        
        Returns:
            Template profile with layouts and shapes
        """
        response = self.client.get(
            f"{self.base_url}/api/template/profile/{template_id}"
        )
        response.raise_for_status()
        return response.json()
    
    def generate_presentation(
        self,
        template_id: str,
        content_spec: List[Dict[str, Any]],
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate a presentation from content spec
        
        Args:
            template_id: Template to use
            content_spec: List of slide specifications
            session_id: Optional session ID
        
        Returns:
            Response with session_id, placements, and render_metrics
        """
        payload = {
            "template_id": template_id,
            "slides": content_spec,
            "session_id": session_id or f"test-session-{int(time.time())}"
        }
        
        # Try the chat endpoint first, then fall back to generate
        try:
            response = self.client.post(
                f"{self.base_url}/api/chat",
                json=payload
            )
            if response.status_code == 404:
                # Try alternative endpoint
                response = self.client.post(
                    f"{self.base_url}/api/generate",
                    json=payload
                )
        except:
            # Try alternative endpoint
            response = self.client.post(
                f"{self.base_url}/api/presentation/generate",
                json=payload
            )
        
        response.raise_for_status()
        return response.json()
    
    def close(self):
        """Close the HTTP client"""
        self.client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def simple_spec(
    num_slides: int = 3,
    include_overflow: bool = False
) -> List[Dict[str, Any]]:
    """
    Generate a simple content specification for testing
    
    Args:
        num_slides: Number of slides to generate
        include_overflow: Add extra long content to trigger overflow
    
    Returns:
        List of slide specifications
    """
    slides = []
    
    # Slide 1: Title slide
    slides.append({
        "slide_id": "slide-1",
        "title": "Test Presentation Title",
        "subtitle": "Accuracy Validation Suite",
        "bullets": [],
        "speaker_notes": "Introduction slide"
    })
    
    # Slide 2: Content slide
    bullets = [
        "First key point about the topic",
        "Second important consideration",
        "Third aspect to discuss"
    ]
    
    if include_overflow:
        # Add many more bullets to trigger overflow
        bullets.extend([
            "Fourth point with additional details that make the text longer",
            "Fifth consideration that requires extensive explanation and context",
            "Sixth item in our comprehensive list of important topics",
            "Seventh point that continues our detailed exploration",
            "Eighth consideration with multiple sub-points to consider",
            "Ninth aspect requiring careful analysis and thought",
            "Tenth and final point wrapping up our extensive discussion"
        ])
    
    slides.append({
        "slide_id": "slide-2",
        "title": "Key Points",
        "bullets": bullets,
        "speaker_notes": "Main content slide"
    })
    
    # Add more slides if requested
    for i in range(3, num_slides + 1):
        slides.append({
            "slide_id": f"slide-{i}",
            "title": f"Additional Topic {i-2}",
            "bullets": [
                f"Point A for topic {i-2}",
                f"Point B for topic {i-2}",
                f"Point C for topic {i-2}"
            ],
            "speaker_notes": f"Details for slide {i}"
        })
    
    return slides


def wait_for_api(base_url: str = "http://localhost:8006", max_wait: int = 30) -> bool:
    """
    Wait for API to be available
    
    Args:
        base_url: API base URL
        max_wait: Maximum seconds to wait
    
    Returns:
        True if API is available, False if timeout
    """
    start = time.time()
    while time.time() - start < max_wait:
        try:
            response = httpx.get(f"{base_url}/health", timeout=2)
            if response.status_code == 200:
                return True
        except:
            pass
        time.sleep(1)
    return False


def get_env_flag(flag_name: str, default: bool = False) -> bool:
    """
    Get boolean environment flag
    
    Args:
        flag_name: Name of the environment variable
        default: Default value if not set
    
    Returns:
        Boolean value of the flag
    """
    value = os.getenv(flag_name, str(default)).lower()
    return value in ('true', '1', 'yes', 'on')