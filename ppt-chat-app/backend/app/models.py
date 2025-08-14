from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

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