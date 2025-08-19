"""
Template Ingest Pipeline
Orchestrates the complete template analysis process including vision labeling
"""

import json
import logging
from pathlib import Path
from typing import Dict, Optional
import redis.asyncio as redis

from pptx import Presentation

from app.models import TemplateProfile
from app.utils.hashing import get_template_id, get_cache_key
from app.utils.geometry import get_shape_bbox_emu, bbox_emu_to_px
from app.services.template_analyzer import template_analyzer
from app.services.preview_renderer import preview_renderer
from app.services.vision_labeler import vision_labeler
from app.config import settings

logger = logging.getLogger(__name__)

class TemplateIngestPipeline:
    """Orchestrates template ingestion with hybrid analysis"""
    
    def __init__(self):
        self.redis_client = None
        self.vision_enabled = getattr(settings, 'HYBRID_VISION_ENABLED', True)
        self.dpi = getattr(settings, 'VISION_IMAGE_DPI', 192)
        
    async def _get_redis(self):
        """Get or create Redis client"""
        if not self.redis_client:
            self.redis_client = await redis.from_url(
                settings.get_redis_url(),
                decode_responses=True
            )
        return self.redis_client
    
    async def ingest_template(
        self,
        pptx_bytes: bytes,
        filename: str
    ) -> Dict:
        """
        Complete template ingestion pipeline
        
        Args:
            pptx_bytes: PPTX file content
            filename: Original filename
            
        Returns:
            Dict with template_id and profile summary
        """
        try:
            # Generate template ID from file hash
            template_id = get_template_id(pptx_bytes)
            logger.info(f"Ingesting template: {filename} (ID: {template_id})")
            
            # Check if already processed
            existing_profile = await self._get_cached_profile(template_id)
            if existing_profile:
                logger.info(f"Template {template_id} already processed, returning cached profile")
                return {
                    'template_id': template_id,
                    'profile_summary': self._get_profile_summary(existing_profile),
                    'cached': True
                }
            
            # Step 1: Parse structure
            profile = await self._parse_structure(pptx_bytes, template_id)
            
            # Step 2: Attach EMU bounding boxes
            profile = self._attach_emu_bboxes(pptx_bytes, profile)
            
            # Step 3: Render previews (if vision enabled)
            if self.vision_enabled:
                previews = await preview_renderer.render_layout_previews(
                    pptx_bytes, template_id
                )
                
                # Step 4: Attach pixel bounding boxes
                profile = self._attach_pixel_bboxes(profile, previews)
                
                # Step 5: Vision labeling
                labels = await vision_labeler.label_layouts(previews, profile)
                
                # Step 6: Merge labels into profile
                profile = vision_labeler.merge_labels_into_profile(profile, labels)
            else:
                logger.info("Vision analysis disabled, using structural parsing only")
            
            # Step 7: Extract designer tags
            profile = self._extract_designer_tags(profile)
            
            # Step 8: Persist profile
            await self._persist_profile(template_id, profile)
            
            # Step 9: Save template file
            await self._save_template_file(template_id, pptx_bytes, filename)
            
            logger.info(f"Template ingestion complete: {template_id}")
            
            return {
                'template_id': template_id,
                'profile_summary': self._get_profile_summary(profile),
                'cached': False
            }
            
        except Exception as e:
            logger.error(f"Error in template ingest pipeline: {str(e)}")
            raise
    
    async def _parse_structure(
        self,
        pptx_bytes: bytes,
        template_id: str
    ) -> TemplateProfile:
        """Parse template structure using existing analyzer"""
        # Save to temp file for analysis
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.pptx', delete=False) as tmp:
            tmp.write(pptx_bytes)
            tmp_path = Path(tmp.name)
        
        try:
            profile = await template_analyzer.analyze_template(tmp_path, template_id)
            return profile
        finally:
            tmp_path.unlink()
    
    def _attach_emu_bboxes(
        self,
        pptx_bytes: bytes,
        profile: TemplateProfile
    ) -> TemplateProfile:
        """Attach EMU bounding boxes to all shapes"""
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.pptx', delete=False) as tmp:
            tmp.write(pptx_bytes)
            tmp_path = Path(tmp.name)
        
        try:
            prs = Presentation(str(tmp_path))
            
            for layout_idx, layout_sig in enumerate(profile.layout_catalog):
                if layout_idx < len(prs.slide_layouts):
                    layout = prs.slide_layouts[layout_idx]
                    
                    for placeholder_info in layout_sig.placeholders:
                        # Find matching placeholder by index
                        for ph in layout.placeholders:
                            if ph.placeholder_format.idx == placeholder_info.idx:
                                placeholder_info.bbox_emu = get_shape_bbox_emu(ph)
                                break
            
            return profile
            
        finally:
            tmp_path.unlink()
    
    def _attach_pixel_bboxes(
        self,
        profile: TemplateProfile,
        previews: Dict
    ) -> TemplateProfile:
        """Attach pixel bounding boxes based on preview metadata"""
        for (master_idx, layout_idx), preview_data in previews.items():
            if layout_idx < len(profile.layout_catalog):
                layout_sig = profile.layout_catalog[layout_idx]
                
                for placeholder in layout_sig.placeholders:
                    if placeholder.bbox_emu:
                        placeholder.bbox_px = bbox_emu_to_px(
                            placeholder.bbox_emu,
                            self.dpi
                        )
        
        return profile
    
    def _extract_designer_tags(self, profile: TemplateProfile) -> TemplateProfile:
        """Extract designer tags from shape names and alt text"""
        for layout in profile.layout_catalog:
            for placeholder in layout.placeholders:
                tags = []
                
                # Check name for slot: prefix
                if placeholder.name:
                    if 'slot:' in placeholder.name.lower():
                        # Extract tag after slot:
                        parts = placeholder.name.lower().split('slot:')
                        if len(parts) > 1:
                            tag = parts[1].strip().split()[0]  # First word after slot:
                            tags.append(f"slot:{tag}")
                
                # Check alt_text for tags
                if placeholder.alt_text:
                    if 'slot:' in placeholder.alt_text.lower():
                        parts = placeholder.alt_text.lower().split('slot:')
                        if len(parts) > 1:
                            tag = parts[1].strip().split()[0]
                            tags.append(f"slot:{tag}")
                
                placeholder.tags = tags
        
        return profile
    
    async def _get_cached_profile(self, template_id: str) -> Optional[TemplateProfile]:
        """Get cached profile from Redis if exists"""
        try:
            redis_client = await self._get_redis()
            cache_key = get_cache_key(template_id, "profile")
            
            profile_json = await redis_client.get(cache_key)
            if profile_json:
                profile_dict = json.loads(profile_json)
                return TemplateProfile(**profile_dict)
        except Exception as e:
            logger.warning(f"Could not get cached profile: {str(e)}")
        
        return None
    
    async def _persist_profile(self, template_id: str, profile: TemplateProfile):
        """Persist profile to Redis and disk"""
        try:
            # Save to Redis
            redis_client = await self._get_redis()
            cache_key = get_cache_key(template_id, "profile")
            profile_json = profile.model_dump_json()
            try:
                await redis_client.set(cache_key, profile_json)
            except Exception as e:
                logger.error(f"Redis set failed: {e}. Skipping Redis cache for profile {template_id}")
            
            # Also save to disk as backup
            profile_path = Path(settings.templates_dir) / f"{template_id}_profile.json"
            try:
                with open(profile_path, 'w') as f:
                    f.write(profile_json)
            except Exception as e:
                logger.error(f"Disk write failed for profile: {e}")
                
            logger.info(f"Profile persisted for template {template_id}")
            
        except Exception as e:
            logger.error(f"Error persisting profile: {str(e)}")
    
    async def _save_template_file(
        self,
        template_id: str,
        pptx_bytes: bytes,
        filename: str
    ):
        """Save template file to disk"""
        try:
            template_path = Path(settings.templates_dir) / f"{template_id}.pptx"
            with open(template_path, 'wb') as f:
                f.write(pptx_bytes)
            
            # Save metadata
            metadata = {
                'original_filename': filename,
                'template_id': template_id,
                'size_bytes': len(pptx_bytes)
            }
            
            redis_client = await self._get_redis()
            cache_key = get_cache_key(template_id, "metadata")
            try:
                await redis_client.set(cache_key, json.dumps(metadata))
            except Exception as e:
                logger.error(f"Redis set failed for metadata: {e}")
            
        except Exception as e:
            logger.error(f"Error saving template file: {str(e)}")
    
    def _get_profile_summary(self, profile: TemplateProfile) -> Dict:
        """Get summary statistics from profile"""
        total_layouts = len(profile.layout_catalog)
        total_shapes = sum(len(l.placeholders) for l in profile.layout_catalog)
        
        # Count shapes by type
        type_counts = {}
        vision_role_counts = {}
        
        for layout in profile.layout_catalog:
            for placeholder in layout.placeholders:
                # Count by placeholder type
                ph_type = str(placeholder.type)
                type_counts[ph_type] = type_counts.get(ph_type, 0) + 1
                
                # Count by vision role if available
                if placeholder.vision:
                    v = placeholder.vision
                    role = v.get('role') if isinstance(v, dict) else getattr(v, 'role', None)
                    if role:
                        vision_role_counts[role] = vision_role_counts.get(role, 0) + 1
        
        return {
            'total_layouts': total_layouts,
            'total_shapes': total_shapes,
            'vision_enabled': profile.vision_enabled,
            'vision_coverage': profile.vision_coverage,
            'placeholder_types': type_counts,
            'vision_roles': vision_role_counts,
            'slide_dimensions': {
                'width': profile.slide_width,
                'height': profile.slide_height
            }
        }
    
    async def get_template_profile(self, template_id: str) -> Optional[TemplateProfile]:
        """Get template profile by ID"""
        # Try Redis first
        profile = await self._get_cached_profile(template_id)
        if profile:
            return profile
        
        # Try disk
        profile_path = Path(settings.templates_dir) / f"{template_id}_profile.json"
        if profile_path.exists():
            with open(profile_path, 'r') as f:
                profile_dict = json.load(f)
                return TemplateProfile(**profile_dict)
        
        return None

# Create singleton instance
template_ingest_pipeline = TemplateIngestPipeline()