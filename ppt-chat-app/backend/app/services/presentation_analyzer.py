"""
Presentation Analyzer Service
Analyzes existing presentations to understand structure and content
"""

import logging
from typing import List, Dict, Optional, Any
from pathlib import Path
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE, PP_PLACEHOLDER

from app.models import SlideSpec, PlaceholderType

logger = logging.getLogger(__name__)

class PresentationAnalyzer:
    """Analyzes existing presentations to understand their structure"""
    
    def __init__(self):
        pass
    
    def analyze_presentation(self, presentation_path: Path) -> Dict[str, Any]:
        """
        Analyze an existing presentation to understand its structure
        
        Returns:
            Dict with slide information, content, and structure
        """
        try:
            prs = Presentation(str(presentation_path))
            
            analysis = {
                "total_slides": len(prs.slides),
                "slides": [],
                "layouts_used": set(),
                "has_content": True if len(prs.slides) > 0 else False
            }
            
            for idx, slide in enumerate(prs.slides):
                slide_info = self._analyze_slide(slide, idx)
                analysis["slides"].append(slide_info)
                analysis["layouts_used"].add(slide_info["layout_name"])
            
            logger.info(f"Analyzed presentation: {len(prs.slides)} slides, {len(analysis['layouts_used'])} unique layouts")
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing presentation: {e}")
            return {
                "total_slides": 0,
                "slides": [],
                "layouts_used": set(),
                "has_content": False,
                "error": str(e)
            }
    
    def _analyze_slide(self, slide, slide_index: int) -> Dict[str, Any]:
        """Analyze a single slide"""
        
        slide_info = {
            "index": slide_index,
            "layout_name": slide.slide_layout.name,
            "title": "",
            "content": [],
            "placeholders": len(slide.placeholders),
            "total_shapes": len(slide.shapes),
            "has_pictures": False,
            "has_charts": False,
            "has_tables": False
        }
        
        # Extract text content
        for shape in slide.shapes:
            try:
                if hasattr(shape, 'text') and shape.text and shape.text.strip():
                    # Determine if this is likely a title or content
                    text = shape.text.strip()
                    
                    # Check if it's a placeholder
                    is_placeholder = hasattr(shape, 'is_placeholder') and shape.is_placeholder
                    
                    if is_placeholder and hasattr(shape, 'placeholder_format'):
                        if shape.placeholder_format.type == PP_PLACEHOLDER.TITLE:
                            slide_info["title"] = text
                        elif shape.placeholder_format.type in [PP_PLACEHOLDER.BODY, PP_PLACEHOLDER.OBJECT]:
                            # Split bullets
                            bullets = [line.strip() for line in text.split('\n') if line.strip()]
                            slide_info["content"].extend(bullets)
                    else:
                        # Non-placeholder text - could be title or content
                        if not slide_info["title"] and len(text) < 100:
                            slide_info["title"] = text
                        else:
                            bullets = [line.strip() for line in text.split('\n') if line.strip()]
                            slide_info["content"].extend(bullets)
                
                # Check for other content types
                if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
                    slide_info["has_pictures"] = True
                elif hasattr(shape, 'chart'):
                    slide_info["has_charts"] = True
                elif hasattr(shape, 'table'):
                    slide_info["has_tables"] = True
                    
            except Exception as e:
                logger.debug(f"Error analyzing shape in slide {slide_index}: {e}")
                continue
        
        # Clean up content
        slide_info["content"] = [c for c in slide_info["content"] if c and len(c) > 2]
        
        logger.debug(f"Slide {slide_index}: '{slide_info['title']}' with {len(slide_info['content'])} content items")
        
        return slide_info
    
    def find_slides_by_content(self, analysis: Dict[str, Any], search_terms: List[str]) -> List[int]:
        """Find slides that contain specific content terms"""
        
        matching_slides = []
        
        for slide_info in analysis["slides"]:
            slide_text = (slide_info["title"] + " " + " ".join(slide_info["content"])).lower()
            
            for term in search_terms:
                if term.lower() in slide_text:
                    matching_slides.append(slide_info["index"])
                    break
        
        return list(set(matching_slides))  # Remove duplicates
    
    def get_slide_summary(self, analysis: Dict[str, Any]) -> str:
        """Get a human-readable summary of the presentation"""
        
        if not analysis["has_content"]:
            return "No presentation content found."
        
        summary = f"Presentation has {analysis['total_slides']} slides:\n\n"
        
        for slide_info in analysis["slides"]:
            title = slide_info["title"] or f"Slide {slide_info['index'] + 1}"
            content_count = len(slide_info["content"])
            summary += f"Slide {slide_info['index'] + 1}: {title}"
            if content_count > 0:
                summary += f" ({content_count} bullet points)"
            summary += "\n"
        
        return summary

# Create singleton instance
presentation_analyzer = PresentationAnalyzer()
