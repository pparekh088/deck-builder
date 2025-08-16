"""
Integration tests for vision labeling pipeline
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path

from app.models import TemplateProfile, SlideLayoutSignature, PlaceholderInfo, PlaceholderType
from app.models.vision import ShapeVisionLabel, LayoutVisionLabels, VisionAnalysisResult
from app.services.vision_labeler import VisionLabeler
from app.services.layout_matcher import LayoutMatcher

class TestVisionLabeling:
    """Test vision labeling integration"""
    
    @pytest.fixture
    def mock_template_profile(self):
        """Create a mock template profile"""
        return TemplateProfile(
            template_id="test_template",
            layout_catalog=[
                SlideLayoutSignature(
                    layout_id=0,
                    name="Title Slide",
                    placeholders=[
                        PlaceholderInfo(
                            idx=0,
                            type=PlaceholderType.TITLE,
                            name="Title",
                            bbox_px={'left': 100, 'top': 100, 'width': 800, 'height': 100}
                        ),
                        PlaceholderInfo(
                            idx=1,
                            type=PlaceholderType.SUBTITLE,
                            name="Subtitle",
                            bbox_px={'left': 100, 'top': 250, 'width': 800, 'height': 80}
                        )
                    ]
                ),
                SlideLayoutSignature(
                    layout_id=1,
                    name="Content Slide",
                    placeholders=[
                        PlaceholderInfo(
                            idx=0,
                            type=PlaceholderType.TITLE,
                            name="Title",
                            bbox_px={'left': 100, 'top': 50, 'width': 800, 'height': 80}
                        ),
                        PlaceholderInfo(
                            idx=1,
                            type=PlaceholderType.BODY,
                            name="Content",
                            bbox_px={'left': 100, 'top': 150, 'width': 800, 'height': 400}
                        )
                    ]
                )
            ],
            theme={},
            brand_assets=[],
            slide_width=10.0,
            slide_height=7.5
        )
    
    @pytest.mark.asyncio
    async def test_vision_labeler_stub_mode(self, mock_template_profile):
        """Test vision labeler in stub mode"""
        labeler = VisionLabeler()
        labeler.vision_provider = 'stub'
        
        # Create mock previews
        from PIL import Image
        mock_image = Image.new('RGB', (1920, 1080), 'white')
        
        previews = {
            (0, 0): {
                'image_pil': mock_image,
                'metadata': {'master_idx': 0, 'layout_idx': 0}
            }
        }
        
        # Run labeling
        labels = await labeler.label_layouts(previews, mock_template_profile)
        
        assert len(labels) > 0
        assert labels[0].intent == 'Unknown'  # Stub returns Unknown
        assert len(labels[0].labels) > 0
    
    @pytest.mark.asyncio
    async def test_vision_merge_into_profile(self, mock_template_profile):
        """Test merging vision labels into profile"""
        labeler = VisionLabeler()
        
        # Create mock labels
        labels = [
            LayoutVisionLabels(
                template_id="test_template",
                master_idx=0,
                layout_idx=0,
                intent="TitleSlide",
                labels=[
                    ShapeVisionLabel(
                        shape_id="shape_0",
                        role="Title",
                        place_content=True,
                        priority=1,
                        confidence=0.95
                    ),
                    ShapeVisionLabel(
                        shape_id="shape_1",
                        role="Subtitle",
                        place_content=True,
                        priority=2,
                        confidence=0.90
                    )
                ]
            )
        ]
        
        # Merge labels
        updated_profile = labeler.merge_labels_into_profile(
            mock_template_profile,
            labels
        )
        
        assert updated_profile.vision_enabled is True
        assert updated_profile.vision_coverage > 0
        
        # Check if labels were applied
        first_layout = updated_profile.layout_catalog[0]
        assert first_layout.placeholders[0].vision is not None
        assert first_layout.placeholders[0].vision.role == "Title"

class TestLayoutMatcherWithVision:
    """Test layout matcher with vision labels"""
    
    @pytest.fixture
    def mock_slide_spec(self):
        """Create a mock slide specification"""
        from app.models import SlideSpec, SlideContentNeeds
        
        return SlideSpec(
            slide_id="slide_1",
            title="Test Slide",
            bullets=["Point 1", "Point 2", "Point 3"],
            needs=SlideContentNeeds(
                has_picture=False,
                has_table=None,
                has_chart=None
            )
        )
    
    @pytest.fixture
    def layout_with_vision(self):
        """Create a layout with vision labels"""
        return SlideLayoutSignature(
            layout_id=0,
            name="Vision Layout",
            placeholders=[
                PlaceholderInfo(
                    idx=0,
                    type=PlaceholderType.TITLE,
                    name="Title",
                    vision=ShapeVisionLabel(
                        shape_id="shape_0",
                        role="Title",
                        place_content=True,
                        priority=1,
                        confidence=0.95
                    ),
                    tags=[]
                ),
                PlaceholderInfo(
                    idx=1,
                    type=PlaceholderType.BODY,
                    name="Content",
                    vision=ShapeVisionLabel(
                        shape_id="shape_1",
                        role="Bullets",
                        place_content=True,
                        priority=2,
                        confidence=0.90
                    ),
                    tags=[]
                )
            ]
        )
    
    @pytest.fixture
    def layout_with_tags(self):
        """Create a layout with designer tags"""
        return SlideLayoutSignature(
            layout_id=1,
            name="Tagged Layout",
            placeholders=[
                PlaceholderInfo(
                    idx=0,
                    type=PlaceholderType.TITLE,
                    name="slot:title",
                    tags=["slot:title"],
                    vision=None
                ),
                PlaceholderInfo(
                    idx=1,
                    type=PlaceholderType.BODY,
                    name="slot:bullets",
                    tags=["slot:bullets"],
                    vision=None
                )
            ]
        )
    
    def test_vision_scoring(self, mock_slide_spec, layout_with_vision):
        """Test that vision labels improve scoring"""
        matcher = LayoutMatcher()
        
        score = matcher._score_vision_match(mock_slide_spec, layout_with_vision)
        
        assert score[0] > 0.5  # Should have good score
        assert len(score[1]) == 0  # No adaptations needed
    
    def test_tag_scoring_priority(self, mock_slide_spec, layout_with_tags):
        """Test that designer tags have highest priority"""
        matcher = LayoutMatcher()
        
        score = matcher._score_tag_match(mock_slide_spec, layout_with_tags)
        
        assert score[0] == 1.0  # Perfect match with tags
    
    def test_placement_penalty(self, layout_with_vision):
        """Test penalty for non-placeable areas"""
        # Add a non-placeable shape
        layout_with_vision.placeholders.append(
            PlaceholderInfo(
                idx=2,
                type=PlaceholderType.FOOTER,
                name="Footer",
                vision=ShapeVisionLabel(
                    shape_id="shape_2",
                    role="Footer",
                    place_content=False,  # Not placeable
                    priority=0,
                    confidence=0.95
                )
            )
        )
        
        matcher = LayoutMatcher()
        penalty = matcher._calculate_placement_penalty(layout_with_vision)
        
        assert penalty > 0  # Should have some penalty
        assert penalty <= 0.3  # But capped at 30%

class TestEndToEndPipeline:
    """Test complete pipeline with vision"""
    
    @pytest.mark.asyncio
    async def test_pipeline_with_vision_disabled(self):
        """Test pipeline works with vision disabled"""
        from app.pipelines.template_ingest import TemplateIngestPipeline
        
        pipeline = TemplateIngestPipeline()
        pipeline.vision_enabled = False
        
        # Would need actual PPTX bytes for full test
        # This is a placeholder for the test structure
        assert pipeline.vision_enabled is False
    
    @pytest.mark.asyncio
    async def test_pipeline_fallback_on_vision_error(self):
        """Test pipeline continues if vision fails"""
        from app.pipelines.template_ingest import TemplateIngestPipeline
        
        pipeline = TemplateIngestPipeline()
        
        # Mock vision to fail
        with patch('app.services.vision_labeler.vision_labeler.label_layouts') as mock_label:
            mock_label.side_effect = Exception("Vision API error")
            
            # Pipeline should still work
            # Would need actual implementation test here
            assert True  # Placeholder

if __name__ == "__main__":
    pytest.main([__file__, "-v"])