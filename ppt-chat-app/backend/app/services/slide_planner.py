"""
Slide Planner Service
Uses LLM to generate structured presentation plans based on user input and template profiles
"""

import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid

from app.models import (
    TemplateProfile, PresentationPlan, SlideSpec, 
    SlideContentNeeds, ChatMessage
)
from app.services.openai_service import openai_service

logger = logging.getLogger(__name__)

class SlidePlanner:
    """Plans presentation slides using LLM with template awareness"""
    
    def __init__(self):
        self.max_retries = 3
    
    async def create_presentation_plan(
        self,
        user_prompt: str,
        template_profile: TemplateProfile,
        chat_history: List[ChatMessage],
        session_id: str
    ) -> PresentationPlan:
        """
        Create a structured presentation plan based on user input and template
        
        Args:
            user_prompt: User's request for the presentation
            template_profile: The analyzed template profile
            chat_history: Previous chat messages for context
            session_id: Current session ID
            
        Returns:
            PresentationPlan with slide specifications
        """
        try:
            # Build the system prompt with template awareness
            system_prompt = self._build_system_prompt(template_profile)
            
            # Build the user message with context
            user_message = self._build_user_message(user_prompt, chat_history)
            
            # Get plan from LLM with JSON schema
            plan_json = await self._get_plan_from_llm(system_prompt, user_message)
            
            # Parse and validate the plan
            plan = self._parse_plan(plan_json, session_id)
            
            logger.info(f"Created presentation plan with {len(plan.slides)} slides")
            return plan
            
        except Exception as e:
            logger.error(f"Error creating presentation plan: {str(e)}")
            raise
    
    def _build_system_prompt(self, template_profile: TemplateProfile) -> str:
        """Build system prompt with template constraints"""
        
        # Summarize available layouts
        layout_summary = []
        for layout in template_profile.layout_catalog:
            placeholders = {}
            for p in layout.placeholders:
                p_type = p.type.value
                placeholders[p_type] = placeholders.get(p_type, 0) + 1
            
            layout_summary.append({
                "layout_id": layout.layout_id,
                "name": layout.name,
                "placeholders": placeholders,
                "description": layout.notes
            })
        
        system_prompt = f"""You are a presentation planning assistant. Your task is to create a structured presentation plan based on user requirements and available template layouts.

AVAILABLE TEMPLATE LAYOUTS:
{json.dumps(layout_summary, indent=2)}

TEMPLATE THEME:
- Fonts: {json.dumps(template_profile.theme.font_scheme)}
- Default font size: {template_profile.theme.default_font_size}pt
- Slide dimensions: {template_profile.slide_width}" x {template_profile.slide_height}"

INSTRUCTIONS:
1. Analyze the user's request and create a logical slide structure
2. For each slide, determine what content elements are needed
3. Consider the available layouts when planning content
4. Keep slides focused - one main idea per slide
5. Use bullet points for clarity
6. Plan for visual elements (pictures, charts, tables) only when specifically requested or highly relevant

OUTPUT FORMAT:
You must respond with ONLY a valid JSON object matching this schema:
{{
    "slides": [
        {{
            "slide_id": "unique_id",
            "title": "Slide Title",
            "bullets": ["Bullet 1", "Bullet 2", ...],
            "speaker_notes": "Optional speaker notes",
            "needs": {{
                "has_picture": false,
                "has_table": null,  // or {{"rows": 3, "cols": 2, "headers": ["Col1", "Col2"]}}
                "has_chart": null,  // or {{"type": "bar", "series": [...], "categories": [...]}}
                "has_multiple_content_areas": false,
                "estimated_bullet_count": 3
            }}
        }}
    ],
    "metadata": {{
        "total_slides": 5,
        "presentation_type": "informational",  // or "pitch", "tutorial", etc.
        "estimated_duration_minutes": 10
    }}
}}

IMPORTANT:
- Each slide must have a unique slide_id
- Keep bullets concise (ideally under 50 characters each)
- Only set has_picture, has_table, or has_chart to true if explicitly needed
- estimated_bullet_count should match the actual number of bullets
- Respond with ONLY the JSON object, no additional text"""
        
        return system_prompt
    
    def _build_user_message(self, user_prompt: str, chat_history: List[ChatMessage]) -> str:
        """Build user message with relevant context"""
        
        # Include recent context if available
        context_parts = []
        
        # Add last few relevant messages from history
        relevant_history = []
        for msg in chat_history[-5:]:  # Last 5 messages
            if msg.role in ["user", "assistant"]:
                relevant_history.append(f"{msg.role.upper()}: {msg.content[:200]}")
        
        if relevant_history:
            context_parts.append("RECENT CONTEXT:\n" + "\n".join(relevant_history))
        
        context_parts.append(f"CURRENT REQUEST:\n{user_prompt}")
        
        return "\n\n".join(context_parts)
    
    async def _get_plan_from_llm(self, system_prompt: str, user_message: str) -> Dict[str, Any]:
        """Get structured plan from LLM"""
        
        for attempt in range(self.max_retries):
            try:
                # Call OpenAI with JSON mode
                response = await openai_service.get_completion(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message}
                    ],
                    temperature=0.7,
                    response_format={"type": "json_object"}  # Force JSON response
                )
                
                # Parse JSON response
                plan_json = json.loads(response)
                
                # Validate structure
                if "slides" in plan_json and isinstance(plan_json["slides"], list):
                    return plan_json
                else:
                    raise ValueError("Invalid plan structure")
                    
            except json.JSONDecodeError as e:
                logger.warning(f"JSON decode error on attempt {attempt + 1}: {str(e)}")
                if attempt == self.max_retries - 1:
                    raise
            except Exception as e:
                logger.error(f"Error getting plan from LLM: {str(e)}")
                if attempt == self.max_retries - 1:
                    raise
        
        raise ValueError("Failed to get valid plan from LLM")
    
    def _parse_plan(self, plan_json: Dict[str, Any], session_id: str) -> PresentationPlan:
        """Parse JSON plan into PresentationPlan model"""
        
        slides = []
        for slide_data in plan_json.get("slides", []):
            # Ensure slide has an ID
            slide_id = slide_data.get("slide_id", str(uuid.uuid4())[:8])
            
            # Parse needs
            needs_data = slide_data.get("needs", {})
            needs = SlideContentNeeds(
                has_picture=needs_data.get("has_picture", False),
                has_table=needs_data.get("has_table"),
                has_chart=needs_data.get("has_chart"),
                has_multiple_content_areas=needs_data.get("has_multiple_content_areas", False),
                estimated_bullet_count=needs_data.get("estimated_bullet_count", len(slide_data.get("bullets", [])))
            )
            
            # Create slide spec
            slide = SlideSpec(
                slide_id=slide_id,
                title=slide_data.get("title", "Untitled Slide"),
                bullets=slide_data.get("bullets", []),
                speaker_notes=slide_data.get("speaker_notes"),
                needs=needs
            )
            slides.append(slide)
        
        # Create presentation plan
        plan = PresentationPlan(
            session_id=session_id,
            slides=slides,
            metadata=plan_json.get("metadata", {}),
            created_at=datetime.now()
        )
        
        return plan
    
    async def adapt_slide_for_layout(
        self,
        slide_spec: SlideSpec,
        target_layout: Dict[str, Any],
        adaptation_type: str
    ) -> SlideSpec:
        """
        Adapt a slide's content to fit a specific layout
        
        Args:
            slide_spec: Original slide specification
            target_layout: Target layout constraints
            adaptation_type: Type of adaptation needed (split, condense, etc.)
            
        Returns:
            Adapted SlideSpec
        """
        try:
            system_prompt = f"""You are adapting slide content to fit a specific PowerPoint layout.

TARGET LAYOUT: {json.dumps(target_layout)}
ADAPTATION TYPE: {adaptation_type}

Adapt the content according to these rules:
- For "split": Divide content into multiple slides if too much for one
- For "condense": Combine or summarize content to fit
- For "reformat": Change structure (e.g., bullets to paragraphs)
- Maintain the core message and information

Respond with ONLY a JSON object for the adapted slide(s)."""
            
            user_message = f"""Original slide:
Title: {slide_spec.title}
Bullets: {json.dumps(slide_spec.bullets)}
Speaker Notes: {slide_spec.speaker_notes or 'None'}

Adapt this slide with adaptation type: {adaptation_type}"""
            
            response = await openai_service.get_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.5,
                response_format={"type": "json_object"}
            )
            
            adapted_json = json.loads(response)
            
            # Parse the adapted slide
            adapted_slide = SlideSpec(
                slide_id=slide_spec.slide_id,
                title=adapted_json.get("title", slide_spec.title),
                bullets=adapted_json.get("bullets", slide_spec.bullets),
                speaker_notes=adapted_json.get("speaker_notes", slide_spec.speaker_notes),
                needs=slide_spec.needs  # Keep original needs for now
            )
            
            return adapted_slide
            
        except Exception as e:
            logger.error(f"Error adapting slide: {str(e)}")
            return slide_spec  # Return original if adaptation fails

# Create singleton instance
slide_planner = SlidePlanner()