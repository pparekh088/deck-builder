"""
Advanced PowerPoint AI Agent - Complete Implementation Examples
This file contains production-ready code for building the most advanced PowerPoint AI agent
"""

import asyncio
import json
import logging
import os
import platform
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import openai
from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Inches, Pt
import redis
from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks
from pydantic import BaseModel, Field
import aiofiles
from langchain.chat_models import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# DATA MODELS
# ============================================================================

class PresentationStyle(str, Enum):
    """Supported presentation styles"""
    PROFESSIONAL = "professional"
    CREATIVE = "creative"
    MINIMAL = "minimal"
    ACADEMIC = "academic"
    SALES = "sales"
    TECHNICAL = "technical"
    MODERN = "modern"
    CORPORATE = "corporate"

class SlideLayout(str, Enum):
    """Available slide layouts"""
    TITLE = "title"
    TITLE_CONTENT = "title_content"
    TWO_COLUMN = "two_column"
    COMPARISON = "comparison"
    BLANK = "blank"
    SECTION_HEADER = "section_header"
    TITLE_ONLY = "title_only"
    CONTENT_WITH_CAPTION = "content_with_caption"
    PICTURE_WITH_CAPTION = "picture_with_caption"

@dataclass
class ColorScheme:
    """Color scheme for presentations"""
    primary: str
    secondary: str
    accent: str
    background: str = "#FFFFFF"
    text: str = "#000000"
    
    def to_rgb(self, color: str) -> RGBColor:
        """Convert hex color to RGBColor"""
        color = color.lstrip('#')
        return RGBColor(
            int(color[0:2], 16),
            int(color[2:4], 16),
            int(color[4:6], 16)
        )

@dataclass
class SlideContent:
    """Content for a single slide"""
    title: str
    subtitle: Optional[str] = None
    bullet_points: List[str] = field(default_factory=list)
    notes: str = ""
    layout: SlideLayout = SlideLayout.TITLE_CONTENT
    image_prompt: Optional[str] = None
    chart_data: Optional[Dict] = None
    custom_content: Optional[Dict] = None

@dataclass
class PresentationConfig:
    """Configuration for presentation generation"""
    topic: str
    num_slides: int = 10
    style: PresentationStyle = PresentationStyle.PROFESSIONAL
    color_scheme: Optional[ColorScheme] = None
    include_images: bool = True
    include_charts: bool = False
    template_id: Optional[str] = None
    language: str = "en"
    audience: str = "general"
    brand_guidelines: Optional[Dict] = None

# ============================================================================
# AI CONTENT GENERATION
# ============================================================================

