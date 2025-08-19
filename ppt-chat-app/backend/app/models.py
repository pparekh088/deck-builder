from pydantic import BaseModel
from typing import Optional, List, Dict, Any, TYPE_CHECKING
from datetime import datetime
from enum import Enum

# Import vision models only for type checking to avoid circular imports
if TYPE_CHECKING:
    from app.vision_models.vision import ShapeVisionLabel, VisionRole
else:
    # Runtime placeholders to avoid import errors
    ShapeVisionLabel = Dict[str, Any]
    VisionRole = str

class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"

class ChatMessage(BaseModel):
    role: MessageRole
    content: str
    timestamp: datetime = datetime.now()

class ChatRequest(BaseModel):
    message: str
    session_id: str
    context: Optional[List[ChatMessage]] = []

class ChatResponse(BaseModel):
    response: str
    markdown_content: str
    session_id: str
    preview_available: bool = False
    preview_url: Optional[str] = None
    # New fields for accuracy validation (non-breaking additions)
    placements: Optional[List[Dict[str, Any]]] = None
    render_metrics: Optional[Dict[str, Any]] = None

class TemplateUploadResponse(BaseModel):
    success: bool
    message: str
    template_id: str
    template_name: str
    thumbnail_url: Optional[str] = None

class SessionInfo(BaseModel):
    session_id: str
    template_id: Optional[str] = None
    template_name: Optional[str] = None
    chat_history: List[ChatMessage] = []
    current_markdown: str = ""
    # How to compose this session by default: 'edit' or 'replace'
    composition_mode: str = "replace"
    created_at: datetime = datetime.now()
    updated_at: datetime = datetime.now()

class SlidePreview(BaseModel):
    slide_number: int
    title: str
    content: str
    image_url: Optional[str] = None

class PresentationPreview(BaseModel):
    session_id: str
    slides: List[SlidePreview]
    total_slides: int
    generated_at: datetime

class DownloadResponse(BaseModel):
    success: bool
    download_url: str
    filename: str
    size_bytes: int

class WebSocketMessage(BaseModel):
    type: str  # "chat", "preview_update", "error", "status"
    data: Dict[str, Any]
    timestamp: datetime = datetime.now()

# ============= New Agentic Models =============

class PlaceholderType(str, Enum):
    TITLE = "title"
    BODY = "body"
    PICTURE = "picture"
    TABLE = "table"
    CHART = "chart"
    SUBTITLE = "subtitle"
    FOOTER = "footer"
    HEADER = "header"
    DATE = "date"
    SLIDE_NUMBER = "slide_number"
    CONTENT = "content"  # Generic content placeholder

class PlaceholderInfo(BaseModel):
    """Information about a placeholder in a slide layout"""
    idx: int  # Placeholder index
    type: PlaceholderType
    name: Optional[str] = None
    is_vertical: bool = False
    width: Optional[float] = None  # In inches
    height: Optional[float] = None  # In inches
    left: Optional[float] = None  # Position from left in inches
    top: Optional[float] = None  # Position from top in inches
    # Vision-based labeling
    vision: Optional["ShapeVisionLabel"] = None
    # Additional metadata
    alt_text: Optional[str] = None
    tags: List[str] = []  # Designer tags from name/alt_text
    bbox_emu: Optional[Dict[str, int]] = None  # {left, top, width, height} in EMU
    bbox_px: Optional[Dict[str, int]] = None  # {left, top, width, height} in pixels
    z_order: Optional[int] = None  # Z-order for layering
    # Safety map annotations
    safety_penalty: float = 0.0
    place_ok: bool = True

class SlideLayoutSignature(BaseModel):
    """Signature of a slide layout from the template"""
    layout_id: int
    name: str
    placeholders: List[PlaceholderInfo]
    notes: Optional[str] = None
    # Encoded safety mask for this layout (if generated)
    safety_mask: Optional[str] = None
    
    def has_placeholder_type(self, placeholder_type: PlaceholderType) -> bool:
        return any(p.type == placeholder_type for p in self.placeholders)
    
    def count_placeholder_type(self, placeholder_type: PlaceholderType) -> int:
        return sum(1 for p in self.placeholders if p.type == placeholder_type)

