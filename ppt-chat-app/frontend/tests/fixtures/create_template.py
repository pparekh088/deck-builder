#!/usr/bin/env python3
"""
Create a minimal PPTX template for E2E testing
"""

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN
from pptx.dml.color import RGBColor
import os

def create_minimal_template():
    """Create a minimal PPTX template with basic layouts"""
    prs = Presentation()
    
    # Set slide size (16:9)
    prs.slide_width = Inches(10)
    prs.slide_height = Inches(5.625)
    
    # Create title slide
    title_slide_layout = prs.slide_layouts[0]
    slide = prs.slides.add_slide(title_slide_layout)
    
    title = slide.shapes.title
    subtitle = slide.placeholders[1]
    
    title.text = "Test Template"
    subtitle.text = "E2E Testing"
    
    # Add a simple shape for visual interest
    left = Inches(0)
    top = Inches(0)
    width = prs.slide_width
    height = Inches(0.3)
    
    shape = slide.shapes.add_shape(
        1,  # Rectangle
        left, top, width, height
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = RGBColor(0, 102, 204)
    shape.line.fill.background()
    
    # Add content slide
    bullet_slide_layout = prs.slide_layouts[1]
    slide2 = prs.slides.add_slide(bullet_slide_layout)
    
    title = slide2.shapes.title
    title.text = "Content Layout"
    
    # Save the template
    output_path = os.path.join(os.path.dirname(__file__), 'template_min.pptx')
    prs.save(output_path)
    print(f"Created minimal template: {output_path}")
    return output_path

if __name__ == "__main__":
    create_minimal_template()