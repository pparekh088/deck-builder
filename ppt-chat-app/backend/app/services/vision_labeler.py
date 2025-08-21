"""
Vision Labeler Service
Uses vision models to label PowerPoint layout shapes for content placement
"""

import json
import logging
import base64
import io
import asyncio
from typing import List, Dict, Optional, Tuple, TYPE_CHECKING
from PIL import Image

if TYPE_CHECKING:
    from app.vision_models.vision import (
        ShapeVisionLabel, LayoutVisionLabels, VisionAnalysisResult,
        VisionRole, LayoutIntent
    )
else:
    # Import at runtime to avoid circular import
    import sys
    import importlib
    # Dynamically import to bypass the models.py file conflict
    vision_module = importlib.import_module('app.vision_models.vision')
    ShapeVisionLabel = vision_module.ShapeVisionLabel
    LayoutVisionLabels = vision_module.LayoutVisionLabels
    VisionAnalysisResult = vision_module.VisionAnalysisResult
    VisionRole = vision_module.VisionRole
    LayoutIntent = vision_module.LayoutIntent
from app.models import TemplateProfile, PlaceholderInfo
from app.utils.geometry import calculate_iou, find_best_iou_match
from app.services.openai_service import openai_service
from app.config import settings

logger = logging.getLogger(__name__)

# Vision analysis prompt
VISION_PROMPT = """You label a PowerPoint *layout* image for content placement. Return strict JSON ONLY.

Given:
- One layout preview image (wireframe).
- Candidate shapes with bounding boxes in pixels: 
  [{"id":"s1","left":120,"top":80,"width":960,"height":160}, ...].

Tasks:
1) For each shape id, set:
   - role: one of ["Title","Subtitle","Bullets","Paragraph","Table","Chart",
                   "HeroImage","Logo","Number","SectionHeader","Footer","Decor","Unknown"]
   - place_content: boolean (true if safe to place user content)
   - priority: integer (1 = highest visual priority; 0 for decor/no-place)
   - confidence: 0.0–1.0
   - notes: short hint (optional)

2) At slide-level, propose an intent label:
   one of ["TitleSlide","Agenda","Bullets","TwoColumn","Comparison",
           "SectionHeader","ImageLeftTextRight","ImageRightTextLeft",
           "Quote","Table","Chart","Unknown"]

Output:
{
  "intent":"TwoColumn",
  "shapes":[
    {"id":"s1","role":"Title","place_content":true,"priority":1,"confidence":0.92,"notes":""},
    {"id":"s2","role":"Bullets","place_content":true,"priority":2,"confidence":0.88,"notes":"left column"},
    {"id":"s3","role":"Bullets","place_content":true,"priority":3,"confidence":0.83,"notes":"right column"},
    {"id":"s4","role":"Logo","place_content":false,"priority":0,"confidence":0.95,"notes":"brand mark"},
    {"id":"s5","role":"Decor","place_content":false,"priority":0,"confidence":0.90,"notes":"accent band"}
  ]
}"""

