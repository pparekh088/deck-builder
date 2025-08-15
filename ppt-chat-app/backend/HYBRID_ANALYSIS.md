# Hybrid Template Analysis

## Overview

The Hybrid Template Analysis system enhances PowerPoint template processing by combining traditional structural parsing with AI-powered vision analysis. This dual approach provides superior content placement accuracy while maintaining fast generation times.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Template Upload                          │
└──────────────────────┬──────────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                  Template ID Generation                      │
│                    (SHA-256 Hashing)                        │
└──────────────────────┬──────────────────────────────────────┘
                       ▼
                ┌──────┴──────┐
                │  Cached?    │
                └──┬──────┬───┘
                   │ No   │ Yes → Return Cached Profile
                   ▼      │
┌─────────────────────────────────────────────────────────────┐
│              Structural Analysis (python-pptx)               │
│  • Extract layouts, placeholders, themes                     │
│  • Calculate EMU bounding boxes                             │
│  • Identify placeholder types                               │
└──────────────────────┬──────────────────────────────────────┘
                       ▼
                ┌──────┴──────┐
                │Vision On?   │
                └──┬──────┬───┘
                   │ Yes  │ No → Skip to Persistence
                   ▼      │
┌─────────────────────────────────────────────────────────────┐
│                  Preview Rendering                           │
│  • Generate wireframe images per layout                      │
│  • LibreOffice (if available) or PIL fallback               │
│  • Convert EMU → pixel coordinates                          │
└──────────────────────┬──────────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                   Vision Analysis                            │
│  • Send layout images + bboxes to GPT-4V                    │
│  • Receive role labels (Title, Bullets, etc.)               │
│  • Get place_content flags & priorities                     │
└──────────────────────┬──────────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    IoU Mapping                               │
│  • Match vision labels to shapes via IoU ≥ 0.5             │
│  • Merge labels into template profile                       │
│  • Calculate coverage statistics                            │
└──────────────────────┬──────────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                 Profile Persistence                          │
│  • Save to Redis (cache)                                    │
│  • Save to disk (backup)                                    │
│  • Store template file                                      │
└──────────────────────────────────────────────────────────────┘
```

## Key Components

### 1. Vision Models (`app/models/vision.py`)

```python
VisionRole = Literal[
    "Title", "Subtitle", "Bullets", "Paragraph", 
    "Table", "Chart", "HeroImage", "Logo", 
    "Number", "SectionHeader", "Footer", "Decor", "Unknown"
]

class ShapeVisionLabel:
    shape_id: str
    role: VisionRole
    place_content: bool  # Safe for user content?
    priority: int        # Visual hierarchy (1=highest)
    confidence: float    # Model confidence
```

### 2. Geometry Utilities (`app/utils/geometry.py`)

- **EMU ↔ Pixel Conversion**: Handles PowerPoint's EMU units
- **IoU Calculation**: Matches vision bboxes to parsed shapes
- **Bbox Operations**: Center, area, merge, containment checks

### 3. Preview Renderer (`app/services/preview_renderer.py`)

- **LibreOffice Integration**: High-fidelity rendering when available
- **PIL Fallback**: Simple wireframes for portability
- **DPI-aware**: Configurable resolution (default 192 DPI)

### 4. Vision Labeler (`app/services/vision_labeler.py`)

Sends structured prompts to GPT-4V with layout images:

```json
{
  "intent": "TwoColumn",
  "shapes": [
    {"id": "s1", "role": "Title", "place_content": true, "priority": 1},
    {"id": "s2", "role": "Bullets", "place_content": true, "priority": 2},
    {"id": "s3", "role": "Logo", "place_content": false, "priority": 0}
  ]
}
```

### 5. Enhanced Layout Matcher (`app/services/layout_matcher.py`)

**Scoring Precedence** (weights):
1. **Designer Tags** (30%): `slot:title`, `slot:bullets` in names
2. **Vision Roles** (25%): AI-identified content areas
3. **Placeholder Types** (15%): Traditional PPTX types
4. **Content Match** (15%): Bullets, tables, charts
5. **Visual Elements** (10%): Images, media
6. **Complexity** (5%): Simple vs complex layouts

**Penalties**:
- Attempting to place in `place_content: false` areas → -∞
- Decorative elements (Logo, Footer, Decor) → -5% each

## API Endpoints

### POST `/api/template/ingest`
Upload and analyze a template with hybrid processing.

**Request:**
```bash
curl -X POST http://localhost:8000/api/template/ingest \
  -F "file=@template.pptx"
