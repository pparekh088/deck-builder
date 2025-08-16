"""
Layout Matcher Service
Matches slide specifications to optimal template layouts
"""

import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

from app.models import (
    SlideSpec, SlideLayoutSignature, TemplateProfile,
    SlideMapping, PlaceholderType, PlaceholderInfo
)
from app.models.vision import VisionRole

# Import ILP solver
from .solver_ilp import choose_layout_and_mapping
from ..config import settings

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
        # Updated scoring weights with vision
        self.weights = {
            'tag_match': 0.30,      # Designer tags (highest priority)
            'vision_match': 0.25,   # Vision role match
            'title_match': 0.15,    # Title placeholder
            'content_match': 0.15,  # Content areas
            'visual_match': 0.10,   # Pictures/charts/tables
            'complexity_match': 0.05  # Layout complexity
        }
        
        # Vision role mapping for content types
        self.content_role_map = {
            'title': VisionRole.Title,
            'subtitle': VisionRole.Subtitle,
            'bullets': VisionRole.Bullets,
            'paragraph': VisionRole.Paragraph,
            'table': VisionRole.Table,
            'chart': VisionRole.Chart,
            'image': VisionRole.HeroImage,
            'quote': VisionRole.Paragraph,
            'section': VisionRole.SectionHeader
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
        Now includes vision-based scoring
        
        Args:
            slide: Slide specification
            layout: Layout to score
            
        Returns:
            LayoutScore with detailed scoring
        """
        scores = {}
        adaptations = []
        
        # 1. Tag match (highest priority) - NEW
        tag_score, tag_adaptations = self._score_tag_match(slide, layout)
        scores['tag_match'] = tag_score
        adaptations.extend(tag_adaptations)
        
        # 2. Vision match - NEW
        vision_score, vision_adaptations = self._score_vision_match(slide, layout)
        scores['vision_match'] = vision_score
        adaptations.extend(vision_adaptations)
        
        # 3. Title match (existing but lower weight now)
        has_title = layout.has_placeholder_type(PlaceholderType.TITLE)
        scores['title_match'] = 1.0 if has_title else 0.0
        if not has_title and slide.title:
            adaptations.append("No title placeholder - will use first text area")
        
        # 4. Content match (existing)
        content_score, content_adaptations = self._score_content_match(slide, layout)
        scores['content_match'] = content_score
        adaptations.extend(content_adaptations)
        
        # 5. Visual match (existing)
        visual_score, visual_adaptations = self._score_visual_match(slide, layout)
        scores['visual_match'] = visual_score
        adaptations.extend(visual_adaptations)
        
        # 6. Complexity match (existing)
        complexity_score = self._score_complexity_match(slide, layout)
        scores['complexity_match'] = complexity_score
        
        # Calculate weighted total
        total_score = sum(
            scores[key] * self.weights.get(key, 0)
            for key in scores
        )
        
        # Apply penalties for placing in non-content areas
        penalty = self._calculate_placement_penalty(layout)
        total_score *= (1.0 - penalty)
        
        return LayoutScore(
            layout_id=layout.layout_id,
            layout_name=layout.name,
            total_score=total_score,
            component_scores=scores,
            adaptations_needed=adaptations
        )
    
    def _score_tag_match(
        self,
        slide: SlideSpec,
        layout: SlideLayoutSignature
    ) -> Tuple[float, List[str]]:
        """Score based on designer tags (slot:* annotations)"""
        score = 0.0
        adaptations = []
        
        # Extract required content types from slide
        required_tags = set()
        if slide.title:
            required_tags.add('slot:title')
        if slide.bullets:
            required_tags.add('slot:bullets')
        if slide.needs.has_picture:
            required_tags.add('slot:image')
        if slide.needs.has_table:
            required_tags.add('slot:table')
        if slide.needs.has_chart:
            required_tags.add('slot:chart')
        
        # Check how many tags are satisfied
        found_tags = set()
        for placeholder in layout.placeholders:
            if placeholder.tags:
                found_tags.update(placeholder.tags)
        
        if required_tags:
            matched = required_tags.intersection(found_tags)
            score = len(matched) / len(required_tags)
            
            missing = required_tags - found_tags
            if missing:
                adaptations.append(f"Missing tagged slots: {', '.join(missing)}")
        else:
            # No specific tags required
            score = 0.5  # Neutral score
        
        return score, adaptations
    
    def _score_vision_match(
        self,
        slide: SlideSpec,
        layout: SlideLayoutSignature
    ) -> Tuple[float, List[str]]:
        """Score based on vision role labels"""
        score = 0.0
        adaptations = []
        
        # Count available vision roles
        vision_roles = {}
        placeable_count = 0
        
        for placeholder in layout.placeholders:
            if placeholder.vision:
                role = placeholder.vision.role
                if placeholder.vision.place_content:
                    placeable_count += 1
                    if role not in vision_roles:
                        vision_roles[role] = []
                    vision_roles[role].append(placeholder)
        
        if not vision_roles:
            # No vision labels, fallback to neutral score
            return 0.5, ["No vision labels available"]
        
        # Score based on required content
        matches = 0
        requirements = 0
        
        # Check title
        if slide.title:
            requirements += 1
            if 'Title' in vision_roles or 'SectionHeader' in vision_roles:
                matches += 1
            else:
                adaptations.append("No Title role identified by vision")
        
        # Check bullets/content
        if slide.bullets:
            requirements += 1
            if 'Bullets' in vision_roles or 'Paragraph' in vision_roles:
                matches += 1
                # Check if we have enough bullet areas
                bullet_areas = len(vision_roles.get('Bullets', []))
                if len(slide.bullets) > 10 and bullet_areas < 2:
                    adaptations.append("May need to split bullets (only 1 bullet area)")
            else:
                adaptations.append("No Bullets/Paragraph role identified")
        
        # Check visual elements
        if slide.needs.has_picture:
            requirements += 1
            if 'HeroImage' in vision_roles or 'Picture' in vision_roles:
                matches += 1
            else:
                adaptations.append("No image placeholder identified by vision")
        
        if slide.needs.has_table:
            requirements += 1
            if 'Table' in vision_roles:
                matches += 1
            else:
                adaptations.append("No table placeholder identified by vision")
        
        if slide.needs.has_chart:
            requirements += 1
            if 'Chart' in vision_roles:
                matches += 1
            else:
                adaptations.append("No chart placeholder identified by vision")
        
        # Calculate score
        if requirements > 0:
            score = matches / requirements
        else:
            score = 1.0 if placeable_count > 0 else 0.0
        
        return score, adaptations
    
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

    def _calculate_placement_penalty(self, layout: SlideLayoutSignature) -> float:
        """Calculate penalty for layouts with non-placeable areas"""
        penalty = 0.0
        total_shapes = len(layout.placeholders)
        non_placeable = 0
        
        for placeholder in layout.placeholders:
            if placeholder.vision and not placeholder.vision.place_content:
                non_placeable += 1
                # Higher penalty for decorative elements
                if placeholder.vision.role in ['Decor', 'Logo', 'Footer']:
                    penalty += 0.05
        
        # Don't penalize too much for brand elements
        if total_shapes > 0:
            penalty = min(penalty, 0.3)  # Cap at 30% penalty
        
        return penalty

    def match_slide_to_layout(
        self,
        slide: SlideSpec,
        template_profile: TemplateProfile
    ) -> SlideMapping:
        """
        Match a slide specification to the best available layout
        Uses ILP solver if enabled, otherwise falls back to greedy scoring
        
        Args:
            slide: Slide specification to match
            template_profile: Available template layouts
            
        Returns:
            SlideMapping with the best layout and placement info
        """
        # Use ILP solver if enabled
        if settings.ACCURATE_SOLVER_ENABLED:
            return self._match_with_ilp_solver(slide, template_profile)
        
        # Otherwise use original greedy scoring
        return self._match_with_greedy_scoring(slide, template_profile)
    
    def _match_with_ilp_solver(
        self,
        slide: SlideSpec,
        template_profile: TemplateProfile
    ) -> SlideMapping:
        """Match using ILP solver for optimal content placement"""
        
        # Prepare content items from slide spec
        content_items = []
        
        # Add title
        if slide.title:
            content_items.append({
                "id": "title",
                "type": "TITLE",
                "text": slide.title,
                "required": True,
                "size_hint": "S"
            })
        
        # Add subtitle if present
        if hasattr(slide, 'subtitle') and slide.subtitle:
            content_items.append({
                "id": "subtitle",
                "type": "SUBTITLE",
                "text": slide.subtitle,
                "required": False,
                "size_hint": "S"
            })
        
        # Add bullets as body content
        if slide.bullets:
            content_items.append({
                "id": "body",
                "type": "BODY",
                "text": "\n".join(f"• {b}" for b in slide.bullets),
                "required": True,
                "size_hint": self._estimate_content_size(slide.bullets)
            })
        
        # Add charts/tables/images if present
        if slide.needs.has_chart:
            content_items.append({
                "id": "chart",
                "type": "CHART",
                "required": True,
                "size_hint": "L"
            })
        
        if slide.needs.has_table:
            content_items.append({
                "id": "table",
                "type": "TABLE",
                "required": True,
                "size_hint": "L"
            })
        
        if slide.needs.has_picture:
            content_items.append({
                "id": "image",
                "type": "IMAGE",
                "required": True,
                "size_hint": "M"
            })
        
        # Prepare layouts with shape information
        layouts_for_solver = []
        for layout in template_profile.layout_catalog:
            layout_dict = {
                "name": layout.name,
                "layout_id": layout.layout_id,
                "archetype_hint": getattr(layout, 'archetype_hint', None),
                "slide_width": getattr(layout, 'slide_width', 1920),
                "slide_height": getattr(layout, 'slide_height', 1080),
                "shapes": []
            }
            
            for placeholder in layout.placeholders:
                shape = {
                    "id": f"shape_{placeholder.idx}",
                    "ph_type": placeholder.type.value if hasattr(placeholder.type, 'value') else str(placeholder.type),
                    "role": placeholder.name,
                    "bbox_px": getattr(placeholder, 'bbox_px', None),
                    "bbox_norm": getattr(placeholder, 'bbox_norm', None),
                    "place_ok": getattr(placeholder, 'place_ok', True),
                    "safety_penalty": getattr(placeholder, 'safety_penalty', 0.0),
                    "priority": 5,  # Default priority
                    "tags": []  # Could be populated from template metadata
                }
                
                # Add vision role if available
                if hasattr(placeholder, 'vision') and placeholder.vision:
                    shape["vision_role"] = placeholder.vision.role
                    shape["place_content"] = placeholder.vision.place_content
                    shape["priority"] = placeholder.vision.priority
                
                layout_dict["shapes"].append(shape)
            
            layouts_for_solver.append(layout_dict)
        
        # Use ILP solver to find optimal layout and mapping
        best_layout, mapping = choose_layout_and_mapping(
            layouts_for_solver,
            content_items,
            config={
                "timeout": settings.SOLVER_TIMEOUT,
                "msg": settings.SOLVER_MSG
            }
        )
        
        if not best_layout:
            # Fallback to greedy if solver fails
            logger.warning("ILP solver failed, falling back to greedy matching")
            return self._match_with_greedy_scoring(slide, template_profile)
        
        # Create SlideMapping from solver result
        adaptations = []
        
        # Check for unmapped required content
        for content in content_items:
            if content["required"] and content["id"] not in mapping:
                adaptations.append(f"Could not place {content['type']}: {content['id']}")
        
        # Calculate confidence based on mapping coverage
        mapped_count = len(mapping)
        total_count = len(content_items)
        confidence = (mapped_count / total_count) if total_count > 0 else 0.0
        
        return SlideMapping(
            slide_spec_id=slide.slide_id,
            layout_id=best_layout["layout_id"],
            layout_name=best_layout["name"],
            confidence_score=confidence,
            adaptations_needed=adaptations,
            content_mapping=mapping  # Store the actual mapping
        )
    
    def _estimate_content_size(self, bullets: List[str]) -> str:
        """Estimate content size hint based on bullet count and length"""
        if not bullets:
            return "XS"
        
        total_chars = sum(len(b) for b in bullets)
        bullet_count = len(bullets)
        
        if bullet_count <= 2 and total_chars < 100:
            return "S"
        elif bullet_count <= 4 and total_chars < 200:
            return "M"
        elif bullet_count <= 6 and total_chars < 400:
            return "L"
        else:
            return "XL"
    
    def _match_with_greedy_scoring(
        self,
        slide: SlideSpec,
        template_profile: TemplateProfile
    ) -> SlideMapping:
        """Original greedy scoring method"""
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

# Create singleton instance
layout_matcher = LayoutMatcher()