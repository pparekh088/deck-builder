"""
Simple Slide Tools for Agentic System
Clean, focused tools for slide manipulation
"""

import logging
import json
import base64
import io
import asyncio
from typing import List, Optional
from pathlib import Path
from pptx import Presentation
from pptx.enum.shapes import PP_PLACEHOLDER
from pptx.util import Pt
from pptx.dml.color import RGBColor
from PIL import Image
from app.services.openai_service import openai_service

logger = logging.getLogger(__name__)

class SimpleSlideTools:
    """Simple, reliable tools for slide manipulation"""
    
    def edit_slide_content(
        self, 
        presentation_path: Path, 
        slide_number: int, 
        new_title: Optional[str] = None,
        add_bullets: Optional[List[str]] = None,
        replace_bullets: Optional[List[str]] = None
    ) -> str:
        """Edit content of an existing slide"""
        try:
            logger.info(f"Editing slide {slide_number}: title={new_title}, add_bullets={add_bullets}, replace_bullets={replace_bullets}")
            
            prs = Presentation(str(presentation_path))
            
            if slide_number < 1 or slide_number > len(prs.slides):
                return f"Error: Invalid slide number {slide_number}"
            
            slide = prs.slides[slide_number - 1]
            logger.info(f"Found slide {slide_number} with {len(slide.shapes)} shapes")
            
            # Update title
            if new_title:
                title_shape = self._find_title_shape(slide)
                if title_shape:
                    if hasattr(title_shape, 'text_frame'):
                        title_shape.text_frame.clear()
                        p = title_shape.text_frame.paragraphs[0]
                        p.text = new_title
                        # Ensure good contrast
                        for run in p.runs:
                            run.font.color.rgb = RGBColor(255, 255, 255)
                    else:
                        title_shape.text = new_title
            
            # Update content
            if replace_bullets is not None:
                content_shape = self._find_content_shape(slide)
                if content_shape and hasattr(content_shape, 'text_frame'):
                    content_shape.text_frame.clear()
                    for bullet in replace_bullets:
                        p = content_shape.text_frame.add_paragraph()
                        p.text = f"• {bullet}"
                        for run in p.runs:
                            run.font.color.rgb = RGBColor(255, 255, 255)
            
            elif add_bullets:
                content_shape = self._find_content_shape(slide)
                logger.info(f"Found content shape: {content_shape is not None}")
                
                if content_shape and hasattr(content_shape, 'text_frame'):
                    # ADD to existing content, don't replace
                    existing_paragraphs = len(content_shape.text_frame.paragraphs)
                    logger.info(f"Content shape has {existing_paragraphs} existing paragraphs")
                    logger.info(f"Adding {len(add_bullets)} bullets to existing content: {add_bullets}")
                    
                    for bullet in add_bullets:
                        p = content_shape.text_frame.add_paragraph()
                        p.text = f"• {bullet}"
                        for run in p.runs:
                            run.font.color.rgb = RGBColor(255, 255, 255)
                    
                    final_paragraphs = len(content_shape.text_frame.paragraphs)
                    logger.info(f"After adding: {final_paragraphs} total paragraphs")
                    
                elif content_shape:
                    # Fallback for shapes without text_frame
                    existing_text = getattr(content_shape, 'text', '')
                    logger.info(f"Using text fallback. Existing text: {existing_text[:50]}...")
                    new_bullets = '\n'.join(f"• {bullet}" for bullet in add_bullets)
                    content_shape.text = f"{existing_text}\n{new_bullets}" if existing_text else new_bullets
                else:
                    logger.warning("No content shape found on slide")
            
            prs.save(str(presentation_path))
            return f"Successfully edited slide {slide_number}"
            
        except Exception as e:
            logger.error(f"Error editing slide: {e}")
            return f"Error editing slide: {str(e)}"
    
    async def add_new_slide(
        self,
        presentation_path: Path,
        title: str,
        bullets: List[str],
        position: Optional[int] = None
    ) -> str:
        """Add a new slide to the presentation"""
        try:
            if not presentation_path.exists():
                return f"Error: Presentation file not found at {presentation_path}"
                
            logger.info(f"Loading presentation from {presentation_path}")
            prs = Presentation(str(presentation_path))
            logger.info(f"Presentation loaded, has {len(prs.slides)} slides")
            
            # Find the best matching slide using detailed text-based LLM evaluation
            logger.info("Finding best matching slide using detailed LLM analysis...")
            try:
                template_slide = await self._find_best_matching_slide_with_detailed_llm(prs, title, bullets)
                logger.info(f"Detailed LLM slide matching completed, found: {template_slide is not None}")
            except Exception as e:
                logger.error(f"Error in detailed LLM slide matching: {e}")
                # Fallback to rule-based matching
                template_slide = self._find_best_matching_slide(prs, title, bullets)
                logger.info(f"Fallback to rule-based matching, found: {template_slide is not None}")
            
            if template_slide:
                logger.info("Found template slide, using its layout")
                try:
                    # Use the same layout as the matching slide
                    layout = template_slide.slide_layout
                    logger.info(f"Template slide layout: {layout.name}")
                    
                    # Check if layout is blank or unsuitable
                    if "blank" in layout.name.lower() or "title_only" in layout.name.lower():
                        logger.warning(f"Template slide has blank/unsuitable layout '{layout.name}', using fallback")
                        layout = self._find_best_layout_for_content(prs, title, bullets)
                        logger.info(f"Using fallback layout: {layout.name}")
                    
                    logger.info(f"Adding new slide with layout: {layout.name}")
                    new_slide = prs.slides.add_slide(layout)
                    logger.info("New slide added, filling with template formatting")
                    # Fill content with formatting copied from the matching slide
                    self._fill_slide_with_template_formatting(new_slide, title, bullets, template_slide)
                except Exception as e:
                    logger.error(f"Error using template slide layout: {e}")
                    # Fallback to basic layout
                    layout = self._find_best_layout_for_content(prs, title, bullets)
                    logger.info(f"Using fallback layout: {layout.name}")
                    new_slide = prs.slides.add_slide(layout)
                    self._fill_slide_with_formatting(new_slide, title, bullets, prs)
            else:
                logger.info("No template slide found, using fallback method")
                # Fallback to old method if no good match found
                layout = self._find_best_layout_for_content(prs, title, bullets)
                logger.info(f"Adding new slide with fallback layout: {layout.name}")
                new_slide = prs.slides.add_slide(layout)
                logger.info("New slide added, filling with general formatting")
                self._fill_slide_with_formatting(new_slide, title, bullets, prs)
            
            logger.info("Saving presentation...")
            prs.save(str(presentation_path))
            logger.info("Presentation saved successfully")
            return f"Successfully added slide: {title}"
            
        except Exception as e:
            logger.error(f"Error adding slide: {e}")
            return f"Error adding slide: {str(e)}"
    
    def delete_slide(self, presentation_path: Path, slide_number: int) -> str:
        """Delete a slide from the presentation"""
        try:
            prs = Presentation(str(presentation_path))
            
            if slide_number < 1 or slide_number > len(prs.slides):
                return f"Error: Invalid slide number {slide_number}"
            
            slide_idx = slide_number - 1
            rId = prs.slides._sldIdLst[slide_idx].rId
            prs.part.drop_rel(rId)
            del prs.slides._sldIdLst[slide_idx]
            
            prs.save(str(presentation_path))
            return f"Successfully deleted slide {slide_number}"
            
        except Exception as e:
            logger.error(f"Error deleting slide: {e}")
            return f"Error deleting slide: {str(e)}"
    
    def _find_title_shape(self, slide):
        """Find title shape on slide"""
        # Try placeholders first
        for shape in slide.shapes:
            try:
                if hasattr(shape, 'is_placeholder') and shape.is_placeholder:
                    if hasattr(shape, 'placeholder_format') and shape.placeholder_format:
                        if shape.placeholder_format.type == PP_PLACEHOLDER.TITLE:
                            return shape
            except Exception:
                continue
        
        # Fallback to first text shape
        for shape in slide.shapes:
            try:
                if hasattr(shape, 'text_frame') and shape.text_frame:
                    return shape
            except Exception:
                continue
        
        return None
    
    def _find_content_shape(self, slide):
        """Find content/body shape on slide"""
        # Try placeholders first
        for shape in slide.shapes:
            try:
                if hasattr(shape, 'is_placeholder') and shape.is_placeholder:
                    if hasattr(shape, 'placeholder_format') and shape.placeholder_format:
                        if shape.placeholder_format.type in [PP_PLACEHOLDER.BODY, PP_PLACEHOLDER.OBJECT]:
                            return shape
            except Exception:
                continue
        
        # Fallback to second text shape (first is likely title)
        text_shapes = []
        for shape in slide.shapes:
            try:
                if hasattr(shape, 'text_frame') and shape.text_frame:
                    text_shapes.append(shape)
            except Exception:
                continue
                
        if len(text_shapes) > 1:
            return text_shapes[1]
        elif len(text_shapes) == 1:
            return text_shapes[0]
        
        return None
    
    def _filter_content_slides(self, prs):
        """Filter slides to exclude intro/outro slides and return only content slides"""
        
        content_slides = []
        total_slides = len(prs.slides)
        
        for i, slide in enumerate(prs.slides):
            slide_number = i + 1
            
            logger.info(f"Evaluating slide {slide_number} of {total_slides}")
            
            # Skip first slide (usually title/intro)
            if slide_number == 1:
                logger.info(f"Skipping slide {slide_number}: First slide (likely intro)")
                continue
            
            # Skip last slide only if it looks like a thank you slide
            if slide_number == total_slides:
                title_shape = self._find_title_shape(slide)
                slide_title = ""
                if title_shape and hasattr(title_shape, 'text_frame'):
                    slide_title = title_shape.text_frame.text.strip().lower()
                
                # Only skip if it actually contains thank you keywords
                if any(keyword in slide_title for keyword in ['thank you', 'thanks', 'questions', 'q&a']):
                    logger.info(f"Skipping slide {slide_number}: Last slide with thank you content '{slide_title}'")
                    continue
                else:
                    logger.info(f"Keeping slide {slide_number}: Last slide but no thank you content '{slide_title}'")
            
            # Get slide title (reuse from above if we already got it)
            if slide_number != total_slides:
                title_shape = self._find_title_shape(slide)
                slide_title = ""
                if title_shape and hasattr(title_shape, 'text_frame'):
                    slide_title = title_shape.text_frame.text.strip().lower()
            
            # Skip slides with intro/outro keywords
            intro_outro_keywords = [
                'thank you', 'thanks', 'questions', 'q&a', 'contact', 
                'agenda', 'outline', 'overview', 'introduction', 'intro',
                'conclusion', 'summary', 'next steps', 'follow up'
                # Removed 'award', 'winning' as these might be in content slides
            ]
            
            is_intro_outro = any(keyword in slide_title for keyword in intro_outro_keywords)
            if is_intro_outro:
                logger.info(f"Skipping slide {slide_number}: Contains intro/outro keyword '{[k for k in intro_outro_keywords if k in slide_title]}' in title '{slide_title}'")
                continue
            
            # Check content density - skip slides with very little content
            content_shape = self._find_content_shape(slide)
            bullet_count = 0
            if content_shape and hasattr(content_shape, 'text_frame'):
                for p in content_shape.text_frame.paragraphs:
                    if p.text.strip():
                        bullet_count += 1
            
            # Skip slides with no content (likely dividers or special slides)
            if bullet_count == 0:
                logger.info(f"Skipping slide {slide_number}: No content bullets found")
                continue
            
            # Check slide layout - skip blank or unsuitable layouts
            layout_name = slide.slide_layout.name.lower()
            if "blank" in layout_name or "title_only" in layout_name:
                logger.info(f"Skipping slide {slide_number}: Has blank/unsuitable layout '{slide.slide_layout.name}'")
                continue
            
            # This looks like a good content slide
            logger.info(f"Including slide {slide_number}: '{slide_title}' with {bullet_count} bullets, layout: {slide.slide_layout.name}")
            content_slides.append(slide)
        
        return content_slides
    
    async def _find_best_matching_slide_with_detailed_llm(self, prs, title: str, bullets: List[str]):
        """Use LLM to evaluate slide images and select the best template slide"""
        
        # Skip first and last slides (intro/outro)
        candidate_slides = []
        total_slides = len(prs.slides)
        
        for i, slide in enumerate(prs.slides):
            slide_number = i + 1
            
            # Skip first slide (intro) and last slide (outro)
            if slide_number == 1 or slide_number == total_slides:
                continue
                
            candidate_slides.append((slide_number, slide))
        
        if not candidate_slides:
            logger.warning("No candidate slides found for LLM evaluation")
            return None
        
        logger.info(f"Evaluating {len(candidate_slides)} candidate slides with detailed LLM analysis")
        
        # Prepare detailed slide information for LLM
        slide_descriptions = []
        
        for slide_number, slide in candidate_slides:
            # Extract comprehensive slide details
            slide_details = await self._extract_detailed_slide_info(slide, slide_number)
            slide_descriptions.append(slide_details)
        
        # Prepare LLM prompt
        target_info = {
            "title": title,
            "bullets": bullets,
            "bullet_count": len(bullets)
        }
        
        llm_prompt = f"""You are selecting the best template slide to copy formatting from based on detailed slide analysis.

TARGET SLIDE TO CREATE:
- Title: "{title}"
- Content: {len(bullets)} bullet points
- Bullets: {bullets}

CANDIDATE TEMPLATE SLIDES (detailed analysis):
{json.dumps(slide_descriptions, indent=2)}

SELECTION CRITERIA:
1. **Content Structure Match**: Similar bullet count and content organization
2. **Layout Quality**: Professional layout with good visual hierarchy
3. **Template Consistency**: Consistent styling and branding elements
4. **Visual Elements**: Appropriate background, colors, and design elements
5. **Orientation Match**: Similar text orientation and layout direction
6. **Avoid**: Blank slides, title-only slides, special/decorative slides, intro/outro slides

INSTRUCTIONS:
- Analyze the detailed slide information provided
- Choose the slide that would provide the best template for the new slide
- Prioritize slides with similar content structure and professional appearance
- Consider background colors, themes, layout orientation, and visual elements
- Prefer slides with meaningful content over special/decorative slides

Return ONLY the slide number (integer) of the best match, nothing else."""

        try:
            # Call OpenAI API with detailed text analysis
            response = await asyncio.to_thread(
                openai_service.client.chat.completions.create,
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an expert at matching slide templates based on detailed slide analysis."},
                    {"role": "user", "content": llm_prompt}
                ],
                max_tokens=10,
                temperature=0.1
            )
            
            # Parse response
            result_text = response.choices[0].message.content.strip()
            selected_slide_number = int(result_text)
            
            logger.info(f"LLM selected slide {selected_slide_number} as best match")
            
            # Find and return the selected slide
            for slide_number, slide in candidate_slides:
                if slide_number == selected_slide_number:
                    logger.info(f"Selected slide {selected_slide_number}: '{slide_descriptions[slide_number-2]['title']}'")
                    return slide
            
            logger.warning(f"LLM selected slide {selected_slide_number} but it's not in candidates")
            return None
            
        except Exception as e:
            logger.error(f"Error in LLM slide selection: {e}")
            raise e
    
    async def _extract_detailed_slide_info(self, slide, slide_number: int) -> dict:
        """Extract comprehensive slide information for LLM analysis"""
        try:
            slide_info = {
                "slide_number": slide_number,
                "layout_name": slide.slide_layout.name,
            }
            
            # Extract title information
            title_shape = self._find_title_shape(slide)
            if title_shape and hasattr(title_shape, 'text_frame'):
                slide_info["title"] = title_shape.text_frame.text.strip()
                slide_info["has_title"] = True
                
                # Try to get title formatting details
                try:
                    if title_shape.text_frame.paragraphs:
                        first_para = title_shape.text_frame.paragraphs[0]
                        if first_para.runs:
                            first_run = first_para.runs[0]
                            slide_info["title_font_name"] = getattr(first_run.font, 'name', 'Unknown')
                            slide_info["title_font_size"] = str(getattr(first_run.font, 'size', 'Unknown'))
                            slide_info["title_bold"] = getattr(first_run.font, 'bold', False)
                            
                            # Try to get color info
                            try:
                                if hasattr(first_run.font, 'color') and hasattr(first_run.font.color, 'rgb'):
                                    rgb = first_run.font.color.rgb
                                    slide_info["title_color"] = f"RGB({rgb.red}, {rgb.green}, {rgb.blue})"
                                else:
                                    slide_info["title_color"] = "Theme color"
                            except:
                                slide_info["title_color"] = "Unknown"
                except Exception as e:
                    logger.debug(f"Could not extract title formatting: {e}")
            else:
                slide_info["title"] = "No title"
                slide_info["has_title"] = False
            
            # Extract content information
            content_shape = self._find_content_shape(slide)
            bullet_count = 0
            bullets_preview = []
            content_orientation = "horizontal"
            
            if content_shape and hasattr(content_shape, 'text_frame'):
                for p in content_shape.text_frame.paragraphs:
                    if p.text.strip():
                        bullet_count += 1
                        bullets_preview.append(p.text.strip()[:40])  # First 40 chars
                        
                        # Check for vertical text (simple heuristic)
                        if len(p.text.strip()) < 5 and bullet_count > 3:
                            content_orientation = "possibly_vertical"
                
                # Try to get content formatting
                try:
                    if content_shape.text_frame.paragraphs:
                        first_para = content_shape.text_frame.paragraphs[0]
                        if first_para.runs:
                            first_run = first_para.runs[0]
                            slide_info["content_font_name"] = getattr(first_run.font, 'name', 'Unknown')
                            slide_info["content_font_size"] = str(getattr(first_run.font, 'size', 'Unknown'))
                except Exception as e:
                    logger.debug(f"Could not extract content formatting: {e}")
            
            slide_info["bullet_count"] = bullet_count
            slide_info["content_preview"] = bullets_preview[:3]  # First 3 bullets
            slide_info["content_orientation"] = content_orientation
            slide_info["has_content"] = bullet_count > 0
            
            # Analyze slide shapes for additional elements
            shape_analysis = self._analyze_slide_shapes(slide)
            slide_info.update(shape_analysis)
            
            # Try to get background/theme information
            try:
                slide_info["slide_layout_type"] = self._classify_layout_type(slide.slide_layout.name)
            except:
                slide_info["slide_layout_type"] = "unknown"
            
            return slide_info
            
        except Exception as e:
            logger.error(f"Error extracting slide info: {e}")
            return {
                "slide_number": slide_number,
                "error": f"Could not analyze slide: {str(e)}",
                "layout_name": "unknown"
            }
    
    def _analyze_slide_shapes(self, slide) -> dict:
        """Analyze slide shapes for images, tables, charts, etc."""
        analysis = {
            "has_images": False,
            "has_tables": False,
            "has_charts": False,
            "total_shapes": len(slide.shapes),
            "shape_types": [],
            "background_elements": 0
        }
        
        try:
            for shape in slide.shapes:
                # Check shape types
                if hasattr(shape, 'shape_type'):
                    shape_type_name = str(shape.shape_type)
                    analysis["shape_types"].append(shape_type_name)
                    
                    if 'PICTURE' in shape_type_name or 'IMAGE' in shape_type_name:
                        analysis["has_images"] = True
                    elif 'TABLE' in shape_type_name:
                        analysis["has_tables"] = True
                    elif 'CHART' in shape_type_name:
                        analysis["has_charts"] = True
                
                # Count non-placeholder shapes (background elements)
                try:
                    if not (hasattr(shape, 'is_placeholder') and shape.is_placeholder):
                        analysis["background_elements"] += 1
                except:
                    pass
                    
        except Exception as e:
            logger.debug(f"Error analyzing shapes: {e}")
        
        return analysis
    
    def _classify_layout_type(self, layout_name: str) -> str:
        """Classify layout type based on name"""
        name_lower = layout_name.lower()
        
        if 'title' in name_lower and 'content' in name_lower:
            return "title_and_content"
        elif 'title' in name_lower and 'only' in name_lower:
            return "title_only"
        elif 'blank' in name_lower:
            return "blank"
        elif 'two' in name_lower and 'column' in name_lower:
            return "two_column"
        elif 'comparison' in name_lower:
            return "comparison"
        elif 'section' in name_lower:
            return "section_header"
        else:
            return "content"
    
    def _find_best_matching_slide(self, prs, title: str, bullets: List[str]):
        """Find the existing slide that best matches the new content structure"""
        
        target_bullet_count = len(bullets)
        best_match = None
        best_score = -1
        
        # Filter out intro/outro slides and get content slides only
        content_slides = self._filter_content_slides(prs)
        logger.info(f"Found {len(content_slides)} content slides to check from {len(prs.slides)} total slides")
        
        for slide in content_slides:
            score = 0
            
            # Check if slide has title
            title_shape = self._find_title_shape(slide)
            has_title = title_shape and hasattr(title_shape, 'text_frame') and title_shape.text_frame.text.strip()
            
            # Check content structure
            content_shape = self._find_content_shape(slide)
            slide_bullet_count = 0
            
            if content_shape and hasattr(content_shape, 'text_frame'):
                # Count paragraphs with content
                for p in content_shape.text_frame.paragraphs:
                    if p.text.strip():
                        slide_bullet_count += 1
            
            # Get slide title for logging
            slide_title = ""
            if title_shape and hasattr(title_shape, 'text_frame'):
                slide_title = title_shape.text_frame.text.strip()
            
            # Scoring criteria
            if has_title and title:
                score += 2  # Both have titles
            elif not has_title and not title:
                score += 1  # Neither have titles
            
            # Match bullet count (prefer exact match, but close is good too)
            if slide_bullet_count == target_bullet_count:
                score += 10  # Perfect match - highly preferred
            elif abs(slide_bullet_count - target_bullet_count) <= 1:
                score += 7   # Very close match
            elif abs(slide_bullet_count - target_bullet_count) <= 2:
                score += 4   # Close match
            elif slide_bullet_count > 0 and target_bullet_count > 0:
                score += 2   # Both have content
            
            # Prefer slides with similar content density
            if slide_bullet_count >= 4 and target_bullet_count >= 4:
                score += 3  # Both are content-heavy
            elif slide_bullet_count >= 2 and target_bullet_count >= 2:
                score += 2  # Both have substantial content
            elif slide_bullet_count <= 2 and target_bullet_count <= 2:
                score += 1  # Both are light content
            
            # Bonus for middle slides (more likely to be good content templates)
            slide_position = list(prs.slides).index(slide) + 1
            total_slides = len(prs.slides)
            if 0.2 * total_slides < slide_position < 0.8 * total_slides:
                score += 1  # Middle slides bonus
            
            logger.info(f"Slide {slide_position} '{slide_title[:30]}...' score: {score} (bullets: {slide_bullet_count} vs target: {target_bullet_count})")
            
            if score > best_score:
                best_score = score
                best_match = slide
                logger.info(f"New best match: Slide {slide_position} with score {score}")
        
        logger.info(f"Best matching slide found with score: {best_score}")
        return best_match if best_score > 0 else None
    
    def _fill_slide_with_template_formatting(self, new_slide, title: str, bullets: List[str], template_slide):
        """Fill new slide with content using formatting from template slide"""
        
        # Fill title with template formatting
        title_shape = self._find_title_shape(new_slide)
        template_title_shape = self._find_title_shape(template_slide)
        
        if title_shape and hasattr(title_shape, 'text_frame'):
            title_shape.text_frame.clear()
            p = title_shape.text_frame.paragraphs[0]
            p.text = title
            
            # Copy formatting from template slide's title
            if template_title_shape and hasattr(template_title_shape, 'text_frame'):
                template_paragraphs = template_title_shape.text_frame.paragraphs
                if template_paragraphs:
                    self._copy_paragraph_formatting(p, template_paragraphs[0])
        
        # Fill content with template formatting
        content_shape = self._find_content_shape(new_slide)
        template_content_shape = self._find_content_shape(template_slide)
        
        if content_shape and hasattr(content_shape, 'text_frame') and bullets:
            content_shape.text_frame.clear()
            
            # Get template content formatting
            template_formats = []
            if template_content_shape and hasattr(template_content_shape, 'text_frame'):
                template_formats = [p for p in template_content_shape.text_frame.paragraphs if p.text.strip()]
            
            # Add bullets with template formatting
            for i, bullet in enumerate(bullets):
                if i == 0:
                    p = content_shape.text_frame.paragraphs[0]
                else:
                    p = content_shape.text_frame.add_paragraph()
                
                p.text = f"• {bullet}"
                
                # Use template formatting
                if i < len(template_formats):
                    self._copy_paragraph_formatting(p, template_formats[i])
                elif template_formats:
                    # Use first template paragraph's formatting
                    self._copy_paragraph_formatting(p, template_formats[0])
                else:
                    # Fallback formatting
                    for run in p.runs:
                        run.font.color.rgb = RGBColor(255, 255, 255)
    
    def _find_best_layout_for_content(self, prs, title: str, bullets: List[str]):
        """Find the best layout based on content needs and existing slide patterns"""
        
        # Analyze existing slides to find common patterns
        content_layouts = []
        for slide in prs.slides:
            slide_layout = slide.slide_layout
            
            # Check if this layout has both title and content placeholders
            has_title = False
            has_content = False
            
            for shape in slide_layout.placeholders:
                try:
                    if hasattr(shape, 'placeholder_format') and shape.placeholder_format:
                        ph_type = shape.placeholder_format.type
                        if ph_type == PP_PLACEHOLDER.TITLE:
                            has_title = True
                        elif ph_type in [PP_PLACEHOLDER.BODY, PP_PLACEHOLDER.OBJECT]:
                            has_content = True
                except Exception:
                    continue
            
            if has_title and has_content and bullets:
                content_layouts.append(slide_layout)
            elif has_title and not bullets:
                content_layouts.append(slide_layout)
        
        # Use the most common content layout, or fallback to layout selection
        if content_layouts:
            # Use the first content layout found (could be improved with frequency analysis)
            return content_layouts[0]
        
        # Fallback: look for standard layout names
        for layout in prs.slide_layouts:
            layout_name = layout.name.upper()
            if any(name in layout_name for name in ["TITLE_AND_CONTENT", "TITLE_AND_BODY", "CONTENT"]):
                return layout
        
        # Final fallback
        return prs.slide_layouts[1] if len(prs.slide_layouts) > 1 else prs.slide_layouts[0]
    
    def _fill_slide_with_formatting(self, new_slide, title: str, bullets: List[str], prs):
        """Fill slide content while preserving template formatting"""
        
        # Find a reference slide with similar content for formatting
        reference_slide = self._find_reference_slide(prs, bullets)
        
        # Fill title with inherited formatting
        title_shape = self._find_title_shape(new_slide)
        if title_shape and hasattr(title_shape, 'text_frame'):
            title_shape.text_frame.clear()
            p = title_shape.text_frame.paragraphs[0]
            p.text = title
            
            # Copy title formatting from reference slide if available
            if reference_slide:
                ref_title_shape = self._find_title_shape(reference_slide)
                if ref_title_shape and hasattr(ref_title_shape, 'text_frame'):
                    self._copy_paragraph_formatting(p, ref_title_shape.text_frame.paragraphs[0])
        
        # Fill content with inherited formatting
        content_shape = self._find_content_shape(new_slide)
        if content_shape and hasattr(content_shape, 'text_frame') and bullets:
            content_shape.text_frame.clear()
            
            # Get reference content formatting
            ref_content_format = None
            if reference_slide:
                ref_content_shape = self._find_content_shape(reference_slide)
                if ref_content_shape and hasattr(ref_content_shape, 'text_frame'):
                    ref_paragraphs = ref_content_shape.text_frame.paragraphs
                    if ref_paragraphs:
                        ref_content_format = ref_paragraphs[0]
            
            # Add bullets with formatting
            for i, bullet in enumerate(bullets):
                if i == 0:
                    p = content_shape.text_frame.paragraphs[0]
                else:
                    p = content_shape.text_frame.add_paragraph()
                
                p.text = f"• {bullet}"
                
                # Copy formatting from reference
                if ref_content_format:
                    self._copy_paragraph_formatting(p, ref_content_format)
                else:
                    # Fallback formatting
                    for run in p.runs:
                        run.font.color.rgb = RGBColor(255, 255, 255)
    
    def _find_reference_slide(self, prs, bullets: List[str]):
        """Find a slide with similar content structure for formatting reference"""
        
        # Look for slides with bullet content
        for slide in prs.slides:
            content_shape = self._find_content_shape(slide)
            if content_shape and hasattr(content_shape, 'text_frame'):
                if len(content_shape.text_frame.paragraphs) > 1 or (
                    len(content_shape.text_frame.paragraphs) == 1 and 
                    content_shape.text_frame.paragraphs[0].text.strip()
                ):
                    return slide
        
        # Fallback to any slide with content
        if len(prs.slides) > 2:  # Skip title slide
            return prs.slides[2]
        elif len(prs.slides) > 1:
            return prs.slides[1]
        
        return None
    
    def _copy_paragraph_formatting(self, target_paragraph, source_paragraph):
        """Copy formatting from source paragraph to target paragraph"""
        try:
            if not source_paragraph.runs:
                return
            
            source_run = source_paragraph.runs[0]
            
            for run in target_paragraph.runs:
                if hasattr(source_run, 'font'):
                    if hasattr(source_run.font, 'name') and source_run.font.name:
                        run.font.name = source_run.font.name
                    if hasattr(source_run.font, 'size') and source_run.font.size:
                        run.font.size = source_run.font.size
                    if hasattr(source_run.font, 'color') and source_run.font.color:
                        try:
                            if hasattr(source_run.font.color, 'rgb'):
                                run.font.color.rgb = source_run.font.color.rgb
                        except Exception:
                            # Fallback to white if color copying fails
                            run.font.color.rgb = RGBColor(255, 255, 255)
                    if hasattr(source_run.font, 'bold'):
                        run.font.bold = source_run.font.bold
                    if hasattr(source_run.font, 'italic'):
                        run.font.italic = source_run.font.italic
        except Exception as e:
            logger.warning(f"Could not copy formatting: {e}")
            # Fallback formatting
            for run in target_paragraph.runs:
                run.font.color.rgb = RGBColor(255, 255, 255)
    
    def create_presentation(self, template_path: Path, output_path: Path, user_request: str) -> str:
        """Create a new presentation from template based on user request"""
        try:
            if not template_path.exists():
                return f"Error: Template file not found at {template_path}"
            
            # For now, simply copy the template to create the initial presentation
            # The user can then make follow-up requests to modify it
            import shutil
            shutil.copy2(template_path, output_path)
            
            logger.info(f"Created new presentation from template at {output_path}")
            return f"Successfully created new presentation from template. You can now make follow-up requests to modify specific slides."
            
        except Exception as e:
            logger.error(f"Error creating presentation: {e}")
            return f"Error creating presentation: {str(e)}"

# Create singleton
simple_slide_tools = SimpleSlideTools()
