import json
import uuid
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import redis
import logging
from app.config import settings
from app.models import (
    SessionInfo, ChatMessage, TemplateProfile, 
    PresentationPlan, SlideMapping
)

logger = logging.getLogger(__name__)

class SessionService:
    def __init__(self):
        try:
            # Use the configured Redis URL with authentication
            redis_url = settings.get_redis_url()
            self.redis_client = redis.from_url(
                redis_url, 
                decode_responses=settings.redis_decode_responses,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30
            )
            # Test connection
            self.redis_client.ping()
            self.redis_available = True
            logger.info("Successfully connected to Redis")
        except redis.ConnectionError as e:
            logger.warning(f"Redis connection failed: {e}. Using in-memory storage")
            self.redis_available = False
            self.sessions = {}  # Fallback to in-memory storage
            self.template_profiles = {}  # Store template profiles
            self.presentation_plans = {}  # Store presentation plans
            self.slide_mappings = {}  # Store slide mappings
        except Exception as e:
            logger.warning(f"Redis not available: {e}. Using in-memory storage")
            self.redis_available = False
            self.sessions = {}  # Fallback to in-memory storage
            self.template_profiles = {}
            self.presentation_plans = {}
            self.slide_mappings = {}
    
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
                session_data = self.sessions.get(session_id)
                if session_data:
                    return SessionInfo(**session_data)
        except Exception as e:
            logger.error(f"Error retrieving session {session_id}: {e}")
        return None
    
    def update_session(self, session_id: str, **kwargs) -> bool:
        """Update session information"""
        session = self.get_session(session_id)
        if not session:
            return False
        
        # Update fields
        for key, value in kwargs.items():
            if hasattr(session, key):
                setattr(session, key, value)
        
        session.updated_at = datetime.now()
        self._save_session(session_id, session)
        return True
    
    def _save_session(self, session_id: str, session_info: SessionInfo):
        """Save session to storage"""
        try:
            session_dict = session_info.model_dump(mode='json')
            
            if self.redis_available:
                self.redis_client.setex(
                    f"session:{session_id}",
                    settings.session_ttl,
                    json.dumps(session_dict)
                )
            else:
                self.sessions[session_id] = session_dict
        except Exception as e:
            logger.error(f"Error saving session {session_id}: {e}")
    
    def add_chat_message(self, session_id: str, message: ChatMessage) -> bool:
        """Add a chat message to session history"""
        session = self.get_session(session_id)
        if not session:
            return False
        
        session.chat_history.append(message)
        self._save_session(session_id, session)
        return True
    
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

    def set_composition_mode(self, session_id: str, mode: str) -> bool:
        """Set composition mode: 'edit' or 'replace'"""
        if mode not in ("edit", "replace"):
            mode = "replace"
        return self.update_session(session_id, composition_mode=mode)

    def get_composition_mode(self, session_id: str) -> str:
        session = self.get_session(session_id)
        return session.composition_mode if session and getattr(session, 'composition_mode', None) else "replace"
    
    def clear_session(self, session_id: str) -> bool:
        """Clear all data for a session"""
        try:
            if self.redis_available:
                # Clear all related keys
                self.redis_client.delete(f"session:{session_id}")
                self.redis_client.delete(f"template_profile:{session_id}")
                self.redis_client.delete(f"presentation_plan:{session_id}")
                self.redis_client.delete(f"slide_mappings:{session_id}")
            else:
                self.sessions.pop(session_id, None)
                self.template_profiles.pop(session_id, None)
                self.presentation_plans.pop(session_id, None)
                self.slide_mappings.pop(session_id, None)
            return True
        except Exception as e:
            logger.error(f"Error clearing session {session_id}: {e}")
            return False
    
    def list_active_sessions(self) -> list:
        """List all active session IDs"""
        try:
            if self.redis_available:
                keys = self.redis_client.keys("session:*")
                return [key.split(":")[-1] for key in keys]
            else:
                return list(self.sessions.keys())
        except Exception as e:
            logger.error(f"Error listing sessions: {e}")
            return []
    
    def cleanup_expired_sessions(self):
        """Clean up expired sessions (for in-memory storage)"""
        if not self.redis_available:
            current_time = datetime.now()
            expired = []
            
            for session_id, session_data in self.sessions.items():
                session_info = SessionInfo(**session_data)
                if (current_time - session_info.updated_at).seconds > settings.session_ttl:
                    expired.append(session_id)
            
            for session_id in expired:
                self.clear_session(session_id)
                logger.info(f"Cleaned up expired session: {session_id}")
    
    def get_session_stats(self) -> dict:
        """Get statistics about sessions"""
        try:
            if self.redis_available:
                session_count = len(self.redis_client.keys("session:*"))
            else:
                session_count = len(self.sessions)
            
            return {
                "active_sessions": session_count,
                "storage_type": "redis" if self.redis_available else "memory",
                "ttl_seconds": settings.session_ttl
            }
        except Exception as e:
            logger.error(f"Error getting session stats: {e}")
            return {
                "active_sessions": 0,
                "storage_type": "unknown",
                "error": str(e)
            }
    
    # ============= New Agentic Methods =============
    
    def save_template_profile(self, session_id: str, profile: TemplateProfile) -> bool:
        """Save template profile for a session"""
        try:
            profile_dict = profile.model_dump(mode='json')
            
            if self.redis_available:
                self.redis_client.setex(
                    f"template_profile:{session_id}",
                    settings.session_ttl,
                    json.dumps(profile_dict)
                )
            else:
                self.template_profiles[session_id] = profile_dict
            
            logger.info(f"Saved template profile for session {session_id}")
            return True
        except Exception as e:
            logger.error(f"Error saving template profile: {e}")
            return False
    
    def get_template_profile(self, session_id: str) -> Optional[TemplateProfile]:
        """Get template profile for a session"""
        try:
            if self.redis_available:
                data = self.redis_client.get(f"template_profile:{session_id}")
                if data:
                    return TemplateProfile(**json.loads(data))
            else:
                profile_data = self.template_profiles.get(session_id)
                if profile_data:
                    return TemplateProfile(**profile_data)
        except Exception as e:
            logger.error(f"Error retrieving template profile: {e}")
        return None
    
    def save_presentation_plan(self, session_id: str, plan: PresentationPlan) -> bool:
        """Save presentation plan for a session"""
        try:
            plan_dict = plan.model_dump(mode='json')
            
            if self.redis_available:
                self.redis_client.setex(
                    f"presentation_plan:{session_id}",
                    settings.session_ttl,
                    json.dumps(plan_dict)
                )
            else:
                self.presentation_plans[session_id] = plan_dict
            
            logger.info(f"Saved presentation plan for session {session_id}")
            return True
        except Exception as e:
            logger.error(f"Error saving presentation plan: {e}")
            return False
    
    def get_presentation_plan(self, session_id: str) -> Optional[PresentationPlan]:
        """Get presentation plan for a session"""
        try:
            if self.redis_available:
                data = self.redis_client.get(f"presentation_plan:{session_id}")
                if data:
                    return PresentationPlan(**json.loads(data))
            else:
                plan_data = self.presentation_plans.get(session_id)
                if plan_data:
                    return PresentationPlan(**plan_data)
        except Exception as e:
            logger.error(f"Error retrieving presentation plan: {e}")
        return None
    
    def save_slide_mappings(self, session_id: str, mappings: list[SlideMapping]) -> bool:
        """Save slide layout mappings for a session"""
        try:
            mappings_dict = [m.model_dump(mode='json') for m in mappings]
            
            if self.redis_available:
                self.redis_client.setex(
                    f"slide_mappings:{session_id}",
                    settings.session_ttl,
                    json.dumps(mappings_dict)
                )
            else:
                self.slide_mappings[session_id] = mappings_dict
            
            logger.info(f"Saved slide mappings for session {session_id}")
            return True
        except Exception as e:
            logger.error(f"Error saving slide mappings: {e}")
            return False
    
    def get_slide_mappings(self, session_id: str) -> Optional[list[SlideMapping]]:
        """Get slide layout mappings for a session"""
        try:
            if self.redis_available:
                data = self.redis_client.get(f"slide_mappings:{session_id}")
                if data:
                    mappings_data = json.loads(data)
                    return [SlideMapping(**m) for m in mappings_data]
            else:
                mappings_data = self.slide_mappings.get(session_id)
                if mappings_data:
                    return [SlideMapping(**m) for m in mappings_data]
        except Exception as e:
            logger.error(f"Error retrieving slide mappings: {e}")
        return None

# Singleton instance
session_service = SessionService()