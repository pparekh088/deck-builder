"""
Vision Labeler Service
Uses vision models to label PowerPoint layout shapes for content placement
"""

import json
import logging
import base64
import io
from typing import List, Dict, Optional, Tuple
from PIL import Image

from app.models.vision import (
    ShapeVisionLabel, LayoutVisionLabels, VisionAnalysisResult,
    VisionRole, LayoutIntent
)
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
            # Call OpenAI vision model
            response = await openai_service.client.chat.completions.create(
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
                            role=vision_shape.get('role', 'Unknown'),
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
                
                for placeholder in layout.placeholders:
                    total_shapes += 1
                    shape_id = f"shape_{placeholder.idx}"
                    
                    if shape_id in label_dict:
                        placeholder.vision = label_dict[shape_id]
                        labeled_shapes += 1
        
        # Update profile metadata
        profile.vision_enabled = True
        profile.vision_coverage = (labeled_shapes / total_shapes * 100) if total_shapes > 0 else 0
        
        logger.info(f"Vision labeling complete: {labeled_shapes}/{total_shapes} shapes labeled "
                   f"({profile.vision_coverage:.1f}% coverage)")
        
        return profile

# Create singleton instance
vision_labeler = VisionLabeler()