"""
Presentation Validator Service
Validates slide compositions and provides repair actions for issues
"""

import logging
from typing import List, Dict, Optional, Tuple
from pathlib import Path

from app.models import (
    SlideSpec, SlideComposition, SlideMapping, TemplateProfile,
    ValidationIssue, RepairAction, PresentationPlan
)
from app.services.slide_planner import slide_planner
from app.services.layout_matcher import layout_matcher

logger = logging.getLogger(__name__)

class PresentationValidator:
    """Validates presentations and suggests repairs"""
    
    def __init__(self):
        self.max_bullets_per_slide = 10
        self.max_title_length = 100
        self.max_bullet_length = 150
        self.max_repair_iterations = 3
    
    def validate_presentation(
        self,
        slides: List[SlideSpec],
        compositions: List[SlideComposition],
        mappings: List[SlideMapping],
        template_profile: TemplateProfile
    ) -> List[ValidationIssue]:
        """
        Validate entire presentation
        
        Args:
            slides: Original slide specifications
            compositions: Composition results
            mappings: Layout mappings
            template_profile: Template information
            
        Returns:
            List of validation issues found
        """
        issues = []
        
        for i, (slide, composition, mapping) in enumerate(zip(slides, compositions, mappings)):
            slide_issues = self._validate_slide(
                slide, composition, mapping, template_profile, i + 1
            )
            issues.extend(slide_issues)
        
        # Check presentation-level issues
        presentation_issues = self._validate_presentation_level(slides, template_profile)
        issues.extend(presentation_issues)
        
        return issues
    
    def _validate_slide(
        self,
        slide: SlideSpec,
        composition: SlideComposition,
        mapping: SlideMapping,
        template_profile: TemplateProfile,
        slide_number: int
    ) -> List[ValidationIssue]:
        """Validate a single slide"""
        
        issues = []
        
        # Check composition success
        if not composition.success:
            issues.append(ValidationIssue(
                slide_number=slide_number,
                issue_type="composition_failure",
                description=f"Slide composition failed: {', '.join(composition.issues)}",
                severity="error",
                suggested_fix="Try different layout or simplify content"
            ))
        
        # Check for overflow
        if composition.overflow_text:
            issues.append(ValidationIssue(
                slide_number=slide_number,
                issue_type="overflow",
                description=f"Content overflow: {len(composition.overflow_text.split())} words don't fit",
                severity="warning",
                suggested_fix="Split slide or condense content"
            ))
        
        # Check title length
        if slide.title and len(slide.title) > self.max_title_length:
            issues.append(ValidationIssue(
                slide_number=slide_number,
                issue_type="title_too_long",
                description=f"Title exceeds {self.max_title_length} characters",
                severity="warning",
                suggested_fix="Shorten title"
            ))
        
        # Check bullet count
        if len(slide.bullets) > self.max_bullets_per_slide:
            issues.append(ValidationIssue(
                slide_number=slide_number,
                issue_type="too_many_bullets",
                description=f"Slide has {len(slide.bullets)} bullets (max: {self.max_bullets_per_slide})",
                severity="warning",
                suggested_fix="Split into multiple slides"
            ))
        
        # Check bullet lengths
        long_bullets = [b for b in slide.bullets if len(b) > self.max_bullet_length]
        if long_bullets:
            issues.append(ValidationIssue(
                slide_number=slide_number,
                issue_type="bullets_too_long",
                description=f"{len(long_bullets)} bullets exceed {self.max_bullet_length} characters",
                severity="info",
                suggested_fix="Condense bullet points"
            ))
        
        # Check layout fit confidence
        if mapping.confidence_score < 0.5:
            issues.append(ValidationIssue(
                slide_number=slide_number,
                issue_type="poor_layout_match",
                description=f"Layout match confidence low ({mapping.confidence_score:.2f})",
                severity="warning",
                suggested_fix="Consider different layout or adapt content"
            ))
        
        # Check for missing required placeholders
        if composition.missing_placeholders:
            issues.append(ValidationIssue(
                slide_number=slide_number,
                issue_type="missing_placeholders",
                description=f"Missing placeholders: {', '.join(composition.missing_placeholders)}",
                severity="error",
                suggested_fix="Change layout or remove content requiring missing placeholders"
            ))
        
        return issues
    
    def _validate_presentation_level(
        self,
        slides: List[SlideSpec],
        template_profile: TemplateProfile
    ) -> List[ValidationIssue]:
        """Validate presentation-level issues"""
        
        issues = []
        
        # Check if presentation is too long
        if len(slides) > 30:
            issues.append(ValidationIssue(
                slide_number=0,
                issue_type="presentation_too_long",
                description=f"Presentation has {len(slides)} slides (recommended max: 30)",
                severity="info",
                suggested_fix="Consider splitting into multiple presentations"
            ))
        
        # Check if presentation is too short
        if len(slides) < 3:
            issues.append(ValidationIssue(
                slide_number=0,
                issue_type="presentation_too_short",
                description=f"Presentation has only {len(slides)} slides",
                severity="info",
                suggested_fix="Add more content or combine with related topics"
            ))
        
        # Check for title slide
        if slides and not any(word in slides[0].title.lower() 
                             for word in ['welcome', 'introduction', 'title', 'agenda']):
            issues.append(ValidationIssue(
                slide_number=1,
                issue_type="missing_title_slide",
                description="First slide doesn't appear to be a title slide",
                severity="info",
                suggested_fix="Add a proper title slide"
            ))
        
        return issues
    
    def suggest_repairs(
        self,
        issues: List[ValidationIssue],
        slides: List[SlideSpec],
        mappings: List[SlideMapping],
        template_profile: TemplateProfile
    ) -> List[RepairAction]:
        """
        Suggest repair actions for validation issues
        
        Args:
            issues: List of validation issues
            slides: Current slide specifications
            mappings: Current layout mappings
            template_profile: Template information
            
        Returns:
            List of suggested repair actions
        """
        repairs = []
        processed_slides = set()
        
        for issue in issues:
            if issue.slide_number in processed_slides:
                continue  # Only one repair per slide
            
            repair = self._suggest_repair_for_issue(
                issue, slides, mappings, template_profile
            )
            
            if repair:
                repairs.append(repair)
                processed_slides.add(issue.slide_number)
        
        return repairs
    
    def _suggest_repair_for_issue(
        self,
        issue: ValidationIssue,
        slides: List[SlideSpec],
        mappings: List[SlideMapping],
        template_profile: TemplateProfile
    ) -> Optional[RepairAction]:
        """Suggest repair for a specific issue"""
        
        if issue.slide_number == 0:
            # Presentation-level issue, no specific repair
            return None
        
        slide_idx = issue.slide_number - 1
        if slide_idx >= len(slides):
            return None
        
        slide = slides[slide_idx]
        mapping = mappings[slide_idx] if slide_idx < len(mappings) else None
        
        if issue.issue_type == "overflow":
            return RepairAction(
                slide_number=issue.slide_number,
                action_type="split",
                parameters={
                    "split_point": len(slide.bullets) // 2,
                    "reason": "Content overflow"
                }
            )
        
        elif issue.issue_type == "too_many_bullets":
            return RepairAction(
                slide_number=issue.slide_number,
                action_type="split",
                parameters={
                    "split_point": self.max_bullets_per_slide,
                    "reason": "Too many bullet points"
                }
            )
        
        elif issue.issue_type == "poor_layout_match":
            # Suggest layout change
            if mapping:
                alt_mapping = layout_matcher.suggest_layout_change(
                    slide, mapping.layout_id, template_profile, "poor_match"
                )
                if alt_mapping:
                    return RepairAction(
                        slide_number=issue.slide_number,
                        action_type="change_layout",
                        parameters={
                            "new_layout_id": alt_mapping.layout_id,
                            "new_layout_name": alt_mapping.layout_name,
                            "reason": "Better layout match available"
                        }
                    )
            
            # If no better layout, suggest content adaptation
            return RepairAction(
                slide_number=issue.slide_number,
                action_type="condense",
                parameters={
                    "target_bullets": 5,
                    "reason": "Simplify for better layout fit"
                }
            )
        
        elif issue.issue_type == "bullets_too_long":
            return RepairAction(
                slide_number=issue.slide_number,
                action_type="condense",
                parameters={
                    "max_length": self.max_bullet_length,
                    "reason": "Bullet points too verbose"
                }
            )
        
        elif issue.issue_type == "title_too_long":
            return RepairAction(
                slide_number=issue.slide_number,
                action_type="condense",
                parameters={
                    "target": "title",
                    "max_length": self.max_title_length,
                    "reason": "Title too long"
                }
            )
        
        return None
    
    async def apply_repairs(
        self,
        repairs: List[RepairAction],
        presentation_plan: PresentationPlan,
        template_profile: TemplateProfile
    ) -> PresentationPlan:
        """
        Apply repair actions to create an updated presentation plan
        
        Args:
            repairs: List of repair actions to apply
            presentation_plan: Current presentation plan
            template_profile: Template information
            
        Returns:
            Updated PresentationPlan
        """
        slides = presentation_plan.slides.copy()
        
        # Sort repairs by slide number (reverse) to handle splits correctly
        repairs.sort(key=lambda r: r.slide_number, reverse=True)
        
        for repair in repairs:
            if repair.slide_number == 0:
                continue  # Skip presentation-level repairs
            
            slide_idx = repair.slide_number - 1
            if slide_idx >= len(slides):
                continue
            
            if repair.action_type == "split":
                slides = await self._apply_split(
                    slides, slide_idx, repair.parameters
                )
            
            elif repair.action_type == "condense":
                slides = await self._apply_condense(
                    slides, slide_idx, repair.parameters, template_profile
                )
            
            elif repair.action_type == "change_layout":
                # Layout change doesn't affect slide spec, handled in mapping
                pass
            
            elif repair.action_type == "merge":
                slides = await self._apply_merge(
                    slides, slide_idx, repair.parameters
                )
        
        # Create updated plan
        updated_plan = PresentationPlan(
            session_id=presentation_plan.session_id,
            slides=slides,
            metadata=presentation_plan.metadata
        )
        
        return updated_plan
    
    async def _apply_split(
        self,
        slides: List[SlideSpec],
        slide_idx: int,
        parameters: Dict
    ) -> List[SlideSpec]:
        """Split a slide into multiple slides"""
        
        slide = slides[slide_idx]
        split_point = parameters.get("split_point", len(slide.bullets) // 2)
        
        # Create two slides from one
        slide1 = SlideSpec(
            slide_id=f"{slide.slide_id}_1",
            title=f"{slide.title} (Part 1)",
            bullets=slide.bullets[:split_point],
            speaker_notes=slide.speaker_notes,
            needs=slide.needs
        )
        
        slide2 = SlideSpec(
            slide_id=f"{slide.slide_id}_2",
            title=f"{slide.title} (Part 2)",
            bullets=slide.bullets[split_point:],
            speaker_notes="",
            needs=slide.needs
        )
        
        # Replace original with two new slides
        new_slides = slides[:slide_idx] + [slide1, slide2] + slides[slide_idx + 1:]
        
        logger.info(f"Split slide {slide_idx + 1} into two slides")
        return new_slides
    
    async def _apply_condense(
        self,
        slides: List[SlideSpec],
        slide_idx: int,
        parameters: Dict,
        template_profile: TemplateProfile
    ) -> List[SlideSpec]:
        """Condense slide content"""
        
        slide = slides[slide_idx]
        
        # Use LLM to condense content
        target_layout = {
            "max_bullets": parameters.get("target_bullets", 5),
            "max_bullet_length": parameters.get("max_length", self.max_bullet_length)
        }
        
        condensed_slide = await slide_planner.adapt_slide_for_layout(
            slide, target_layout, "condense"
        )
        
        slides[slide_idx] = condensed_slide
        logger.info(f"Condensed slide {slide_idx + 1}")
        
        return slides
    
    async def _apply_merge(
        self,
        slides: List[SlideSpec],
        slide_idx: int,
        parameters: Dict
    ) -> List[SlideSpec]:
        """Merge two slides into one"""
        
        if slide_idx + 1 >= len(slides):
            return slides  # Can't merge last slide
        
        slide1 = slides[slide_idx]
        slide2 = slides[slide_idx + 1]
        
        # Merge slides
        merged_slide = SlideSpec(
            slide_id=f"{slide1.slide_id}_merged",
            title=slide1.title,  # Keep first title
            bullets=slide1.bullets + slide2.bullets,
            speaker_notes=f"{slide1.speaker_notes or ''}\n{slide2.speaker_notes or ''}".strip(),
            needs=slide1.needs  # Keep first slide's needs
        )
        
        # Replace two slides with merged one
        new_slides = slides[:slide_idx] + [merged_slide] + slides[slide_idx + 2:]
        
        logger.info(f"Merged slides {slide_idx + 1} and {slide_idx + 2}")
        return new_slides
    
    async def repair_loop(
        self,
        presentation_plan: PresentationPlan,
        compositions: List[SlideComposition],
        mappings: List[SlideMapping],
        template_profile: TemplateProfile,
        max_iterations: Optional[int] = None
    ) -> Tuple[PresentationPlan, List[SlideMapping], List[ValidationIssue]]:
        """
        Run validation and repair loop until presentation is valid or max iterations reached
        
        Args:
            presentation_plan: Initial presentation plan
            compositions: Initial composition results
            mappings: Initial layout mappings
            template_profile: Template information
            max_iterations: Maximum repair iterations (default: self.max_repair_iterations)
            
        Returns:
            Tuple of (final_plan, final_mappings, remaining_issues)
        """
        max_iterations = max_iterations or self.max_repair_iterations
        current_plan = presentation_plan
        current_mappings = mappings
        
        for iteration in range(max_iterations):
            logger.info(f"Repair iteration {iteration + 1}")
            
            # Validate
            issues = self.validate_presentation(
                current_plan.slides,
                compositions,
                current_mappings,
                template_profile
            )
            
            # Check if valid
            critical_issues = [i for i in issues if i.severity == "error"]
            if not critical_issues:
                logger.info("No critical issues found, validation complete")
                return current_plan, current_mappings, issues
            
            # Suggest repairs
            repairs = self.suggest_repairs(
                critical_issues,
                current_plan.slides,
                current_mappings,
                template_profile
            )
            
            if not repairs:
                logger.info("No repairs suggested, stopping")
                return current_plan, current_mappings, issues
            
            # Apply repairs
            current_plan = await self.apply_repairs(
                repairs,
                current_plan,
                template_profile
            )
            
            # Re-match layouts after repairs
            current_mappings = layout_matcher.match_slides_to_layouts(
                current_plan.slides,
                template_profile
            )
            
            # Note: In production, would also re-compose here
        
        logger.warning(f"Max repair iterations ({max_iterations}) reached")
        return current_plan, current_mappings, issues

# Create singleton instance
presentation_validator = PresentationValidator()