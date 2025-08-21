from fastapi import FastAPI, HTTPException, UploadFile, File, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import os
import json
import asyncio
from typing import Dict, Optional, List
from datetime import datetime
import logging
from pathlib import Path

from app.config import settings
from app.models import (
    ChatRequest, ChatResponse, TemplateUploadResponse,
    SessionInfo, ChatMessage, MessageRole, PresentationPreview,
    DownloadResponse, WebSocketMessage, GenerationStatus,
    TemplateProfile, PresentationPlan, SlideMapping, ValidationIssue
)
from app.services.openai_service import openai_service
from app.services.ppt_service import ppt_service
from app.services.session_service import session_service
from app.services.template_analyzer import template_analyzer
from app.services.slide_planner import slide_planner
from app.services.layout_matcher import layout_matcher
from app.services.slide_composer import slide_composer
from app.services.presentation_validator import presentation_validator
from app.services.mcp_client import mcp_client

# Import the template routes (disabled for now - missing dependencies)
# from app.api.routes.template import router as template_router

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="PowerPoint Chat Generator",
    description="Generate PowerPoint presentations using AI chat",
    version="2.0.0"  # Updated version for agentic system
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include the template router
# app.include_router(template_router)  # Disabled - missing dependencies

# Mount static files for serving generated files
if not os.path.exists(settings.upload_dir):
    os.makedirs(settings.upload_dir)
app.mount("/static", StaticFiles(directory=settings.upload_dir), name="static")

# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    """Initialize MCP client connection on startup"""
    try:
        await mcp_client.connect()
        logger.info("MCP client connected successfully")
    except Exception as e:
        logger.warning(f"Failed to connect MCP client on startup: {e}")
        # Continue running even if MCP connection fails initially

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up MCP client connection on shutdown"""
    try:
        await mcp_client.disconnect()
        logger.info("MCP client disconnected successfully")
    except Exception as e:
        logger.error(f"Error disconnecting MCP client: {e}")

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections[session_id] = websocket
        logger.info(f"WebSocket connected for session: {session_id}")
    
    def disconnect(self, session_id: str):
        if session_id in self.active_connections:
            del self.active_connections[session_id]
            logger.info(f"WebSocket disconnected for session: {session_id}")
    
    async def send_message(self, session_id: str, message: dict):
        if session_id in self.active_connections:
            try:
                await self.active_connections[session_id].send_json(message)
            except Exception as e:
                logger.error(f"Error sending WebSocket message: {str(e)}")
                self.disconnect(session_id)
    
    async def broadcast(self, message: dict):
        for session_id in list(self.active_connections.keys()):
            await self.send_message(session_id, message)

manager = ConnectionManager()

# API Endpoints

@app.get("/")
async def root():
    return {"message": "PowerPoint Chat Generator API", "version": "2.0.0", "agentic": True}

@app.post("/api/session/create")
async def create_session():
    """Create a new chat session"""
    session_id = session_service.create_session()
    return {"session_id": session_id, "created": True}

@app.get("/api/session/{session_id}")
async def get_session(session_id: str):
    """Get session information"""
    session = session_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session

@app.post("/api/template/upload")
async def upload_template(
    session_id: str,
    file: UploadFile = File(...)
):
    """Upload a PowerPoint template and analyze it"""
    if not file.filename.endswith(('.pptx', '.ppt')):
        raise HTTPException(status_code=400, detail="File must be a PowerPoint file")
    
    try:
        # Save template
        content = await file.read()
        template_id = ppt_service.save_template(content, file.filename, session_id)
        
        # Update session
        session_service.set_template(session_id, template_id, file.filename)
        
        # Analyze template asynchronously
        template_path = Path(settings.templates_dir) / f"{template_id}.pptx"
        asyncio.create_task(analyze_template_background(session_id, template_path, template_id))
        
        # Send WebSocket notification
        await manager.send_message(session_id, {
            "type": "template_uploaded",
            "data": {
                "template_id": template_id,
                "template_name": file.filename,
                "status": "analyzing"
            }
        })
        
        return TemplateUploadResponse(
            success=True,
            message="Template uploaded successfully. Analysis in progress.",
            template_id=template_id,
            template_name=file.filename
        )
        
    except Exception as e:
        logger.error(f"Error uploading template: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def analyze_template_background(session_id: str, template_path: Path, template_id: str):
    """Background task to analyze template"""
    try:
        # Analyze template
        profile = await template_analyzer.analyze_template(template_path, template_id)
        
        # Save profile to session
        session_service.save_template_profile(session_id, profile)
        
        # Send WebSocket notification with profile
        await manager.send_message(session_id, {
            "type": "template_profile",
            "data": {
                "template_id": template_id,
                "layout_count": len(profile.layout_catalog),
                "layouts": [
                    {
                        "id": layout.layout_id,
                        "name": layout.name,
                        "placeholders": [p.type.value for p in layout.placeholders]
                    }
                    for layout in profile.layout_catalog
                ],
                "theme": profile.theme.model_dump()
            }
        })
        
        logger.info(f"Template analysis complete for session {session_id}")
        
    except Exception as e:
        logger.error(f"Error analyzing template: {str(e)}")
        await manager.send_message(session_id, {
            "type": "error",
            "data": {"message": f"Template analysis failed: {str(e)}"}
        })

@app.get("/api/template/profile/{session_id}")
async def get_template_profile(session_id: str):
    """Get the analyzed template profile for a session"""
    profile = session_service.get_template_profile(session_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Template profile not found")
    return profile

@app.post("/api/chat")
async def chat(request: ChatRequest):
    """Process chat message and generate presentation with agentic system"""
    try:
        # Get session
        session = session_service.get_session(request.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Add user message to history
        user_message = ChatMessage(role=MessageRole.USER, content=request.message)
        session_service.add_chat_message(request.session_id, user_message)
        
        # Get template profile if available
        template_profile = session_service.get_template_profile(request.session_id)
        
        # Send status update
        await manager.send_message(request.session_id, {
            "type": "status",
            "data": {"stage": "planning", "message": "Creating presentation plan..."}
        })
        
        if template_profile:
            # Use NEW agentic system only
            from app.services.presentation_agent import presentation_agent
            
            # Check if presentation already exists (for edit mode)
            existing_presentation_path = Path(settings.upload_dir) / f"{request.session_id}_presentation.pptx"
            template_path = Path(settings.templates_dir) / f"{session.template_id}.pptx"
            output_path = Path(settings.upload_dir) / f"{request.session_id}_presentation.pptx"
            
            if not existing_presentation_path.exists():
                existing_presentation_path = template_path
            
            agent_response = await presentation_agent.process_request(
                request.message,
                request.session_id,
                template_profile,
                existing_presentation_path,
                output_path,
                session.chat_history
            )
            
            # Send debug information to frontend
            try:
                debug_info = agent_response["debug_info"]
                logger.info(f"Sending debug info to frontend: {len(debug_info.get('thinking_steps', []))} thinking steps")
                
                # Debug: log the actual message being sent
                debug_message = {
                    "type": "agent_debug",
                    "data": debug_info
                }
                logger.info(f"Debug message structure: {list(debug_message.keys())}")
                logger.info(f"Debug data keys: {list(debug_info.keys())}")
                logger.info(f"Thinking steps count: {len(debug_info.get('thinking_steps', []))}")
                logger.info(f"Actions executed count: {len(debug_info.get('actions_executed', []))}")
                
                # Check if session has active WebSocket connection
                if request.session_id in manager.active_connections:
                    logger.info(f"WebSocket connection found for session {request.session_id}")
                    await manager.send_message(request.session_id, debug_message)
                    logger.info("Debug info sent successfully")
                else:
                    logger.warning(f"No WebSocket connection found for session {request.session_id}")
                    logger.info(f"Active connections: {list(manager.active_connections.keys())}")
            except Exception as e:
                logger.error(f"Failed to send debug info: {e}")
            
            response_text = agent_response["result"]
            markdown = ""  # Agent handles content directly
            preview_url = f"/api/preview/{request.session_id}" if output_path.exists() else None
            # Ensure the composed deck exists for download endpoint
            # generate_with_agentic_system saves to uploads/{session_id}_presentation.pptx
            # So no extra action needed here
        else:
            # Fallback to simple generation
            response_text, markdown = await openai_service.generate_presentation_content(
                request.message,
                session.chat_history,
                session.current_markdown
            )
            
            # Generate preview
            if session.template_id and markdown:
                preview_path = ppt_service.generate_presentation(
                    markdown,
                    session.template_id,
                    request.session_id
                )
                preview_url = f"/api/preview/{request.session_id}"
            else:
                preview_url = None
        
        # Update session with new markdown
        session_service.update_markdown(request.session_id, markdown)
        
        # Add assistant response to history
        assistant_message = ChatMessage(role=MessageRole.ASSISTANT, content=response_text)
        session_service.add_chat_message(request.session_id, assistant_message)
        
        # Collect placements and render metrics if features are enabled
        placements = None
        render_metrics = None
        
        # Get placements if solver is enabled
        if settings.ACCURATE_SOLVER_ENABLED:
            # Try to get placements from session data
            mappings = session_service.get_slide_mappings(request.session_id)
            if mappings:
                placements = []
                for mapping in mappings:
                    if hasattr(mapping, 'content_mapping') and mapping.content_mapping:
                        for content_id, shape_id in mapping.content_mapping.items():
                            placements.append({
                                "key": content_id,
                                "shape_id": shape_id,
                                "ph_type": "BODY",  # Would need to get actual type
                                "safety_ok": True,  # Would need actual safety check
                                "slide_id": mapping.slide_spec_id
                            })
        
        # Get render metrics if measurement is enabled
        if settings.RENDER_MEASURE_ENABLED:
            # Get from session or compositions
            render_metrics = {
                "font_shrink_events": 0,
                "continuation_slides_added": 0
            }
            # Would need to collect actual metrics from render service
        
        # Send WebSocket notification
        await manager.send_message(request.session_id, {
            "type": "chat",
            "data": {
                "response": response_text,
                "markdown": markdown,
                "preview_available": preview_url is not None
            }
        })
        
        return ChatResponse(
            response=response_text,
            markdown_content=markdown,
            session_id=request.session_id,
            preview_available=preview_url is not None,
            preview_url=preview_url,
            placements=placements,
            render_metrics=render_metrics
        )
            
    except Exception as e:
        logger.error(f"Error in chat: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

async def detect_user_intent(user_prompt: str, chat_history: List[ChatMessage]) -> str:
    """Use LLM to detect user intent for presentation composition"""
    try:
        # Build context from chat history
        context = ""
        if chat_history:
            recent_messages = chat_history[-3:]  # Last 3 messages for context
            for msg in recent_messages:
                context += f"{msg.role}: {msg.content}\n"
        
        # Create intent detection prompt
        intent_prompt = f"""