class ThemeInfo(BaseModel):
    """Theme information extracted from template"""
    font_scheme: Dict[str, str] = {}  # major/minor fonts
    color_scheme: Dict[str, str] = {}  # theme colors
    default_font_size: Optional[int] = None
    bullet_styles: List[str] = []

class BrandAsset(BaseModel):
    """Brand assets detected in template"""
    type: str  # "logo", "watermark", "footer", etc.
    slide_indices: List[int]  # Which slides contain this asset
    position: Optional[Dict[str, float]] = None  # Position info

class TemplateProfile(BaseModel):
    """Complete profile of the analyzed template"""
    template_id: str
    layout_catalog: List[SlideLayoutSignature]
    theme: ThemeInfo
    brand_assets: List[BrandAsset] = []
    slide_width: float  # In inches
    slide_height: float  # In inches
    analyzed_at: datetime = datetime.now()
    # Vision analysis metadata
    vision_enabled: bool = False
    vision_coverage: float = 0.0  # % of shapes with vision labels
    # Whether safety maps have been generated and attached
    safety_maps_enabled: bool = False
    
    def get_layout_by_id(self, layout_id: int) -> Optional[SlideLayoutSignature]:
        return next((l for l in self.layout_catalog if l.layout_id == layout_id), None)
    
    def get_layouts_with_placeholder(self, placeholder_type: PlaceholderType) -> List[SlideLayoutSignature]:
        return [l for l in self.layout_catalog if l.has_placeholder_type(placeholder_type)]
    
    def get_layouts_with_vision_role(self, role: "VisionRole") -> List[SlideLayoutSignature]:
        """Get layouts containing shapes with specific vision role"""
        layouts = []
        for layout in self.layout_catalog:
            for placeholder in layout.placeholders:
                # Handle both dict and object forms
                if placeholder.vision:
                    vision_role = placeholder.vision.get('role') if isinstance(placeholder.vision, dict) else getattr(placeholder.vision, 'role', None)
                    if vision_role == role:
                        layouts.append(layout)
                        break
        return layouts

class SlideContentNeeds(BaseModel):
    """What content a slide needs"""
    has_picture: bool = False
    has_table: Optional[Dict[str, Any]] = None  # {rows: int, cols: int, headers: List[str]}
    has_chart: Optional[Dict[str, Any]] = None  # {type: str, series: List, categories: List}
    has_multiple_content_areas: bool = False
    estimated_bullet_count: int = 0

class SlideSpec(BaseModel):
    """Specification for a single slide from the plan"""
    slide_id: str  # Unique ID for this slide spec
    title: str
    bullets: List[str] = []
    speaker_notes: Optional[str] = None
    needs: SlideContentNeeds = SlideContentNeeds()
    
class PresentationPlan(BaseModel):
    """The complete presentation plan generated by LLM"""
    session_id: str
    slides: List[SlideSpec]
    metadata: Dict[str, Any] = {}  # Additional metadata
    created_at: datetime = datetime.now()

class SlideMapping(BaseModel):
    """Maps a slide spec to a template layout"""
    slide_spec_id: str
    layout_id: int
    layout_name: str
    confidence_score: float  # 0-1, how well the layout matches needs
    adaptations_needed: List[str] = []  # What changes are needed to fit

class SlideComposition(BaseModel):
    """Result of composing a slide"""
    slide_spec_id: str
    layout_id: int
    success: bool
    issues: List[str] = []
    overflow_text: Optional[str] = None
    missing_placeholders: List[str] = []

class ValidationIssue(BaseModel):
    """Issues found during validation"""
    slide_number: int
    issue_type: str  # "overflow", "missing_placeholder", "layout_mismatch", etc.
    description: str
    severity: str  # "error", "warning", "info"
    suggested_fix: Optional[str] = None

class RepairAction(BaseModel):
    """Action to repair a validation issue"""
    slide_number: int
    action_type: str  # "split", "condense", "change_layout", "merge"
    parameters: Dict[str, Any]
    
class GenerationStatus(BaseModel):
    """Status of the presentation generation process"""
    session_id: str
    stage: str  # "analyzing", "planning", "matching", "composing", "validating", "complete"
    progress: float  # 0-100
    current_action: str
    issues: List[ValidationIssue] = []
    timestamp: datetime = datetime.now()