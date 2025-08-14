import json
import uuid
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import redis
import logging
from app.config import settings
from app.models import SessionInfo, ChatMessage

logger = logging.getLogger(__name__)

class SessionService:
    def __init__(self):
        try:
            self.redis_client = redis.from_url(settings.redis_url, decode_responses=True)
            self.redis_available = True
            self.redis_client.ping()
        except:
            logger.warning("Redis not available, using in-memory storage")
            self.redis_available = False
            self.sessions = {}  # Fallback to in-memory storage
    
    def create_session(self) -> str:
        """Create a new session and return session ID"""
        session_id = str(uuid.uuid4())
        session_info = SessionInfo(session_id=session_id)
        
        self._save_session(session_id, session_info)
        return session_id
    
    def get_session(self, session_id: str) -> Optional[SessionInfo]:
        """Retrieve session information"""
        try:
            if self.redis_available:
                data = self.redis_client.get(f"session:{session_id}")
                if data:
                    return SessionInfo(**json.loads(data))
            else:
                return self.sessions.get(session_id)
        except Exception as e:
            logger.error(f"Error getting session: {str(e)}")
            return None
    
    def update_session(self, session_id: str, **kwargs) -> bool:
        """Update session information"""
        try:
            session = self.get_session(session_id)
            if not session:
                session = SessionInfo(session_id=session_id)
            
            # Update fields
            for key, value in kwargs.items():
                if hasattr(session, key):
                    setattr(session, key, value)
            
            session.updated_at = datetime.now()
            self._save_session(session_id, session)
            return True
        except Exception as e:
            logger.error(f"Error updating session: {str(e)}")
            return False
    
    def add_chat_message(self, session_id: str, message: ChatMessage) -> bool:
        """Add a chat message to session history"""
        try:
            session = self.get_session(session_id)
            if not session:
                session = SessionInfo(session_id=session_id)
            
            session.chat_history.append(message)
            session.updated_at = datetime.now()
            
            # Keep only last 50 messages to prevent memory issues
            if len(session.chat_history) > 50:
                session.chat_history = session.chat_history[-50:]
            
            self._save_session(session_id, session)
            return True
        except Exception as e:
            logger.error(f"Error adding chat message: {str(e)}")
            return False
    
    def update_markdown(self, session_id: str, markdown: str) -> bool:
        """Update the current markdown content for a session"""
        return self.update_session(session_id, current_markdown=markdown)
    
    def set_template(self, session_id: str, template_id: str, template_name: str) -> bool:
        """Set the template for a session"""
        return self.update_session(
            session_id, 
            template_id=template_id,
            template_name=template_name
        )
    
    def _save_session(self, session_id: str, session_info: SessionInfo):
        """Save session to storage"""
        try:
            if self.redis_available:
                # Convert to JSON, handling datetime objects
                data = session_info.model_dump_json()
                self.redis_client.setex(
                    f"session:{session_id}",
                    timedelta(hours=24),  # Session expires after 24 hours
                    data
                )
            else:
                self.sessions[session_id] = session_info
        except Exception as e:
            logger.error(f"Error saving session: {str(e)}")
            # Fallback to in-memory
            self.sessions[session_id] = session_info
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session"""
        try:
            if self.redis_available:
                self.redis_client.delete(f"session:{session_id}")
            else:
                self.sessions.pop(session_id, None)
            return True
        except Exception as e:
            logger.error(f"Error deleting session: {str(e)}")
            return False
    
    def get_active_sessions(self) -> list:
        """Get list of active session IDs"""
        try:
            if self.redis_available:
                keys = self.redis_client.keys("session:*")
                return [key.split(":")[-1] for key in keys]
            else:
                return list(self.sessions.keys())
        except Exception as e:
            logger.error(f"Error getting active sessions: {str(e)}")
            return []

# Singleton instance
session_service = SessionService()