class VisionLabeler:
    """Labels PowerPoint shapes using vision models"""
    
    def __init__(self):
        self.vision_enabled = getattr(settings, 'HYBRID_VISION_ENABLED', True)
        self.vision_provider = getattr(settings, 'VISION_PROVIDER', 'openai')
        self.vision_model = getattr(settings, 'VISION_MODEL', 'gpt-4o-mini')
        self.min_iou = 0.5  # Minimum IoU for matching
        
    async def label_layouts(
        self,
        previews: Dict[Tuple[int, int], Dict],
        template_profile: TemplateProfile
    ) -> List[LayoutVisionLabels]:
        """
        Label all layouts using vision analysis
        
        Args:
            previews: Dict of layout previews with images and metadata
            template_profile: Template profile with structural information
            
        Returns:
            List of LayoutVisionLabels for each layout
        """
        if not self.vision_enabled:
            logger.info("Vision labeling disabled")
            return []
        
        all_labels = []
        
        for (master_idx, layout_idx), preview_data in previews.items():
            try:
                # Get layout from profile
                layout_sig = self._get_layout_signature(
                    template_profile, master_idx, layout_idx
                )
                
                if not layout_sig:
                    continue
                
                # Prepare shape candidates
                shape_candidates = self._prepare_shape_candidates(layout_sig)
                
                # Call vision model
                vision_result = await self._analyze_layout_image(
                    preview_data['image_pil'],
                    shape_candidates
                )
                
                # Map vision results to shapes
                layout_labels = self._map_vision_to_shapes(
                    vision_result,
                    layout_sig,
                    template_profile.template_id,
                    master_idx,
                    layout_idx
                )
                
                all_labels.append(layout_labels)
                
            except Exception as e:
                logger.error(f"Error labeling layout ({master_idx}, {layout_idx}): {str(e)}")
        
        return all_labels
    
    def _get_layout_signature(
        self,
        profile: TemplateProfile,
        master_idx: int,
        layout_idx: int
    ) -> Optional[Dict]:
        """Get layout signature by indices"""
        # Since we store layouts flat, we need to find the right one
        # This is simplified - actual implementation would track master/layout relationship
        if layout_idx < len(profile.layout_catalog):
            return profile.layout_catalog[layout_idx]
        return None
    
    def _prepare_shape_candidates(self, layout_sig: Dict) -> List[Dict]:
        """Prepare shape candidates for vision analysis"""
        shapes = []
        
        for idx, placeholder in enumerate(layout_sig.placeholders):
            if placeholder.bbox_px:
                shapes.append({
                    'id': f"s{idx}",
                    'left': placeholder.bbox_px['left'],
                    'top': placeholder.bbox_px['top'],
                    'width': placeholder.bbox_px['width'],
                    'height': placeholder.bbox_px['height']
                })
        
        return shapes
    
    def _normalize_vision_role(self, role: str) -> str:
        """Map provider role variants to our allowed VisionRole values"""
        if not role:
            return 'Unknown'
        r = str(role).strip()
        # Canonical mapping
        mapping = {
            'Image': 'HeroImage',
            'Picture': 'HeroImage',
            'Header': 'SectionHeader',
            'Heading': 'SectionHeader',
            'Text': 'Paragraph',
            'Body': 'Paragraph',
            'Content': 'Paragraph',
        }
        allowed = {
            'Title','Subtitle','Bullets','Paragraph','Table','Chart',
            'HeroImage','Logo','Number','SectionHeader','Footer','Decor','Unknown'
        }
        candidate = mapping.get(r, r)
        return candidate if candidate in allowed else 'Unknown'

    async def _analyze_layout_image(
        self,
        image: Image.Image,
        shape_candidates: List[Dict]
    ) -> VisionAnalysisResult:
        """
        Analyze layout image with vision model
        
        Args:
            image: PIL Image of the layout
            shape_candidates: List of shape bounding boxes
            
        Returns:
            VisionAnalysisResult with labels
        """
        if self.vision_provider == 'stub':
            return self._get_stub_result(shape_candidates)
        
        # Convert image to base64
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        # Prepare messages for vision model
        messages = [
            {
                "role": "system",
                "content": VISION_PROMPT
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"Shape candidates: {json.dumps(shape_candidates)}"
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_base64}"
                        }
                    }
                ]
            }
        ]
        
        try:
            # Call OpenAI vision model (sync client) in a thread to avoid blocking the event loop
            response = await asyncio.to_thread(
                openai_service.client.chat.completions.create,
                model=self.vision_model,
                messages=messages,
                max_tokens=1000,
                temperature=0.1
            )
            
            # Parse JSON response
            result_text = response.choices[0].message.content
            result_json = json.loads(result_text)
            
            return VisionAnalysisResult(
                intent=result_json.get('intent', 'Unknown'),
                shapes=result_json.get('shapes', [])
            )
            
        except Exception as e:
            logger.error(f"Vision API error: {str(e)}")
            return self._get_stub_result(shape_candidates)
    
    def _get_stub_result(self, shape_candidates: List[Dict]) -> VisionAnalysisResult:
        """Get stub result when vision is disabled or fails"""
        shapes = []
        for candidate in shape_candidates:
            shapes.append({
                'id': candidate['id'],
                'role': 'Unknown',
                'place_content': True,
                'priority': 1,
                'confidence': 0.0,
                'notes': 'Stub result'
            })
        
        return VisionAnalysisResult(
            intent='Unknown',
            shapes=shapes
        )
    
    def _map_vision_to_shapes(
        self,
        vision_result: VisionAnalysisResult,
        layout_sig: Dict,
        template_id: str,
        master_idx: int,
        layout_idx: int
    ) -> LayoutVisionLabels:
        """
        Map vision results to actual shapes using IoU matching
        
        Args:
            vision_result: Vision analysis results
            layout_sig: Layout signature with placeholders
            template_id: Template identifier
            master_idx: Master slide index
            layout_idx: Layout index
            
        Returns:
            LayoutVisionLabels with mapped labels
        """
        layout_labels = LayoutVisionLabels(
            template_id=template_id,
            master_idx=master_idx,
            layout_idx=layout_idx,
            intent=vision_result.intent,
            labels=[]
        )
        
        # Prepare candidate bboxes for IoU matching
        candidate_bboxes = []
        for placeholder in layout_sig.placeholders:
            if placeholder.bbox_px:
                shape_id = f"shape_{placeholder.idx}"
                candidate_bboxes.append((shape_id, placeholder.bbox_px))
        
        # Map each vision shape to actual shapes
        for vision_shape in vision_result.shapes:
            # Extract vision bbox (from the id used in candidates)
            vision_id = vision_shape['id']
            idx = int(vision_id[1:])  # Remove 's' prefix
            
            if idx < len(layout_sig.placeholders):
                placeholder = layout_sig.placeholders[idx]
                if placeholder.bbox_px:
                    # Find best matching shape by IoU
                    best_shape_id = find_best_iou_match(
                        placeholder.bbox_px,
                        candidate_bboxes,
                        self.min_iou
                    )
                    
                    if best_shape_id:
                        # Create shape vision label
                        label = ShapeVisionLabel(
                            shape_id=best_shape_id,
                            role=self._normalize_vision_role(vision_shape.get('role', 'Unknown')),
                            place_content=vision_shape.get('place_content', True),
                            priority=vision_shape.get('priority', 0),
                            confidence=vision_shape.get('confidence', 0.0),
                            notes=vision_shape.get('notes', '')
                        )
                        layout_labels.labels.append(label)
        
        return layout_labels
    
    def merge_labels_into_profile(
        self,
        profile: TemplateProfile,
        all_labels: List[LayoutVisionLabels]
    ) -> TemplateProfile:
        """
        Merge vision labels into template profile
        
        Args:
            profile: Template profile to update
            all_labels: Vision labels for all layouts
            
        Returns:
            Updated template profile
        """
        # Import safety map functions
        from ..analysis.safety_map import (
            make_safety_mask, compute_shape_safety_scores, encode_mask_to_string
        )
        from ..config import settings
        
        # Create mapping of labels by layout
        labels_map = {}
        for layout_labels in all_labels:
            key = (layout_labels.master_idx, layout_labels.layout_idx)
            labels_map[key] = layout_labels
        
        # Update placeholders with vision labels
        total_shapes = 0
        labeled_shapes = 0
        
        for layout_idx, layout in enumerate(profile.layout_catalog):
            # Find corresponding labels (simplified - assumes flat indexing)
            key = (0, layout_idx)  # Assuming single master for now
            if key in labels_map:
                layout_labels = labels_map[key]
                
                # Map labels to placeholders
                label_dict = {label.shape_id: label for label in layout_labels.labels}
                
                # Prepare labels for safety map generation
                safety_labels = []
                
                for placeholder in layout.placeholders:
                    total_shapes += 1
                    shape_id = f"shape_{placeholder.idx}"
                    
                    if shape_id in label_dict:
                        label = label_dict[shape_id]
                        # Persist as plain dict to avoid Pydantic serializer warnings
                        try:
                            placeholder.vision = label.model_dump()
                        except Exception:
                            # Fallback if already a dict or different type
                            placeholder.vision = getattr(label, '__dict__', label)
                        labeled_shapes += 1
                        
                        # Prepare label for safety map
                        if placeholder.bbox_px:
                            safety_label = {
                                "shape_id": shape_id,
                                "role": label.role,
                                "place_content": label.place_content,
                                "bbox_px": placeholder.bbox_px
                            }
                            safety_labels.append(safety_label)
                
                # Generate safety mask if enabled
                if settings.SAFETY_MAP_ENABLED and safety_labels:
                    # Get slide pixel dimensions from profile inches * DPI
                    dpi = getattr(settings, 'VISION_IMAGE_DPI', 192)
                    slide_width = int((profile.slide_width or 10.0) * dpi)
                    slide_height = int((profile.slide_height or 5.625) * dpi)
                    
                    # Create safety mask
                    safety_mask = make_safety_mask(
                        None,  # No image needed for basic mask
                        safety_labels,
                        int(slide_width),
                        int(slide_height)
                    )
                    
                    # Encode mask for storage
                    layout.safety_mask = encode_mask_to_string(safety_mask)
                    
                    # Compute safety penalties for each shape
                    shapes_with_safety = compute_shape_safety_scores(
                        [{"id": p.idx, "bbox_px": p.bbox_px} for p in layout.placeholders if p.bbox_px],
                        safety_mask
                    )
                    
                    # Update placeholders with safety penalties
                    for shape_info in shapes_with_safety:
                        placeholder = next((p for p in layout.placeholders if p.idx == shape_info["id"]), None)
                        if placeholder:
                            placeholder.safety_penalty = shape_info.get("safety_penalty", 0.0)
                            placeholder.place_ok = shape_info.get("place_ok", True)
                    
                    logger.debug(f"Generated safety map for layout {layout_idx}")
        
        # Update profile metadata
        profile.vision_enabled = True
        profile.vision_coverage = (labeled_shapes / total_shapes * 100) if total_shapes > 0 else 0
        profile.safety_maps_enabled = settings.SAFETY_MAP_ENABLED
        
        logger.info(f"Vision labeling complete: {labeled_shapes}/{total_shapes} shapes labeled "
                   f"({profile.vision_coverage:.1f}% coverage)")
        
        return profile

# Create singleton instance
vision_labeler = VisionLabeler()