class AIContentGenerator:
    """Advanced AI content generation for presentations"""
    
    def __init__(self, api_key: str):
        self.client = openai.OpenAI(api_key=api_key)
        self.llm = ChatOpenAI(
            openai_api_key=api_key,
            model_name="gpt-4-turbo-preview",
            temperature=0.7
        )
        self.memory = ConversationBufferMemory()
        
    async def generate_presentation_outline(
        self, 
        config: PresentationConfig
    ) -> List[SlideContent]:
        """Generate complete presentation outline with AI"""
        
        prompt = f"""
        Create a detailed presentation outline about "{config.topic}" with {config.num_slides} slides.
        
        Style: {config.style.value}
        Audience: {config.audience}
        Language: {config.language}
        
        For each slide, provide:
        1. Title (concise and impactful)
        2. Subtitle (if applicable)
        3. 3-5 bullet points (clear and concise)
        4. Speaker notes (detailed explanation)
        5. Suggested image description (if applicable)
        
        Format as JSON array with this structure:
        [
            {{
                "title": "Slide Title",
                "subtitle": "Optional Subtitle",
                "bullet_points": ["Point 1", "Point 2", "Point 3"],
                "notes": "Detailed speaker notes",
                "image_prompt": "Description for image generation",
                "layout": "title_content"
            }}
        ]
        
        Ensure the presentation flows logically and covers the topic comprehensively.
        """
        
        try:
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                model="gpt-4-turbo-preview",
                messages=[
                    {"role": "system", "content": "You are an expert presentation designer."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.7,
                max_tokens=4000
            )
            
            content = json.loads(response.choices[0].message.content)
            
            # Convert to SlideContent objects
            slides = []
            for slide_data in content.get('slides', content):
                slide = SlideContent(
                    title=slide_data['title'],
                    subtitle=slide_data.get('subtitle'),
                    bullet_points=slide_data.get('bullet_points', []),
                    notes=slide_data.get('notes', ''),
                    layout=SlideLayout(slide_data.get('layout', 'title_content')),
                    image_prompt=slide_data.get('image_prompt')
                )
                slides.append(slide)
            
            return slides
            
        except Exception as e:
            logger.error(f"Error generating outline: {e}")
            raise
    
    async def enhance_content(
        self, 
        content: str, 
        enhancement_type: str = "professional"
    ) -> str:
        """Enhance existing content with AI"""
        
        prompts = {
            "professional": "Make this content more professional and polished:",
            "creative": "Make this content more creative and engaging:",
            "concise": "Make this content more concise and impactful:",
            "detailed": "Expand this content with more details and examples:"
        }
        
        prompt = f"{prompts.get(enhancement_type, prompts['professional'])}\n\n{content}"
        
        response = await asyncio.to_thread(
            self.client.chat.completions.create,
            model="gpt-4-turbo-preview",
            messages=[
                {"role": "system", "content": "You are a professional content editor."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.6,
            max_tokens=1000
        )
        
        return response.choices[0].message.content
    
    async def generate_speaker_notes(
        self, 
        slide_content: SlideContent
    ) -> str:
        """Generate detailed speaker notes for a slide"""
        
        prompt = f"""
        Generate detailed speaker notes for this presentation slide:
        
        Title: {slide_content.title}
        Subtitle: {slide_content.subtitle or 'N/A'}
        Bullet Points: {json.dumps(slide_content.bullet_points)}
        
        The speaker notes should:
        1. Provide context and background
        2. Explain each bullet point in detail
        3. Include relevant examples or anecdotes
        4. Suggest transition to the next slide
        5. Be 150-200 words
        
        Write in a conversational, professional tone.
        """
        
        response = await asyncio.to_thread(
            self.client.chat.completions.create,
            model="gpt-4-turbo-preview",
            messages=[
                {"role": "system", "content": "You are a presentation coach."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=500
        )
        
        return response.choices[0].message.content

# ============================================================================
# TEMPLATE MANAGEMENT
# ============================================================================

class TemplateManager:
    """Advanced template management system"""
    
    def __init__(self, storage_path: str = "./templates"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(exist_ok=True)
        self.templates_cache = {}
        self.embeddings_cache = {}
        
    async def analyze_template(self, template_path: str) -> Dict:
        """Analyze a PowerPoint template to extract features"""
        
        prs = Presentation(template_path)
        
        features = {
            "num_layouts": len(prs.slide_layouts),
            "layouts": [],
            "colors": self._extract_colors(prs),
            "fonts": self._extract_fonts(prs),
            "master_elements": self._extract_master_elements(prs),
            "placeholders": self._extract_placeholders(prs)
        }
        
        # Analyze each layout
        for layout in prs.slide_layouts:
            layout_info = {
                "name": layout.name,
                "placeholders": [
                    {
                        "idx": ph.placeholder_format.idx,
                        "type": str(ph.placeholder_format.type),
                        "position": (ph.left, ph.top, ph.width, ph.height)
                    }
                    for ph in layout.placeholders
                ]
            }
            features["layouts"].append(layout_info)
        
        return features
    
    def _extract_colors(self, presentation: Presentation) -> Dict:
        """Extract color scheme from presentation"""
        try:
            theme = presentation.slide_master.theme
            colors = {
                "scheme": "custom",
                "colors": []
            }
            # Extract theme colors if available
            return colors
        except:
            return {"scheme": "default", "colors": []}
    
    def _extract_fonts(self, presentation: Presentation) -> Dict:
        """Extract font information from presentation"""
        fonts = {
            "heading": "Calibri",
            "body": "Calibri",
            "sizes": {"title": 44, "subtitle": 32, "body": 18}
        }
        
        try:
            # Extract from master slide
            master = presentation.slide_master
            for shape in master.shapes:
                if shape.has_text_frame:
                    for paragraph in shape.text_frame.paragraphs:
                        if paragraph.font.name:
                            fonts["body"] = paragraph.font.name
                            break
        except:
            pass
        
        return fonts
    
    def _extract_master_elements(self, presentation: Presentation) -> List[Dict]:
        """Extract master slide elements"""
        elements = []
        
        try:
            master = presentation.slide_master
            for shape in master.shapes:
                element = {
                    "type": shape.shape_type,
                    "position": (shape.left, shape.top, shape.width, shape.height)
                }
                elements.append(element)
        except:
            pass
        
        return elements
    
    def _extract_placeholders(self, presentation: Presentation) -> List[Dict]:
        """Extract placeholder information"""
        placeholders = []
        
        for layout in presentation.slide_layouts:
            for placeholder in layout.placeholders:
                ph_info = {
                    "layout": layout.name,
                    "idx": placeholder.placeholder_format.idx,
                    "type": str(placeholder.placeholder_format.type)
                }
                placeholders.append(ph_info)
        
        return placeholders
    
    async def save_template(
        self, 
        template_file: bytes, 
        metadata: Dict
    ) -> str:
        """Save template with metadata"""
        
        template_id = str(uuid.uuid4())
        template_path = self.storage_path / f"{template_id}.pptx"
        
        # Save file
        async with aiofiles.open(template_path, 'wb') as f:
            await f.write(template_file)
        
        # Analyze template
        features = await self.analyze_template(str(template_path))
        
        # Save metadata
        metadata_path = self.storage_path / f"{template_id}.json"
        metadata.update({
            "id": template_id,
            "created_at": datetime.now().isoformat(),
            "features": features
        })
        
        async with aiofiles.open(metadata_path, 'w') as f:
            await f.write(json.dumps(metadata, indent=2))
        
        # Cache template
        self.templates_cache[template_id] = {
            "path": str(template_path),
            "metadata": metadata
        }
        
        return template_id
    
    async def get_template(self, template_id: str) -> Optional[Presentation]:
        """Retrieve template by ID"""
        
        if template_id in self.templates_cache:
            template_path = self.templates_cache[template_id]["path"]
        else:
            template_path = self.storage_path / f"{template_id}.pptx"
            if not template_path.exists():
                return None
        
        return Presentation(str(template_path))
    
    async def find_best_template(
        self, 
        requirements: Dict
    ) -> Optional[str]:
        """Find best matching template based on requirements"""
        
        best_score = 0
        best_template = None
        
        for template_id, template_data in self.templates_cache.items():
            score = self._calculate_template_score(
                template_data["metadata"]["features"],
                requirements
            )
            
            if score > best_score:
                best_score = score
                best_template = template_id
        
        return best_template
    
    def _calculate_template_score(
        self, 
        features: Dict, 
        requirements: Dict
    ) -> float:
        """Calculate how well a template matches requirements"""
        
        score = 0.0
        
        # Check style match
        if requirements.get("style"):
            # Implement style matching logic
            score += 0.3
        
        # Check layout requirements
        if requirements.get("required_layouts"):
            available_layouts = {l["name"] for l in features["layouts"]}
            required_layouts = set(requirements["required_layouts"])
            match_ratio = len(required_layouts & available_layouts) / len(required_layouts)
            score += match_ratio * 0.4
        
        # Check color scheme preference
        if requirements.get("color_preference"):
            # Implement color matching logic
            score += 0.2
        
        # Check complexity match
        if requirements.get("complexity"):
            num_layouts = features["num_layouts"]
            if requirements["complexity"] == "simple" and num_layouts < 10:
                score += 0.1
            elif requirements["complexity"] == "complex" and num_layouts >= 10:
                score += 0.1
        
        return score

# ============================================================================
# POWERPOINT BUILDER
# ============================================================================

class AdvancedPowerPointBuilder:
    """Advanced PowerPoint presentation builder with all features"""
    
    def __init__(self):
        self.presentation = None
        self.current_slide = None
        
    def create_presentation(
        self, 
        template: Optional[Presentation] = None
    ) -> Presentation:
        """Create new presentation with optional template"""
        
        if template:
            self.presentation = template
        else:
            self.presentation = Presentation()
        
        return self.presentation
    
    def add_title_slide(
        self, 
        title: str, 
        subtitle: str,
        color_scheme: Optional[ColorScheme] = None
    ) -> Any:
        """Add title slide with custom styling"""
        
        slide_layout = self.presentation.slide_layouts[0]
        slide = self.presentation.slides.add_slide(slide_layout)
        
        # Set title
        title_shape = slide.shapes.title
        title_shape.text = title
        
        # Set subtitle
        if len(slide.placeholders) > 1:
            subtitle_shape = slide.placeholders[1]
            subtitle_shape.text = subtitle
        
        # Apply color scheme if provided
        if color_scheme:
            self._apply_slide_colors(slide, color_scheme)
        
        return slide
    
    def add_content_slide(
        self, 
        content: SlideContent,
        color_scheme: Optional[ColorScheme] = None
    ) -> Any:
        """Add content slide with advanced formatting"""
        
        # Select appropriate layout
        layout_idx = self._get_layout_index(content.layout)
        slide_layout = self.presentation.slide_layouts[layout_idx]
        slide = self.presentation.slides.add_slide(slide_layout)
        
        # Add title
        if slide.shapes.title:
            slide.shapes.title.text = content.title
        
        # Add content based on layout
        if content.layout == SlideLayout.TITLE_CONTENT:
            self._add_bullet_points(slide, content.bullet_points)
        elif content.layout == SlideLayout.TWO_COLUMN:
            self._add_two_column_content(slide, content)
        elif content.layout == SlideLayout.COMPARISON:
            self._add_comparison_content(slide, content)
        
        # Add speaker notes
        if content.notes:
            notes_slide = slide.notes_slide
            notes_slide.notes_text_frame.text = content.notes
        
        # Apply color scheme
        if color_scheme:
            self._apply_slide_colors(slide, color_scheme)
        
        # Add image if specified
        if content.image_prompt:
            # Placeholder for image generation/placement
            pass
        
        # Add chart if specified
        if content.chart_data:
            self._add_chart(slide, content.chart_data)
        
        return slide
    
    def _get_layout_index(self, layout: SlideLayout) -> int:
        """Get layout index based on layout type"""
        
        layout_mapping = {
            SlideLayout.TITLE: 0,
            SlideLayout.TITLE_CONTENT: 1,
            SlideLayout.SECTION_HEADER: 2,
            SlideLayout.TWO_COLUMN: 3,
            SlideLayout.COMPARISON: 4,
            SlideLayout.TITLE_ONLY: 5,
            SlideLayout.BLANK: 6,
            SlideLayout.CONTENT_WITH_CAPTION: 7,
            SlideLayout.PICTURE_WITH_CAPTION: 8
        }
        
        # Default to title_content if not found
        return layout_mapping.get(layout, 1)
    
    def _add_bullet_points(
        self, 
        slide: Any, 
        bullet_points: List[str]
    ):
        """Add bullet points to slide"""
        
        # Find content placeholder
        for shape in slide.placeholders:
            if shape.placeholder_format.idx == 1:  # Content placeholder
                text_frame = shape.text_frame
                
                # Clear existing text
                text_frame.clear()
                
                # Add bullet points
                for i, point in enumerate(bullet_points):
                    if i == 0:
                        text_frame.text = point
                    else:
                        p = text_frame.add_paragraph()
                        p.text = point
                        p.level = 0
                
                # Format text
                for paragraph in text_frame.paragraphs:
                    paragraph.font.size = Pt(18)
                    paragraph.font.name = 'Calibri'
                
                break
    
    def _add_two_column_content(
        self, 
        slide: Any, 
        content: SlideContent
    ):
        """Add two-column content to slide"""
        
        # Split bullet points into two columns
        mid_point = len(content.bullet_points) // 2
        left_points = content.bullet_points[:mid_point]
        right_points = content.bullet_points[mid_point:]
        
        # Add left column
        left = Inches(0.5)
        top = Inches(1.5)
        width = Inches(4.5)
        height = Inches(5)
        
        left_box = slide.shapes.add_textbox(left, top, width, height)
        left_frame = left_box.text_frame
        
        for i, point in enumerate(left_points):
            if i == 0:
                left_frame.text = f"• {point}"
            else:
                p = left_frame.add_paragraph()
                p.text = f"• {point}"
        
        # Add right column
        left = Inches(5)
        right_box = slide.shapes.add_textbox(left, top, width, height)
        right_frame = right_box.text_frame
        
        for i, point in enumerate(right_points):
            if i == 0:
                right_frame.text = f"• {point}"
            else:
                p = right_frame.add_paragraph()
                p.text = f"• {point}"
    
    def _add_comparison_content(
        self, 
        slide: Any, 
        content: SlideContent
    ):
        """Add comparison table to slide"""
        
        # Add table
        rows = len(content.bullet_points) + 1
        cols = 2
        left = Inches(0.5)
        top = Inches(1.5)
        width = Inches(9)
        height = Inches(5)
        
        table = slide.shapes.add_table(rows, cols, left, top, width, height).table
        
        # Set column widths
        table.columns[0].width = Inches(4.5)
        table.columns[1].width = Inches(4.5)
        
        # Add headers
        table.cell(0, 0).text = "Option A"
        table.cell(0, 1).text = "Option B"
        
        # Add comparison points
        for i, point in enumerate(content.bullet_points):
            if "vs" in point.lower() or "|" in point:
                parts = point.split("|") if "|" in point else point.split("vs")
                if len(parts) == 2:
                    table.cell(i + 1, 0).text = parts[0].strip()
                    table.cell(i + 1, 1).text = parts[1].strip()
                else:
                    table.cell(i + 1, 0).text = point
                    table.cell(i + 1, 1).text = ""
            else:
                table.cell(i + 1, 0).text = point
                table.cell(i + 1, 1).text = ""
    
    def _add_chart(
        self, 
        slide: Any, 
        chart_data: Dict
    ):
        """Add chart to slide"""
        
        from pptx.chart.data import ChartData
        from pptx.enum.chart import XL_CHART_TYPE
        
        # Define chart position and size
        x, y, cx, cy = Inches(2), Inches(2), Inches(6), Inches(4)
        
        # Create chart data
        chart_data_obj = ChartData()
        chart_data_obj.categories = chart_data.get('categories', ['Category 1', 'Category 2'])
        
        for series_name, values in chart_data.get('series', {}).items():
            chart_data_obj.add_series(series_name, values)
        
        # Add chart to slide
        chart_type = XL_CHART_TYPE.COLUMN_CLUSTERED
        chart = slide.shapes.add_chart(
            chart_type, x, y, cx, cy, chart_data_obj
        ).chart
        
        # Customize chart
        chart.has_legend = True
        chart.legend.position = XL_LEGEND_POSITION.BOTTOM
        chart.has_title = True
        chart.chart_title.text_frame.text = chart_data.get('title', 'Chart')
    
    def _apply_slide_colors(
        self, 
        slide: Any, 
        color_scheme: ColorScheme
    ):
        """Apply color scheme to slide"""
        
        # Apply to title
        if slide.shapes.title:
            title = slide.shapes.title
            for paragraph in title.text_frame.paragraphs:
                for run in paragraph.runs:
                    run.font.color.rgb = color_scheme.to_rgb(color_scheme.primary)
        
        # Apply to content shapes
        for shape in slide.shapes:
            if shape.has_text_frame and shape != slide.shapes.title:
                for paragraph in shape.text_frame.paragraphs:
                    for run in paragraph.runs:
                        run.font.color.rgb = color_scheme.to_rgb(color_scheme.text)
    
    def add_image(
        self, 
        slide: Any, 
        image_path: str,
        left: float = None,
        top: float = None,
        width: float = None,
        height: float = None
    ):
        """Add image to slide with smart positioning"""
        
        # Default positioning
        if left is None:
            left = Inches(7)
        if top is None:
            top = Inches(1.5)
        if width is None:
            width = Inches(3)
        
        # Add image
        pic = slide.shapes.add_picture(
            image_path, left, top, width=width, height=height
        )
        
        return pic
    
    def add_smart_art(
        self, 
        slide: Any,
        diagram_type: str,
        items: List[str]
    ):
        """Add SmartArt-like diagram"""
        
        # This is a simplified version - full SmartArt requires COM automation
        if diagram_type == "process":
            self._add_process_diagram(slide, items)
        elif diagram_type == "cycle":
            self._add_cycle_diagram(slide, items)
        elif diagram_type == "hierarchy":
            self._add_hierarchy_diagram(slide, items)
    
    def _add_process_diagram(
        self, 
        slide: Any, 
        items: List[str]
    ):
        """Add process flow diagram"""
        
        left = Inches(1)
        top = Inches(2)
        box_width = Inches(1.5)
        box_height = Inches(0.75)
        spacing = Inches(0.5)
        
        for i, item in enumerate(items):
            # Add box
            shape = slide.shapes.add_shape(
                MSO_SHAPE.ROUNDED_RECTANGLE,
                left + i * (box_width + spacing),
                top,
                box_width,
                box_height
            )
            
            # Add text
            shape.text = item
            shape.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER
            
            # Add arrow (except for last item)
            if i < len(items) - 1:
                arrow = slide.shapes.add_connector(
                    MSO_CONNECTOR.STRAIGHT,
                    left + (i + 1) * (box_width + spacing) - spacing,
                    top + box_height / 2,
                    left + (i + 1) * (box_width + spacing),
                    top + box_height / 2
                )
    
    def save(self, filename: str):
        """Save presentation to file"""
        self.presentation.save(filename)
        return filename
    
    def save_to_bytes(self) -> bytes:
        """Save presentation to bytes"""
        import io
        
        output = io.BytesIO()
        self.presentation.save(output)
        output.seek(0)
        return output.read()

# ============================================================================
# MEDIA HANDLER
# ============================================================================

class MediaHandler:
    """Handle media generation and processing"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key
        self.cache_dir = Path("./media_cache")
        self.cache_dir.mkdir(exist_ok=True)
        
    async def generate_image(
        self, 
        prompt: str,
        size: str = "1024x1024",
        style: str = "natural"
    ) -> str:
        """Generate image using AI"""
        
        # Check cache first
        cache_key = f"{prompt}_{size}_{style}"
        cached_path = self._get_cached_image(cache_key)
        if cached_path:
            return cached_path
        
        try:
            # Generate with DALL-E 3
            client = openai.OpenAI(api_key=self.api_key)
            
            response = await asyncio.to_thread(
                client.images.generate,
                model="dall-e-3",
                prompt=f"{prompt}. Style: {style}",
                size=size,
                quality="standard",
                n=1
            )
            
            image_url = response.data[0].url
            
            # Download and save image
            import requests
            image_response = requests.get(image_url)
            
            filename = f"{uuid.uuid4()}.png"
            filepath = self.cache_dir / filename
            
            with open(filepath, 'wb') as f:
                f.write(image_response.content)
            
            # Cache the result
            self._cache_image(cache_key, str(filepath))
            
            return str(filepath)
            
        except Exception as e:
            logger.error(f"Error generating image: {e}")
            # Return placeholder image path
            return self._get_placeholder_image()
    
    def _get_cached_image(self, cache_key: str) -> Optional[str]:
        """Get cached image if exists"""
        # Implement cache lookup
        cache_file = self.cache_dir / f"{hash(cache_key)}.cache"
        if cache_file.exists():
            return str(cache_file)
        return None
    
    def _cache_image(self, cache_key: str, filepath: str):
        """Cache image for future use"""
        # Implement caching logic
        pass
    
    def _get_placeholder_image(self) -> str:
        """Get placeholder image when generation fails"""
        # Create simple placeholder
        img = Image.new('RGB', (1024, 768), color='lightgray')
        filepath = self.cache_dir / "placeholder.png"
        img.save(filepath)
        return str(filepath)
    
    async def optimize_image(
        self, 
        image_path: str,
        max_size: Tuple[int, int] = (1920, 1080)
    ) -> str:
        """Optimize image for presentation"""
        
        img = Image.open(image_path)
        
        # Resize if too large
        img.thumbnail(max_size, Image.Resampling.LANCZOS)
        
        # Convert to RGB if necessary
        if img.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = background
        
        # Save optimized image
        optimized_path = image_path.replace('.png', '_optimized.jpg')
        img.save(optimized_path, 'JPEG', quality=85, optimize=True)
        
        return optimized_path

# ============================================================================
# MAIN ORCHESTRATOR
# ============================================================================

class PowerPointAIAgent:
    """Main orchestrator for the AI PowerPoint agent"""
    
    def __init__(
        self,
        openai_api_key: str,
        redis_url: str = "redis://localhost:6379"
    ):
        self.ai_generator = AIContentGenerator(openai_api_key)
        self.template_manager = TemplateManager()
        self.builder = AdvancedPowerPointBuilder()
        self.media_handler = MediaHandler(openai_api_key)
        self.redis_client = redis.from_url(redis_url)
        
    async def create_presentation(
        self,
        config: PresentationConfig,
        progress_callback: Optional[callable] = None
    ) -> bytes:
        """Create complete presentation from configuration"""
        
        try:
            # Step 1: Generate outline
            await self._update_progress(progress_callback, 10, "Generating outline...")
            slides_content = await self.ai_generator.generate_presentation_outline(config)
            
            # Step 2: Select or load template
            await self._update_progress(progress_callback, 20, "Selecting template...")
            template = None
            if config.template_id:
                template = await self.template_manager.get_template(config.template_id)
            elif config.style != PresentationStyle.PROFESSIONAL:
                # Find best matching template
                template_id = await self.template_manager.find_best_template({
                    "style": config.style.value,
                    "complexity": "standard"
                })
                if template_id:
                    template = await self.template_manager.get_template(template_id)
            
            # Step 3: Create presentation
            await self._update_progress(progress_callback, 30, "Building presentation...")
            self.builder.create_presentation(template)
            
            # Step 4: Add title slide
            self.builder.add_title_slide(
                title=config.topic,
                subtitle=f"Generated on {datetime.now().strftime('%B %d, %Y')}",
                color_scheme=config.color_scheme
            )
            
            # Step 5: Add content slides
            total_slides = len(slides_content)
            for i, slide_content in enumerate(slides_content):
                progress = 30 + (50 * (i + 1) / total_slides)
                await self._update_progress(
                    progress_callback, 
                    progress, 
                    f"Creating slide {i + 1}/{total_slides}..."
                )
                
                # Generate speaker notes if not present
                if not slide_content.notes:
                    slide_content.notes = await self.ai_generator.generate_speaker_notes(
                        slide_content
                    )
                
                # Generate image if requested
                if config.include_images and slide_content.image_prompt:
                    try:
                        image_path = await self.media_handler.generate_image(
                            slide_content.image_prompt,
                            style=config.style.value
                        )
                        # Add image to slide content
                        slide_content.custom_content = {"image_path": image_path}
                    except Exception as e:
                        logger.warning(f"Failed to generate image: {e}")
                
                # Add slide
                slide = self.builder.add_content_slide(
                    slide_content,
                    config.color_scheme
                )
                
                # Add image if generated
                if slide_content.custom_content and "image_path" in slide_content.custom_content:
                    self.builder.add_image(
                        slide,
                        slide_content.custom_content["image_path"]
                    )
            
            # Step 6: Add conclusion slide
            await self._update_progress(progress_callback, 85, "Adding conclusion...")
            conclusion_content = SlideContent(
                title="Thank You",
                subtitle="Questions?",
                bullet_points=[
                    "Summary of key points",
                    "Next steps",
                    "Contact information"
                ],
                layout=SlideLayout.TITLE_CONTENT
            )
            self.builder.add_content_slide(conclusion_content, config.color_scheme)
            
            # Step 7: Save presentation
            await self._update_progress(progress_callback, 95, "Finalizing presentation...")
            presentation_bytes = self.builder.save_to_bytes()
            
            await self._update_progress(progress_callback, 100, "Complete!")
            
            return presentation_bytes
            
        except Exception as e:
            logger.error(f"Error creating presentation: {e}")
            raise
    
    async def _update_progress(
        self,
        callback: Optional[callable],
        progress: float,
        message: str
    ):
        """Update progress if callback provided"""
        if callback:
            await callback(progress, message)

# ============================================================================
# FASTAPI APPLICATION
# ============================================================================

app = FastAPI(title="Advanced PowerPoint AI Agent API")

# Global instances
agent = None

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    global agent
    api_key = os.getenv("OPENAI_API_KEY")
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    agent = PowerPointAIAgent(api_key, redis_url)

@app.post("/api/v1/presentations")
async def create_presentation_endpoint(
    config: PresentationConfig,
    background_tasks: BackgroundTasks
):
    """Create a new AI-powered presentation"""
    
    presentation_id = str(uuid.uuid4())
    
    # Start async processing
    background_tasks.add_task(
        process_presentation_task,
        presentation_id,
        config
    )
    
    return {
        "id": presentation_id,
        "status": "processing",
        "message": "Presentation generation started"
    }

async def process_presentation_task(presentation_id: str, config: PresentationConfig):
    """Background task to process presentation"""
    
    try:
        # Create presentation
        presentation_bytes = await agent.create_presentation(config)
        
        # Save to storage
        output_path = Path("./outputs") / f"{presentation_id}.pptx"
        output_path.parent.mkdir(exist_ok=True)
        
        with open(output_path, 'wb') as f:
            f.write(presentation_bytes)
        
        # Update status in Redis
        agent.redis_client.hset(
            f"presentation:{presentation_id}",
            mapping={
                "status": "completed",
                "path": str(output_path),
                "completed_at": datetime.now().isoformat()
            }
        )
        
    except Exception as e:
        # Update error status
        agent.redis_client.hset(
            f"presentation:{presentation_id}",
            mapping={
                "status": "failed",
                "error": str(e),
                "failed_at": datetime.now().isoformat()
            }
        )

@app.get("/api/v1/presentations/{presentation_id}")
async def get_presentation_status(presentation_id: str):
    """Get presentation generation status"""
    
    data = agent.redis_client.hgetall(f"presentation:{presentation_id}")
    
    if not data:
        raise HTTPException(status_code=404, detail="Presentation not found")
    
    return {k.decode(): v.decode() for k, v in data.items()}

@app.get("/api/v1/presentations/{presentation_id}/download")
async def download_presentation(presentation_id: str):
    """Download completed presentation"""
    
    data = agent.redis_client.hgetall(f"presentation:{presentation_id}")
    
    if not data or data.get(b"status", b"").decode() != "completed":
        raise HTTPException(
            status_code=404, 
            detail="Presentation not found or not ready"
        )
    
    file_path = data.get(b"path", b"").decode()
    
    from fastapi.responses import FileResponse
    return FileResponse(
        file_path,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        filename=f"presentation_{presentation_id}.pptx"
    )

@app.post("/api/v1/templates")
async def upload_template(
    file: UploadFile = File(...),
    name: str = None,
    description: str = None
):
    """Upload a custom template"""
    
    template_data = await file.read()
    
    template_id = await agent.template_manager.save_template(
        template_data,
        {
            "name": name or file.filename,
            "description": description or "",
            "uploaded_at": datetime.now().isoformat()
        }
    )
    
    return {
        "template_id": template_id,
        "status": "uploaded",
        "message": "Template uploaded successfully"
    }

# ============================================================================
# CLI INTERFACE
# ============================================================================

async def main_cli():
    """Command-line interface for testing"""
    
    import argparse
    
    parser = argparse.ArgumentParser(description="PowerPoint AI Agent CLI")
    parser.add_argument("topic", help="Presentation topic")
    parser.add_argument("--slides", type=int, default=10, help="Number of slides")
    parser.add_argument("--style", default="professional", help="Presentation style")
    parser.add_argument("--output", default="output.pptx", help="Output filename")
    parser.add_argument("--api-key", help="OpenAI API key")
    
    args = parser.parse_args()
    
    # Set API key
    api_key = args.api_key or os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Error: OpenAI API key required")
        return
    
    # Create agent
    agent = PowerPointAIAgent(api_key)
    
    # Create configuration
    config = PresentationConfig(
        topic=args.topic,
        num_slides=args.slides,
        style=PresentationStyle(args.style)
    )
    
    # Progress callback
    async def progress_callback(progress: float, message: str):
        print(f"[{progress:3.0f}%] {message}")
    
    print(f"Creating presentation about: {args.topic}")
    
    # Generate presentation
    presentation_bytes = await agent.create_presentation(config, progress_callback)
    
    # Save to file
    with open(args.output, 'wb') as f:
        f.write(presentation_bytes)
    
    print(f"✅ Presentation saved to: {args.output}")

if __name__ == "__main__":
    # Run CLI
    asyncio.run(main_cli())