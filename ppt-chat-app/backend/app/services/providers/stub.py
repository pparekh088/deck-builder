"""
Stub LLM Provider for deterministic testing
"""

import json
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class StubLLMProvider:
    """Stub LLM provider that returns deterministic responses for testing"""
    
    def __init__(self):
        logger.info("Initialized Stub LLM provider (deterministic mode for testing)")
        self.call_count = 0
    
    async def generate_presentation_content(
        self,
        prompt: str,
        chat_history: List[Dict[str, str]] = None,
        current_markdown: str = None
    ) -> tuple[str, str]:
        """Generate deterministic presentation content for testing"""
        
        self.call_count += 1
        
        # Deterministic response based on keywords in prompt
        if "roadmap" in prompt.lower() or "ai" in prompt.lower():
            markdown = """## Slide 1: AI Roadmap Overview
### Title: AI Strategy Roadmap 2024

**Key Points:**
- Foundation Phase: Q1 2024
- Implementation Phase: Q2-Q3 2024
- Scaling Phase: Q4 2024

---

## Slide 2: Key Performance Indicators
### Title: Success Metrics

**KPIs:**
- Model Accuracy: >95%
- Processing Speed: <100ms
- User Adoption: 80% by Q4
- ROI: 3x by year end

---

## Slide 3: Implementation Timeline
### Title: Quarterly Milestones

**Timeline:**
- Q1: Infrastructure setup
- Q2: Pilot deployment
- Q3: Full rollout
- Q4: Optimization & scaling"""
            
            response = f"I've created a 3-slide AI roadmap presentation with:\n\n{markdown}"
        
        else:
            # Default response
            markdown = """## Slide 1: Introduction
### Title: Welcome

**Agenda:**
- Overview
- Key Points
- Conclusion

---

## Slide 2: Main Content
### Title: Core Information

**Details:**
- Point 1: Important information
- Point 2: Supporting details
- Point 3: Additional context

---

## Slide 3: Summary
### Title: Key Takeaways

**Summary:**
- Main conclusion
- Action items
- Next steps"""
            
            response = f"I've created a 3-slide presentation:\n\n{markdown}"
        
        return response, markdown
    
    async def analyze_with_vision(
        self,
        image_data: bytes,
        prompt: str = "Analyze this slide layout"
    ) -> Dict[str, Any]:
        """Return deterministic vision analysis for testing"""
        
        # Deterministic vision labels
        return {
            "labels": [
                {
                    "shape_id": "shape_1",
                    "role": "Title",
                    "place_content": True,
                    "bbox_px": {"left": 100, "top": 50, "width": 800, "height": 100}
                },
                {
                    "shape_id": "shape_2",
                    "role": "Body",
                    "place_content": True,
                    "bbox_px": {"left": 100, "top": 200, "width": 800, "height": 400}
                },
                {
                    "shape_id": "shape_3",
                    "role": "Footer",
                    "place_content": False,
                    "bbox_px": {"left": 100, "top": 650, "width": 800, "height": 50}
                },
                {
                    "shape_id": "shape_4",
                    "role": "Logo",
                    "place_content": False,
                    "bbox_px": {"left": 850, "top": 20, "width": 100, "height": 100}
                }
            ],
            "description": "Standard slide layout with title, body, footer, and logo areas",
            "layout_type": "TitleBody"
        }
    
    async def create_presentation_plan(
        self,
        prompt: str,
        template_profile: Any = None
    ) -> Dict[str, Any]:
        """Return deterministic presentation plan for testing"""
        
        return {
            "title": "Test Presentation",
            "slides": [
                {
                    "slide_id": "slide_1",
                    "title": "Introduction",
                    "bullets": [
                        "Welcome to the presentation",
                        "Today's agenda",
                        "Key objectives"
                    ],
                    "speaker_notes": "Introduction and welcome"
                },
                {
                    "slide_id": "slide_2",
                    "title": "Main Content",
                    "bullets": [
                        "Core concept explanation",
                        "Supporting evidence",
                        "Real-world applications"
                    ],
                    "speaker_notes": "Main content delivery"
                },
                {
                    "slide_id": "slide_3",
                    "title": "Conclusion",
                    "bullets": [
                        "Summary of key points",
                        "Action items",
                        "Questions and next steps"
                    ],
                    "speaker_notes": "Wrap up and Q&A"
                }
            ]
        }