```

**Response:**
```json
{
  "success": true,
  "template_id": "a3f5d8c9b2e1f4a7",
  "profile_summary": {
    "total_layouts": 12,
    "total_shapes": 48,
    "vision_enabled": true,
    "vision_coverage": 87.5,
    "placeholder_types": {...},
    "vision_roles": {
      "Title": 12,
      "Bullets": 8,
      "HeroImage": 4,
      "Logo": 12,
      "Footer": 12
    }
  },
  "cached": false
}
```

### GET `/api/template/profile/{template_id}`
Retrieve full profile with vision labels.

### GET `/api/template/preview/{template_id}/{master_idx}/{layout_idx}`
Get layout preview image (PNG).

## Configuration

Environment variables in `.env`:

```bash
# Vision Configuration
HYBRID_VISION_ENABLED=true
VISION_PROVIDER=openai       # openai|azure|stub
VISION_MODEL=gpt-4o-mini
VISION_IMAGE_DPI=192
LIBREOFFICE_PATH=soffice

# OpenAI Configuration
OPENAI_API_KEY=sk-...
```

## Generation Flow (Hot Path)

The generation path remains **deterministic and fast** - no vision calls:

```python
# In layout_matcher.py
def find_best_layout(slide_spec, template_profile):
    for layout in template_profile.layout_catalog:
        # 1. Check designer tags
        if has_matching_tags(slide_spec, layout):
            score += 3
        
        # 2. Check vision roles (cached)
        if has_matching_vision_roles(slide_spec, layout):
            score += 2
            
        # 3. Check placeholder types
        if has_matching_types(slide_spec, layout):
            score += 1
            
        # 4. Geometry heuristics
        score += geometry_score(slide_spec, layout)
        
        # 5. Apply penalties
        if places_in_non_content_area(layout):
            score = -infinity
```

## Testing

### Unit Tests
```bash
pytest tests/test_geometry.py -v
```

Tests IoU calculation, EMU conversion, bbox operations.

### Integration Tests
```bash
pytest tests/test_vision_integration.py -v
```

Tests vision labeling, profile merging, scoring with vision.

### End-to-End Test
```bash
# With vision enabled
HYBRID_VISION_ENABLED=true python -m pytest tests/

# Without vision (fallback)
HYBRID_VISION_ENABLED=false python -m pytest tests/
```

## Performance Metrics

- **Upload Time**: ~3-5s for vision analysis (one-time)
- **Cache Hit**: <100ms for previously analyzed templates
- **Generation**: <500ms (no vision calls, uses cached labels)
- **Vision Coverage**: Target >80% shapes labeled
- **IoU Threshold**: 0.5 for reliable matching

## Fallback Behavior

The system gracefully degrades when:

1. **Vision Disabled**: Uses structural parsing only
2. **LibreOffice Unavailable**: Uses PIL wireframes
3. **Vision API Error**: Returns stub labels, continues
4. **No Cache**: Re-analyzes template on demand

## Developer Tools

### Preview Templates
```bash
python -m app.cli.preview --template template.pptx --out previews/
```

### Show Layout Labels
```bash
python -m app.cli.show --template_id a3f5d8c9
```

### Force Re-label
```bash
python -m app.cli.label --template_id a3f5d8c9 --relabel
```

## Best Practices

### For Template Designers

1. **Use Semantic Names**: Name placeholders descriptively
2. **Add Tags**: Use `slot:title`, `slot:bullets` prefixes
3. **Consistent Layouts**: Keep decorative elements in same positions
4. **Clear Visual Hierarchy**: Larger/centered = higher priority

### For Developers

1. **Cache Aggressively**: Template analysis is expensive
2. **Monitor Coverage**: Log vision coverage metrics
3. **Test Both Modes**: Ensure fallback behavior works
4. **Version Templates**: Hash changes trigger re-analysis

## Troubleshooting

### Low Vision Coverage
- Check preview quality (increase DPI)
- Verify shapes have proper bounding boxes
- Review vision model responses for errors

### Incorrect Mappings
- Adjust IoU threshold (default 0.5)
- Check for overlapping shapes
- Verify EMU→pixel conversion accuracy

### Performance Issues
- Enable Redis caching
- Pre-process templates in batch
- Use stub provider for development

## Future Enhancements

- **Contrast Detection**: Adjust text color based on background
- **Template Quality Score**: Rate templates for generation suitability
- **Multi-model Support**: Claude, Gemini vision models
- **Batch Processing**: Analyze multiple templates in parallel
- **Smart Caching**: Invalidate on template structure changes

## Migration Guide

### From Pure Structural Analysis

1. **Install Dependencies**:
   ```bash
   pip install Pillow pdf2image numpy
   ```

2. **Enable Vision**:
   ```bash
   HYBRID_VISION_ENABLED=true
   ```

3. **Re-ingest Templates**:
   ```python
   # Templates are automatically re-analyzed on next upload
   # Or force re-analysis:
   await template_ingest_pipeline.ingest_template(
       pptx_bytes, filename
   )
   ```

4. **Update Client Code**:
   - Use `/api/template/ingest` instead of `/upload`
   - Check `vision_coverage` in responses
   - Handle `cached` flag for performance monitoring

## Conclusion

Hybrid Template Analysis combines the reliability of structural parsing with the intelligence of vision models to deliver superior PowerPoint generation. By running vision analysis once at upload time and caching results, we maintain fast generation speeds while significantly improving content placement accuracy.