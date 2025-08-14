from fastapi import FastAPI, HTTPException, UploadFile, File, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import os
import json
import asyncio
from typing import Dict, Optional
from datetime import datetime
import logging

from app.config import settings
from app.models import (
    ChatRequest, ChatResponse, TemplateUploadResponse,
    SessionInfo, ChatMessage, MessageRole, PresentationPreview,
    DownloadResponse, WebSocketMessage
)
from app.services.openai_service import openai_service
from app.services.ppt_service import ppt_service
from app.services.session_service import session_service

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="PowerPoint Chat Generator",
    description="Generate PowerPoint presentations using AI chat",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for serving generated files
if not os.path.exists(settings.upload_dir):
    os.makedirs(settings.upload_dir)
app.mount("/static", StaticFiles(directory=settings.upload_dir), name="static")

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
    return {"message": "PowerPoint Chat Generator API", "version": "1.0.0"}

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
    """Upload a PowerPoint template for the session"""
    try:
        # Validate file type
        if not file.filename.endswith('.pptx'):
            raise HTTPException(status_code=400, detail="Only .pptx files are allowed")
        
        # Check file size
        contents = await file.read()
        if len(contents) > settings.max_file_size:
            raise HTTPException(status_code=400, detail=f"File too large. Max size: {settings.max_file_size} bytes")
        
        # Save template
        template_id = ppt_service.save_template(contents, file.filename, session_id)
        
        # Update session
        session_service.set_template(session_id, template_id, file.filename)
        
        # Send WebSocket notification
        await manager.send_message(session_id, {
            "type": "template_uploaded",
            "data": {
                "template_id": template_id,
                "template_name": file.filename
            }
        })
        
        return TemplateUploadResponse(
            success=True,
            message="Template uploaded successfully",
            template_id=template_id,
            template_name=file.filename
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error uploading template: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to upload template")

@app.post("/api/chat")
async def chat(request: ChatRequest):
    """Process chat message and generate/update presentation"""
    try:
        # Get session
        session = session_service.get_session(request.session_id)
        if not session:
            session = SessionInfo(session_id=request.session_id)
        
        # Add user message to history
        user_message = ChatMessage(
            role=MessageRole.USER,
            content=request.message
        )
        session_service.add_chat_message(request.session_id, user_message)
        
        # Send status update via WebSocket
        await manager.send_message(request.session_id, {
            "type": "status",
            "data": {"message": "Generating content with AI..."}
        })
        
        # Generate content with OpenAI
        response_text, markdown_content = await openai_service.generate_presentation_content(
            prompt=request.message,
            context=session.chat_history,
            current_markdown=session.current_markdown
        )
        
        # Add assistant message to history
        assistant_message = ChatMessage(
            role=MessageRole.ASSISTANT,
            content=response_text
        )
        session_service.add_chat_message(request.session_id, assistant_message)
        
        # Update markdown in session
        if markdown_content:
            # Append or replace markdown based on context
            if "new presentation" in request.message.lower() or "start over" in request.message.lower():
                session.current_markdown = markdown_content
            else:
                session.current_markdown += "\n\n" + markdown_content
            
            session_service.update_markdown(request.session_id, session.current_markdown)
            
            # Send status update
            await manager.send_message(request.session_id, {
                "type": "status",
                "data": {"message": "Converting to PowerPoint..."}
            })
            
            # Generate PowerPoint
            pptx_path, slide_previews = ppt_service.markdown_to_pptx(
                markdown=session.current_markdown,
                template_id=session.template_id,
                session_id=request.session_id
            )
            
            # Create preview data
            preview = PresentationPreview(
                session_id=request.session_id,
                slides=slide_previews,
                total_slides=len(slide_previews),
                generated_at=datetime.now()
            )
            
            # Send preview update via WebSocket
            await manager.send_message(request.session_id, {
                "type": "preview_update",
                "data": preview.model_dump()
            })
            
            # Prepare response
            return ChatResponse(
                response=response_text,
                markdown_content=session.current_markdown,
                session_id=request.session_id,
                preview_available=True,
                preview_url=f"/api/preview/{request.session_id}"
            )
        else:
            return ChatResponse(
                response=response_text,
                markdown_content=session.current_markdown,
                session_id=request.session_id,
                preview_available=False
            )
            
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        await manager.send_message(request.session_id, {
            "type": "error",
            "data": {"message": str(e)}
        })
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/preview/{session_id}")
async def get_preview(session_id: str):
    """Get presentation preview data"""
    try:
        session = session_service.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Get the latest presentation file
        pptx_path = ppt_service.get_presentation_path(session_id)
        if not pptx_path:
            raise HTTPException(status_code=404, detail="No presentation found")
        
        # Parse current markdown to get slide data
        _, slide_previews = ppt_service.markdown_to_pptx(
            markdown=session.current_markdown,
            template_id=session.template_id,
            session_id=session_id
        )
        
        preview = PresentationPreview(
            session_id=session_id,
            slides=slide_previews,
            total_slides=len(slide_previews),
            generated_at=datetime.now()
        )
        
        return preview
        
    except Exception as e:
        logger.error(f"Error getting preview: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/download/{session_id}")
async def download_presentation(session_id: str):
    """Download the generated PowerPoint file"""
    try:
        # Get the latest presentation file
        pptx_path = ppt_service.get_presentation_path(session_id)
        if not pptx_path or not os.path.exists(pptx_path):
            raise HTTPException(status_code=404, detail="Presentation not found")
        
        filename = os.path.basename(pptx_path)
        return FileResponse(
            path=pptx_path,
            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            filename=f"presentation_{session_id}.pptx"
        )
        
    except Exception as e:
        logger.error(f"Error downloading presentation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time updates"""
    await manager.connect(websocket, session_id)
    try:
        while True:
            # Keep connection alive and handle incoming messages
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Handle different message types
            if message.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
            elif message.get("type") == "get_status":
                session = session_service.get_session(session_id)
                if session:
                    await websocket.send_json({
                        "type": "status",
                        "data": {
                            "has_template": bool(session.template_id),
                            "template_name": session.template_name,
                            "message_count": len(session.chat_history)
                        }
                    })
                    
    except WebSocketDisconnect:
        manager.disconnect(session_id)
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        manager.disconnect(session_id)

@app.delete("/api/session/{session_id}")
async def delete_session(session_id: str):
    """Delete a session and its associated files"""
    try:
        # Delete session data
        session_service.delete_session(session_id)
        
        # Clean up files
        # TODO: Implement file cleanup
        
        return {"success": True, "message": "Session deleted"}
        
    except Exception as e:
        logger.error(f"Error deleting session: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint with detailed service status"""
    try:
        # Get session service health
        session_health = session_service.health_check()
        
        # Check if Azure OpenAI is configured
        openai_configured = bool(settings.azure_openai_api_key and settings.azure_openai_endpoint)
        
        # Overall health status
        overall_status = "healthy"
        if session_health["status"] == "unhealthy":
            overall_status = "unhealthy"
        elif session_health["status"] == "degraded":
            overall_status = "degraded"
        elif not openai_configured:
            overall_status = "degraded"
        
        return {
            "status": overall_status,
            "timestamp": datetime.now().isoformat(),
            "version": "1.0.0",
            "services": {
                "session_storage": session_health,
                "openai": {
                    "configured": openai_configured,
                    "endpoint": settings.azure_openai_endpoint if openai_configured else None
                },
                "websocket": {
                    "active_connections": len(manager.active_connections)
                }
            }
        }
    except Exception as e:
        return {
            "status": "error",
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)