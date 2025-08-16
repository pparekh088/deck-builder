# Agentic PowerPoint Generation System

## Overview

This document describes the agentic features that enable intelligent, template-aware PowerPoint generation. The system analyzes uploaded templates, plans presentations to fit available layouts, and self-corrects to ensure high-quality output.

## Architecture

### Core Components

1. **Template Analyzer** (`services/template_analyzer.py`)
   - Extracts layout signatures from PowerPoint templates
   - Identifies placeholder types and positions
   - Captures theme information (fonts, colors)
   - Detects brand assets

2. **Slide Planner** (`services/slide_planner.py`)
   - Uses LLM with JSON schema for structured output
   - Creates presentation plans based on template capabilities
   - Adapts content to fit layout constraints

3. **Layout Matcher** (`services/layout_matcher.py`)
   - Scores slide content against available layouts
   - Multi-factor matching algorithm
   - Suggests best layout for each slide

4. **Slide Composer** (`services/slide_composer.py`)
   - Fills template placeholders with content
   - Handles overflow and distribution
   - Applies theme styling

5. **Presentation Validator** (`services/presentation_validator.py`)
   - Validates slide compositions
   - Detects and repairs issues automatically
   - Implements repair loop for quality assurance

## Data Flow

```
User Input → Template Analysis → Slide Planning → Layout Matching 
    ↓                                                    ↓
Preview ← Validation/Repair ← Slide Composition ←───────┘
```

## API Endpoints

### Template Management

#### `POST /api/template/upload`
Uploads and analyzes a PowerPoint template.

**Request:**
- `session_id`: Session identifier
- `file`: PowerPoint file (.pptx)

**Response:**
```json
{
  "success": true,
  "message": "Template uploaded successfully. Analysis in progress.",
  "template_id": "template_123",
  "template_name": "corporate_template.pptx"
}
```

#### `GET /api/template/profile/{session_id}`
Retrieves the analyzed template profile.

**Response:**
```json
{
  "template_id": "template_123",
  "layout_catalog": [
    {
      "layout_id": 0,
      "name": "Title Slide",
      "placeholders": [
        {"type": "title", "idx": 0},
        {"type": "subtitle", "idx": 1}
      ]
    }
  ],
  "theme": {
    "font_scheme": {"major": "Calibri", "minor": "Arial"},
    "color_scheme": {"accent1": "#FF0000"}
  }
}
```

### Slide Control

#### `POST /api/slide/{session_id}/{slide_number}/layout`
Changes the layout of a specific slide.

**Request Body:**
```json
{
  "layout_id": 2
}
```

#### `POST /api/slide/{session_id}/{slide_number}/regenerate`
Regenerates a specific slide with optional instructions.

**Request Body:**
```json
{
  "instruction": "Make this slide more concise"
}
```

## WebSocket Events

The system sends real-time updates through WebSocket connections:

### `template_profile`
Sent after template analysis completes.
```json
{
  "type": "template_profile",
  "data": {
    "template_id": "template_123",
    "layout_count": 5,
    "layouts": [...],
    "theme": {...}
  }
}
```

### `plan_update`
Updates on presentation planning progress.
```json
{
  "type": "plan_update",
  "data": {
    "status": "complete",
    "slide_count": 10,
    "slides": [...]
  }
}
```

### `status`
General status updates during generation.
```json
{
  "type": "status",
  "data": {
    "stage": "composing",
    "message": "Creating slides..."
  }
}
```

## Configuration

### Environment Variables

```env
# Enable agentic features
ENABLE_AGENTIC_FEATURES=true

# Validation settings
MAX_BULLETS_PER_SLIDE=10
MAX_TITLE_LENGTH=100
MAX_BULLET_LENGTH=150
MAX_REPAIR_ITERATIONS=3

# Composer settings
DEFAULT_FONT_SIZE=18
TITLE_FONT_SIZE=32
```

## Usage Example

```python
# 1. Upload and analyze template
template_profile = await template_analyzer.analyze_template(
    template_path="corporate.pptx",
    template_id="template_123"
)

# 2. Create presentation plan
plan = await slide_planner.create_presentation_plan(
    user_prompt="Create a presentation about AI",
    template_profile=template_profile,
    chat_history=[],
    session_id="session_456"
)

# 3. Match layouts
mappings = layout_matcher.match_slides_to_layouts(
    slides=plan.slides,
    template_profile=template_profile
)

# 4. Compose presentation
compositions = slide_composer.compose_presentation(
    template_path=template_path,
    output_path="output.pptx",
    slides=plan.slides,
    mappings=mappings,
    template_profile=template_profile
)

# 5. Validate and repair
final_plan, final_mappings, issues = await presentation_validator.repair_loop(
    plan=plan,
    compositions=compositions,
    mappings=mappings,
    template_profile=template_profile
)
```

## Layout Matching Algorithm

The layout matcher uses a weighted scoring system:

- **Title Match (25%)**: Does the layout have a title placeholder?
- **Content Match (30%)**: Can the layout accommodate the bullets?
- **Visual Match (20%)**: Are required visual elements supported?
- **Complexity Match (15%)**: Does complexity align with content?
- **Layout Type Match (10%)**: Does the name suggest suitability?

## Validation Rules

The validator checks for:

1. **Composition Success**: Did the slide render properly?
2. **Content Overflow**: Does all content fit?
3. **Title Length**: Is the title within limits?
4. **Bullet Count**: Are there too many bullets?
5. **Bullet Length**: Are bullets concise enough?
6. **Layout Fit**: Is the confidence score acceptable?
7. **Missing Placeholders**: Are required placeholders available?

## Repair Actions

The system can automatically:

- **Split**: Divide slides with too much content
- **Condense**: Summarize verbose content
- **Change Layout**: Switch to better-fitting layout
- **Merge**: Combine related slides

## Error Handling

The system gracefully handles:

- Missing templates
- Invalid template formats
- LLM response errors
- Layout matching failures
- Composition errors

Each component includes fallback mechanisms to ensure presentation generation continues even with partial failures.

## Performance Considerations

- Template analysis is performed asynchronously
- Layout matching uses caching for repeated queries
- Validation runs with configurable iteration limits
- WebSocket updates provide real-time feedback without blocking

## Future Enhancements

Potential improvements include:

1. **Image Generation**: AI-generated images for picture placeholders
2. **Chart Data Synthesis**: Automatic chart data from content
3. **Multi-language Support**: Template analysis in multiple languages
4. **Custom Scoring Weights**: User-configurable matching priorities
5. **Template Learning**: Learn from user preferences over time

## Troubleshooting

### Common Issues

1. **Template Analysis Fails**
   - Ensure template is valid .pptx format
   - Check for corrupted files
   - Verify python-pptx compatibility

2. **Poor Layout Matches**
   - Review template for sufficient layout variety
   - Adjust scoring weights if needed
   - Consider adding more layouts to template

3. **Content Overflow**
   - Reduce MAX_BULLETS_PER_SLIDE setting
   - Enable automatic splitting
   - Use condensation prompts

## Testing

Run the test suite:

```bash
pytest tests/test_agentic_features.py -v
```

Key test areas:
- Template analysis accuracy
- Plan generation consistency
- Layout matching logic
- Validation rule enforcement
- Repair action effectiveness