Analyze this user request and determine the intent for PowerPoint presentation management.

Chat Context:
{context}

Current User Request: "{user_prompt}"

Determine the intent from these options:

1. "edit" - User wants to modify existing slides or add content to existing slides
   Examples: 
   - "edit slide 2"
   - "update the roadmap" 
   - "add agentic ai in the roadmap slide"
   - "change the title of slide 3"
   - "add more bullets to the benefits slide"
   - "modify the conclusion"
   - "add X to the Y slide"

2. "delete" - User wants to remove specific slides
   Examples:
   - "delete slide 3"
   - "remove the last slide"
   - "drop slide 2"

3. "replace" - User wants to create a completely new presentation from scratch
   Examples:
   - "create 5 slides about AI"
   - "make a presentation on finance"
   - "generate slides on blockchain"
   - "build a deck about marketing"

Key Rules:
- If user references existing slide content (roadmap, benefits, conclusion, etc.) AND wants to add/modify → "edit"
- If user says "add X to Y slide" or "add X in the Y" → "edit" 
- If user mentions specific slide numbers or slide names → "edit"
- If user wants to remove slides → "delete"
- If user wants entirely new content without referencing existing slides → "replace"
- When in doubt between edit and replace, choose "edit" if there's any reference to existing content

Respond with only one word: edit, delete, or replace
"""

        # Call OpenAI for intent detection
        response = await openai_service.get_completion([
            {"role": "system", "content": "You are an expert at understanding user intent for presentation management. Respond with only one word."},
            {"role": "user", "content": intent_prompt}
        ])
        
        intent = response.strip().lower()
        if intent not in ["edit", "delete", "replace"]:
            intent = "replace"  # Default fallback

        logger.info(f"LLM Intent detected: {intent.upper()} based on prompt: {user_prompt[:100]}")
        return intent
        
    except Exception as e:
        logger.warning(f"Intent detection failed: {e}, defaulting to replace")
        return "replace"



def generate_markdown_from_plan(plan: PresentationPlan) -> str:
    """Convert presentation plan to markdown format"""
    markdown_lines = []
    
    for slide in plan.slides:
        # Add title
        markdown_lines.append(f"# {slide.title}")
        
        # Add bullets
        for bullet in slide.bullets:
            markdown_lines.append(f"- {bullet}")
        
        # Add speaker notes as comment
        if slide.speaker_notes:
            markdown_lines.append(f"<!-- Speaker Notes: {slide.speaker_notes} -->")
        
        markdown_lines.append("")  # Empty line between slides
    
    return "\n".join(markdown_lines)

@app.get("/api/preview/{session_id}")
async def get_preview(session_id: str):
    """Get presentation preview"""
    session = session_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Check if presentation file exists
    preview_path = os.path.join(settings.upload_dir, f"{session_id}_presentation.pptx")
    if not os.path.exists(preview_path):
        raise HTTPException(status_code=404, detail="Preview not available")
    
    # Generate preview data
    slides = ppt_service.parse_markdown_to_slides(session.current_markdown)
    
    return PresentationPreview(
        session_id=session_id,
        slides=slides,
        total_slides=len(slides),
        generated_at=datetime.now()
    )

@app.get("/api/download/{session_id}")
async def download_presentation(session_id: str):
    """Download the generated presentation"""
    session = session_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Check if presentation file exists
    file_path = os.path.join(settings.upload_dir, f"{session_id}_presentation.pptx")
    if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="Presentation not found")
        
    return FileResponse(
        file_path,
            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            filename=f"presentation_{session_id}.pptx"
    )

@app.post("/api/slide/{session_id}/{slide_number}/layout")
async def change_slide_layout(
    session_id: str,
    slide_number: int,
    layout_id: int
):
    """Change the layout of a specific slide"""
    try:
        # Get current plan and mappings
        plan = session_service.get_presentation_plan(session_id)
        mappings = session_service.get_slide_mappings(session_id)
        
        if not plan or not mappings:
            raise HTTPException(status_code=404, detail="Presentation plan not found")
        
        if slide_number < 1 or slide_number > len(mappings):
            raise HTTPException(status_code=400, detail="Invalid slide number")
        
        # Update mapping
        mappings[slide_number - 1].layout_id = layout_id
        session_service.save_slide_mappings(session_id, mappings)
        
        # Recompose slide
        template_profile = session_service.get_template_profile(session_id)
        if template_profile:
            presentation_path = Path(settings.upload_dir) / f"{session_id}_presentation.pptx"
            slide_composer.update_slide(
                presentation_path,
                slide_number,
                plan.slides[slide_number - 1],
                layout_id
            )
        
        return {"success": True, "message": f"Layout updated for slide {slide_number}"}
        
    except Exception as e:
        logger.error(f"Error changing slide layout: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/slide/{session_id}/{slide_number}/regenerate")
async def regenerate_slide(
    session_id: str,
    slide_number: int,
    instruction: Optional[str] = None
):
    """Regenerate a specific slide with optional instruction"""
    try:
        # Get current plan
        plan = session_service.get_presentation_plan(session_id)
        if not plan:
            raise HTTPException(status_code=404, detail="Presentation plan not found")
        
        if slide_number < 1 or slide_number > len(plan.slides):
            raise HTTPException(status_code=400, detail="Invalid slide number")
        
        # Regenerate slide content
        slide = plan.slides[slide_number - 1]
        template_profile = session_service.get_template_profile(session_id)
        
        if instruction and template_profile:
            # Use LLM to adapt slide based on instruction
            adapted_slide = await slide_planner.adapt_slide_for_layout(
                slide,
                {"instruction": instruction},
                "regenerate"
            )
            plan.slides[slide_number - 1] = adapted_slide
            session_service.save_presentation_plan(session_id, plan)
        
        return {"success": True, "message": f"Slide {slide_number} regenerated"}
        
    except Exception as e:
        logger.error(f"Error regenerating slide: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time updates"""
    await manager.connect(websocket, session_id)
    try:
        while True:
            # Keep connection alive and handle incoming messages
            message = await websocket.receive_json()
            logger.info(f"WebSocket received message: {message}")
            
            # Handle specific commands
            if message.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
            elif message.get("type") == "get_status":
                await websocket.send_json({"type": "status", "data": {"connected": True}})
            else:
                # Echo back other messages
                await websocket.send_json({"type": "echo", "data": message})
                
    except WebSocketDisconnect:
        manager.disconnect(session_id)
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        manager.disconnect(session_id)

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": "2.0.0",
        "agentic_features": True,
        "services": {
            "template_analyzer": "active",
            "slide_planner": "active",
            "layout_matcher": "active",
            "slide_composer": "active",
            "validator": "active"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)