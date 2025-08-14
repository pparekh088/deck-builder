"""
Layout Matcher Service
Matches slide specifications to the best available template layouts using scoring algorithms
"""

import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

from app.models import (
    SlideSpec, SlideLayoutSignature, TemplateProfile,
    SlideMapping, PlaceholderType
)

logger = logging.getLogger(__name__)

@dataclass
class LayoutScore:
    """Score for a layout match"""
    layout_id: int
    layout_name: str
    total_score: float
    component_scores: Dict[str, float]
    adaptations_needed: List[str]

class LayoutMatcher:
    """Matches slide specifications to optimal template layouts"""
    
    def __init__(self):
        # Scoring weights
        self.weights = {
            'title_match': 0.25,
            'content_match': 0.30,
            'visual_match': 0.20,
            'complexity_match': 0.15,
            'layout_type_match': 0.10
        }
    
    def match_slides_to_layouts(
        self,
        slides: List[SlideSpec],
        template_profile: TemplateProfile
    ) -> List[SlideMapping]:
        """
        Match all slides to the best available layouts
        
        Args:
            slides: List of slide specifications
            template_profile: Available template layouts
            
        Returns:
            List of SlideMapping objects
        """
        mappings = []
        
        for slide in slides:
            best_match = self.find_best_layout(slide, template_profile)
            mappings.append(best_match)
            
            logger.info(f"Slide '{slide.title}' matched to layout '{best_match.layout_name}' "
                       f"(confidence: {best_match.confidence_score:.2f})")
        
        return mappings
    
    def find_best_layout(
        self,
        slide: SlideSpec,
        template_profile: TemplateProfile
    ) -> SlideMapping:
        """
        Find the best matching layout for a single slide
        
        Args:
            slide: Slide specification
            template_profile: Available template layouts
            
        Returns:
            SlideMapping with the best match
        """
        scores = []
        
        for layout in template_profile.layout_catalog:
            score = self._score_layout(slide, layout)
            scores.append(score)
        
        # Sort by total score (highest first)
        scores.sort(key=lambda x: x.total_score, reverse=True)
        
        if not scores:
            # Fallback to first layout if no matches
            return SlideMapping(
                slide_spec_id=slide.slide_id,
                layout_id=0,
                layout_name="Default",
                confidence_score=0.0,
                adaptations_needed=["No suitable layout found"]
            )
        
        best_score = scores[0]
        
        return SlideMapping(
            slide_spec_id=slide.slide_id,
            layout_id=best_score.layout_id,
            layout_name=best_score.layout_name,
            confidence_score=best_score.total_score,
            adaptations_needed=best_score.adaptations_needed
        )
    
    def _score_layout(
        self,
        slide: SlideSpec,
        layout: SlideLayoutSignature
    ) -> LayoutScore:
        """
        Score how well a layout matches a slide specification
        
        Args:
            slide: Slide specification
            layout: Layout to score
            
        Returns:
            LayoutScore with detailed scoring
        """
        scores = {}
        adaptations = []
        
        # 1. Title match (does layout have title placeholder?)
        has_title = layout.has_placeholder_type(PlaceholderType.TITLE)
        scores['title_match'] = 1.0 if has_title else 0.0
        if not has_title and slide.title:
            adaptations.append("No title placeholder - will use first text area")
        
        # 2. Content match (body/content placeholders vs bullets)
        content_score, content_adaptations = self._score_content_match(slide, layout)
        scores['content_match'] = content_score
        adaptations.extend(content_adaptations)
        
        # 3. Visual match (pictures, charts, tables)
        visual_score, visual_adaptations = self._score_visual_match(slide, layout)
        scores['visual_match'] = visual_score
        adaptations.extend(visual_adaptations)
        
        # 4. Complexity match (simple vs complex layouts)
        complexity_score = self._score_complexity_match(slide, layout)
        scores['complexity_match'] = complexity_score
        
        # 5. Layout type match (based on layout name heuristics)
        type_score = self._score_layout_type(slide, layout)
        scores['layout_type_match'] = type_score
        
        # Calculate weighted total
        total_score = sum(
            scores[key] * self.weights[key]
            for key in scores
        )
        
        return LayoutScore(
            layout_id=layout.layout_id,
            layout_name=layout.name,
            total_score=total_score,
            component_scores=scores,
            adaptations_needed=adaptations
        )
    
    def _score_content_match(
        self,
        slide: SlideSpec,
        layout: SlideLayoutSignature
    ) -> Tuple[float, List[str]]:
        """Score content placeholder match"""
        adaptations = []
        
        # Count content placeholders
        body_count = layout.count_placeholder_type(PlaceholderType.BODY)
        content_count = layout.count_placeholder_type(PlaceholderType.CONTENT)
        total_content_areas = body_count + content_count
        
        # Check if slide needs multiple content areas
        if slide.needs.has_multiple_content_areas:
            if total_content_areas >= 2:
                return 1.0, []
            else:
                adaptations.append("Need to combine content into single area")
                return 0.5, adaptations
        
        # Check bullet count vs available space
        bullet_count = len(slide.bullets)
        
        if bullet_count == 0:
            # No bullets, any layout works
            return 1.0, []
        elif bullet_count <= 5:
            # Few bullets, single content area is fine
            if total_content_areas >= 1:
                return 1.0, []
            else:
                adaptations.append("No content placeholder for bullets")
                return 0.2, adaptations
        elif bullet_count <= 10:
            # Medium bullets, might need two areas
            if total_content_areas >= 2:
                return 1.0, []
            elif total_content_areas == 1:
                adaptations.append("May need to condense bullets")
                return 0.7, adaptations
            else:
                adaptations.append("No content placeholder for bullets")
                return 0.2, adaptations
        else:
            # Many bullets, definitely need multiple areas or split
            if total_content_areas >= 2:
                return 0.9, []
            elif total_content_areas == 1:
                adaptations.append("Need to split bullets across slides")
                return 0.4, adaptations
            else:
                adaptations.append("No content placeholder, need major restructuring")
                return 0.1, adaptations
    
    def _score_visual_match(
        self,
        slide: SlideSpec,
        layout: SlideLayoutSignature
    ) -> Tuple[float, List[str]]:
        """Score visual element match"""
        score = 1.0
        adaptations = []
        
        # Check picture needs
        if slide.needs.has_picture:
            if layout.has_placeholder_type(PlaceholderType.PICTURE):
                score *= 1.0
            else:
                score *= 0.5
                adaptations.append("No picture placeholder - will insert as shape")
        
        # Check table needs
        if slide.needs.has_table:
            if layout.has_placeholder_type(PlaceholderType.TABLE):
                score *= 1.0
            elif layout.has_placeholder_type(PlaceholderType.CONTENT):
                score *= 0.8  # Can use content placeholder
                adaptations.append("Will use content placeholder for table")
            else:
                score *= 0.4
                adaptations.append("No suitable placeholder for table")
        
        # Check chart needs
        if slide.needs.has_chart:
            if layout.has_placeholder_type(PlaceholderType.CHART):
                score *= 1.0
            elif layout.has_placeholder_type(PlaceholderType.CONTENT):
                score *= 0.8  # Can use content placeholder
                adaptations.append("Will use content placeholder for chart")
            else:
                score *= 0.4
                adaptations.append("No suitable placeholder for chart")
        
        return score, adaptations
    
    def _score_complexity_match(
        self,
        slide: SlideSpec,
        layout: SlideLayoutSignature
    ) -> float:
        """Score based on complexity match"""
        
        # Calculate slide complexity
        slide_complexity = 0
        if slide.title:
            slide_complexity += 1
        if slide.bullets:
            slide_complexity += min(len(slide.bullets) / 3, 3)  # Cap at 3
        if slide.needs.has_picture:
            slide_complexity += 2
        if slide.needs.has_table:
            slide_complexity += 2
        if slide.needs.has_chart:
            slide_complexity += 2
        
        # Calculate layout complexity
        layout_complexity = len(layout.placeholders)
        
        # Score based on how close the complexities are
        diff = abs(slide_complexity - layout_complexity)
        if diff == 0:
            return 1.0
        elif diff <= 1:
            return 0.8
        elif diff <= 2:
            return 0.6
        elif diff <= 3:
            return 0.4
        else:
            return 0.2
    
    def _score_layout_type(
        self,
        slide: SlideSpec,
        layout: SlideLayoutSignature
    ) -> float:
        """Score based on layout name heuristics"""
        
        layout_name_lower = layout.name.lower()
        
        # Title slide detection
        if any(word in slide.title.lower() for word in ['welcome', 'introduction', 'agenda', 'title']):
            if 'title' in layout_name_lower:
                return 1.0
            elif 'section' in layout_name_lower:
                return 0.7
        
        # Section header detection
        if len(slide.bullets) == 0 and slide.title:
            if 'section' in layout_name_lower or 'divider' in layout_name_lower:
                return 1.0
        
        # Content slide detection
        if slide.bullets:
            if 'content' in layout_name_lower or 'bullet' in layout_name_lower:
                return 1.0
            elif 'text' in layout_name_lower:
                return 0.8
        
        # Two content detection
        if slide.needs.has_multiple_content_areas:
            if 'two' in layout_name_lower or 'comparison' in layout_name_lower:
                return 1.0
        
        # Picture slide detection
        if slide.needs.has_picture:
            if 'picture' in layout_name_lower or 'image' in layout_name_lower:
                return 1.0
            elif 'content' in layout_name_lower and 'picture' in layout_name_lower:
                return 0.9
        
        # Default score
        return 0.5
    
    def suggest_layout_change(
        self,
        slide: SlideSpec,
        current_layout_id: int,
        template_profile: TemplateProfile,
        reason: str
    ) -> Optional[SlideMapping]:
        """
        Suggest an alternative layout for a slide
        
        Args:
            slide: Slide specification
            current_layout_id: Currently assigned layout
            template_profile: Available layouts
            reason: Reason for change (e.g., "overflow", "missing_placeholder")
            
        Returns:
            Alternative SlideMapping or None if current is best
        """
        # Get all layout scores except current
        scores = []
        for layout in template_profile.layout_catalog:
            if layout.layout_id != current_layout_id:
                score = self._score_layout(slide, layout)
                scores.append(score)
        
        # Sort by score
        scores.sort(key=lambda x: x.total_score, reverse=True)
        
        if not scores:
            return None
        
        # Check if best alternative is significantly better
        best_alt = scores[0]
        current_layout = template_profile.get_layout_by_id(current_layout_id)
        
        if current_layout:
            current_score = self._score_layout(slide, current_layout)
            
            # Only suggest change if alternative is notably better
            if best_alt.total_score > current_score.total_score + 0.2:
                return SlideMapping(
                    slide_spec_id=slide.slide_id,
                    layout_id=best_alt.layout_id,
                    layout_name=best_alt.layout_name,
                    confidence_score=best_alt.total_score,
                    adaptations_needed=best_alt.adaptations_needed
                )
        
        return None

# Create singleton instance
layout_matcher = LayoutMatcher()