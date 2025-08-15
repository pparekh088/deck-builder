"""
Template API Routes
Handles template upload, ingestion, and profile retrieval
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import JSONResponse, FileResponse
from typing import Optional
import logging
from pathlib import Path

from app.pipelines.template_ingest import template_ingest_pipeline
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/template", tags=["template"])

@router.post("/ingest")
async def ingest_template(
    file: UploadFile = File(...)
):
    """
    Ingest a PowerPoint template with hybrid analysis
    
    This endpoint:
    1. Hashes the file to generate template_id
    2. Parses structural information
    3. Renders layout previews (if vision enabled)
    4. Performs vision labeling (if enabled)
    5. Persists the enriched profile
    
    Returns:
        JSON with template_id and profile summary
    """
    try:
        # Validate file type
        if not file.filename.endswith(('.pptx', '.ppt')):
            raise HTTPException(
                status_code=400,
                detail="Only PowerPoint files (.pptx, .ppt) are supported"
            )
        
        # Read file content
        content = await file.read()
        
        # Check file size
        if len(content) > settings.max_file_size:
            raise HTTPException(
                status_code=400,
                detail=f"File size exceeds maximum of {settings.max_file_size} bytes"
            )
        
        # Run ingestion pipeline
        result = await template_ingest_pipeline.ingest_template(
            pptx_bytes=content,
            filename=file.filename
        )
        
        return JSONResponse(
            content={
                "success": True,
                "template_id": result['template_id'],
                "profile_summary": result['profile_summary'],
                "cached": result.get('cached', False),
                "message": "Template ingested successfully with hybrid analysis"
            }
        )
        
    except Exception as e:
        logger.error(f"Error ingesting template: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to ingest template: {str(e)}"
        )

@router.get("/profile/{template_id}")
async def get_template_profile(template_id: str):
    """
    Get the full template profile including vision labels
    
    Args:
        template_id: Template identifier (hash)
        
    Returns:
        Complete TemplateProfile with vision labels
    """
    try:
        profile = await template_ingest_pipeline.get_template_profile(template_id)
        
        if not profile:
            raise HTTPException(
                status_code=404,
                detail=f"Template profile not found for ID: {template_id}"
            )
        
        return profile.model_dump()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving template profile: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve template profile: {str(e)}"
        )

@router.get("/preview/{template_id}/{master_idx}/{layout_idx}")
async def get_layout_preview(
    template_id: str,
    master_idx: int,
    layout_idx: int
):
    """
    Get the preview image for a specific layout
    
    Args:
        template_id: Template identifier
        master_idx: Master slide index
        layout_idx: Layout index within the master
        
    Returns:
        PNG image of the layout preview
    """
    try:
        # Check if preview exists
        preview_path = Path(settings.templates_dir) / "previews" / template_id / f"{master_idx}_{layout_idx}.png"
        
        if not preview_path.exists():
            # Try to regenerate preview
            template_path = Path(settings.templates_dir) / f"{template_id}.pptx"
            if not template_path.exists():
                raise HTTPException(
                    status_code=404,
                    detail="Template not found"
                )
            
            # Read template and regenerate previews
            with open(template_path, 'rb') as f:
                pptx_bytes = f.read()
            
            from app.services.preview_renderer import preview_renderer
            previews = await preview_renderer.render_layout_previews(pptx_bytes, template_id)
            
            # Save preview to disk
            preview_data = previews.get((master_idx, layout_idx))
            if preview_data:
                import base64
                preview_path.parent.mkdir(parents=True, exist_ok=True)
                
                image_data = base64.b64decode(preview_data['image_data'])
                with open(preview_path, 'wb') as f:
                    f.write(image_data)
            else:
                raise HTTPException(
                    status_code=404,
                    detail="Layout not found in template"
                )
        
        return FileResponse(
            path=preview_path,
            media_type="image/png",
            filename=f"layout_{master_idx}_{layout_idx}.png"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting layout preview: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get layout preview: {str(e)}"
        )

@router.post("/upload")
async def upload_template_legacy(
    file: UploadFile = File(...)
):
    """
    Legacy upload endpoint - redirects to /ingest
    Kept for backwards compatibility
    """
    return await ingest_template(file)

@router.get("/list")
async def list_templates():
    """
    List all available templates with their summaries
    
    Returns:
        List of template summaries
    """
    try:
        templates = []
        template_dir = Path(settings.templates_dir)
        
        # Find all profile files
        for profile_path in template_dir.glob("*_profile.json"):
            template_id = profile_path.stem.replace("_profile", "")
            
            # Get profile summary
            profile = await template_ingest_pipeline.get_template_profile(template_id)
            if profile:
                summary = template_ingest_pipeline._get_profile_summary(profile)
                templates.append({
                    "template_id": template_id,
                    "summary": summary,
                    "analyzed_at": profile.analyzed_at.isoformat()
                })
        
        return {
            "templates": templates,
            "total": len(templates)
        }
        
    except Exception as e:
        logger.error(f"Error listing templates: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list templates: {str(e)}"
        )