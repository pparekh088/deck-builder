"""
Vision-related models for hybrid template analysis
"""

from pydantic import BaseModel, Field
from typing import Literal, Optional, Dict, List
from datetime import datetime

# Vision role enumeration
VisionRole = Literal[
    "Title", "Subtitle", "Bullets", "Paragraph", 
    "Table", "Chart", "HeroImage", "Logo", 
    "Number", "SectionHeader", "Footer", "Decor", "Unknown"
]

# Layout intent enumeration
LayoutIntent = Literal[
    "TitleSlide", "Agenda", "Bullets", "TwoColumn", "Comparison",
    "SectionHeader", "ImageLeftTextRight", "ImageRightTextLeft",
    "Quote", "Table", "Chart", "Unknown"
]

class ShapeVisionLabel(BaseModel):
    """Vision-based label for a shape in a layout"""
    shape_id: str
    role: VisionRole
    place_content: bool = True  # Whether safe to place user content
    priority: int = 0  # Visual priority (1 = highest)
    confidence: float = 0.0  # Model confidence 0-1
    notes: Optional[str] = None  # Optional hints

class LayoutVisionLabels(BaseModel):
    """Vision labels for all shapes in a layout"""
    template_id: str
    master_idx: int
    layout_idx: int
    intent: LayoutIntent = "Unknown"
    labels: List[ShapeVisionLabel] = Field(default_factory=list)
    
class VisionAnalysisResult(BaseModel):
    """Result from vision analysis of a layout"""
    intent: LayoutIntent
    shapes: List[Dict] = Field(default_factory=list)
    
class LayoutPreviewMetadata(BaseModel):
    """Metadata for a rendered layout preview"""
    master_idx: int
    layout_idx: int
    width_px: int
    height_px: int
    dpi: int = 192
    slide_width_emu: int  # EMU units
    slide_height_emu: int
    
class TemplateVisionProfile(BaseModel):
    """Complete vision analysis results for a template"""
    template_id: str
    layouts: List[LayoutVisionLabels] = Field(default_factory=list)
    coverage_stats: Dict[str, float] = Field(default_factory=dict)
    analyzed_at: datetime = Field(default_factory=datetime.now)