"""
Visual safety map for identifying no-go zones in slide layouts
"""

import numpy as np
import logging
from typing import List, Dict, Any, Tuple, Optional
from PIL import Image, ImageDraw
import io
import base64

logger = logging.getLogger(__name__)


def make_safety_mask(
    img_rgba: np.ndarray,
    labels: List[Dict[str, Any]],
    width: int,
    height: int
) -> np.ndarray:
    """
    Create a safety mask from vision labels
    
    Args:
        img_rgba: HxWx4 preview image array (optional, for future enhancement)
        labels: Vision labels with shape_id, role, place_content, bbox_px
        width: Slide width in pixels
        height: Slide height in pixels
    
    Returns:
        Binary mask HxW where 1=safe, 0=unsafe
    """
    # Initialize mask as all safe
    mask = np.ones((height, width), dtype=np.uint8)
    
    for label in labels:
        role = label.get("role", "Unknown")
        place_content = label.get("place_content", True)
        bbox_px = label.get("bbox_px")
        
        # Mark unsafe zones
        if bbox_px and (
            role in ["Logo", "Footer", "Decor", "Watermark", "Copyright"] or
            not place_content
        ):
            left = int(bbox_px.get("left", 0))
            top = int(bbox_px.get("top", 0))
            bbox_width = int(bbox_px.get("width", 0))
            bbox_height = int(bbox_px.get("height", 0))
            
            # Ensure bounds are within image
            left = max(0, min(left, width - 1))
            top = max(0, min(top, height - 1))
            right = min(left + bbox_width, width)
            bottom = min(top + bbox_height, height)
            
            # Mark region as unsafe
            mask[top:bottom, left:right] = 0
            
            logger.debug(f"Marked unsafe zone: {role} at ({left},{top},{bbox_width},{bbox_height})")
    
    return mask


def overlap_penalty(
    bbox_px: Dict[str, float],
    mask: np.ndarray,
    penalty_scale: float = 1.0
) -> float:
    """
    Calculate penalty for placing content in unsafe zones
    
    Args:
        bbox_px: Bounding box with 'left', 'top', 'width', 'height' in pixels
        mask: Safety mask where 1=safe, 0=unsafe
        penalty_scale: Scale factor for penalty
    
    Returns:
        Penalty score from 0 (completely safe) to 1 (completely unsafe)
    """
    if mask is None or mask.size == 0:
        return 0.0
    
    left = int(bbox_px.get("left", 0))
    top = int(bbox_px.get("top", 0))
    width = int(bbox_px.get("width", 0))
    height = int(bbox_px.get("height", 0))
    
    # Ensure bounds are within mask
    mask_h, mask_w = mask.shape
    left = max(0, min(left, mask_w - 1))
    top = max(0, min(top, mask_h - 1))
    right = min(left + width, mask_w)
    bottom = min(top + height, mask_h)
    
    # Extract sub-region
    if right <= left or bottom <= top:
        return 0.0
    
    sub_mask = mask[top:bottom, left:right]
    
    if sub_mask.size == 0:
        return 0.0
    
    # Calculate ratio of safe pixels (1s) in the region
    safe_ratio = sub_mask.mean()
    
    # Convert to penalty (more unsafe = higher penalty)
    penalty = (1.0 - safe_ratio) * penalty_scale
    
    return min(1.0, penalty)


def create_safety_visualization(
    mask: np.ndarray,
    shapes: List[Dict[str, Any]],
    width: int = 1920,
    height: int = 1080
) -> bytes:
    """
    Create a visualization of the safety map
    
    Args:
        mask: Safety mask
        shapes: List of shapes with bounding boxes
        width: Image width
        height: Image height
    
    Returns:
        PNG image as bytes
    """
    # Create RGBA image
    img = Image.new('RGBA', (width, height), (255, 255, 255, 255))
    draw = ImageDraw.Draw(img)
    
    # Draw safety mask (red for unsafe, green for safe)
    if mask is not None and mask.size > 0:
        # Resize mask if needed
        if mask.shape != (height, width):
            mask_img = Image.fromarray((mask * 255).astype(np.uint8))
            mask_img = mask_img.resize((width, height), Image.NEAREST)
            mask = np.array(mask_img) / 255.0
        
        # Create colored overlay
        overlay = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        
        for y in range(0, height, 10):  # Draw in 10px blocks for efficiency
            for x in range(0, width, 10):
                if mask[y, x] < 0.5:  # Unsafe
                    overlay_draw.rectangle(
                        [(x, y), (x + 10, y + 10)],
                        fill=(255, 0, 0, 100)
                    )
                else:  # Safe
                    overlay_draw.rectangle(
                        [(x, y), (x + 10, y + 10)],
                        fill=(0, 255, 0, 50)
                    )
        
        # Composite overlay
        img = Image.alpha_composite(img, overlay)
        draw = ImageDraw.Draw(img)
    
    # Draw shape boundaries
    for shape in shapes:
        bbox = shape.get("bbox_px", {})
        if bbox:
            left = int(bbox.get("left", 0))
            top = int(bbox.get("top", 0))
            right = left + int(bbox.get("width", 0))
            bottom = top + int(bbox.get("height", 0))
            
            role = shape.get("role", "Unknown")
            place_content = shape.get("place_content", True)
            
            # Choose color based on safety
            if role in ["Logo", "Footer", "Decor"] or not place_content:
                color = (255, 0, 0, 255)  # Red for unsafe
                width_line = 3
            else:
                color = (0, 0, 255, 255)  # Blue for normal shapes
                width_line = 1
            
            draw.rectangle(
                [(left, top), (right, bottom)],
                outline=color,
                width=width_line
            )
            
            # Add label
            if role != "Unknown":
                draw.text((left + 5, top + 5), role, fill=color)
    
    # Convert to bytes
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    return buffer.getvalue()


def encode_mask_to_string(mask: np.ndarray) -> str:
    """
    Encode safety mask to a compact string representation
    
    Args:
        mask: Binary mask array
    
    Returns:
        Base64 encoded string
    """
    if mask is None or mask.size == 0:
        return ""
    
    # Convert to bytes (pack 8 pixels per byte)
    h, w = mask.shape
    
    # Flatten and pack
    flat = mask.flatten()
    
    # Pad to multiple of 8
    pad_size = (8 - len(flat) % 8) % 8
    if pad_size > 0:
        flat = np.concatenate([flat, np.zeros(pad_size, dtype=np.uint8)])
    
    # Pack bits
    packed = np.packbits(flat)
    
    # Encode metadata and data
    metadata = f"{h},{w},"
    data = base64.b64encode(packed.tobytes()).decode('ascii')
    
    return metadata + data


def decode_mask_from_string(encoded: str) -> Optional[np.ndarray]:
    """
    Decode safety mask from string representation
    
    Args:
        encoded: Base64 encoded string with metadata
    
    Returns:
        Binary mask array or None if invalid
    """
    if not encoded:
        return None
    
    try:
        # Parse metadata
        parts = encoded.split(',', 2)
        if len(parts) != 3:
            return None
        
        h = int(parts[0])
        w = int(parts[1])
        data = parts[2]
        
        # Decode data
        packed = np.frombuffer(base64.b64decode(data), dtype=np.uint8)
        
        # Unpack bits
        unpacked = np.unpackbits(packed)
        
        # Reshape to original size
        mask = unpacked[:h * w].reshape(h, w)
        
        return mask.astype(np.uint8)
        
    except Exception as e:
        logger.error(f"Failed to decode safety mask: {e}")
        return None


def compute_shape_safety_scores(
    shapes: List[Dict[str, Any]],
    mask: np.ndarray,
    config: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Compute safety scores for all shapes
    
    Args:
        shapes: List of shape dictionaries
        mask: Safety mask
        config: Optional configuration parameters
    
    Returns:
        Updated shapes with safety_penalty field
    """
    if mask is None or mask.size == 0:
        # No mask available, return shapes unchanged
        return shapes
    
    config = config or {}
    penalty_scale = config.get("penalty_scale", 1.0)
    
    updated_shapes = []
    
    for shape in shapes:
        shape_copy = shape.copy()
        bbox_px = shape.get("bbox_px")
        
        if bbox_px:
            penalty = overlap_penalty(bbox_px, mask, penalty_scale)
            shape_copy["safety_penalty"] = penalty
            
            # Also set place_ok based on penalty threshold
            if penalty > 0.8:  # More than 80% unsafe
                shape_copy["place_ok"] = False
                logger.debug(f"Shape {shape.get('id')} marked as not placeable (penalty: {penalty:.2f})")
        else:
            shape_copy["safety_penalty"] = 0.0
        
        updated_shapes.append(shape_copy)
    
    return updated_shapes


def create_safety_report(
    shapes: List[Dict[str, Any]],
    mask: np.ndarray
) -> Dict[str, Any]:
    """
    Generate a safety analysis report
    
    Args:
        shapes: List of shapes with safety scores
        mask: Safety mask
    
    Returns:
        Report dictionary with statistics and recommendations
    """
    total_shapes = len(shapes)
    unsafe_shapes = sum(1 for s in shapes if s.get("safety_penalty", 0) > 0.5)
    blocked_shapes = sum(1 for s in shapes if not s.get("place_ok", True))
    
    # Calculate mask coverage
    if mask is not None and mask.size > 0:
        unsafe_ratio = 1.0 - mask.mean()
    else:
        unsafe_ratio = 0.0
    
    # Identify problematic roles
    problematic_roles = {}
    for shape in shapes:
        role = shape.get("role", "Unknown")
        penalty = shape.get("safety_penalty", 0)
        if penalty > 0:
            if role not in problematic_roles:
                problematic_roles[role] = []
            problematic_roles[role].append(penalty)
    
    # Calculate average penalties by role
    role_penalties = {}
    for role, penalties in problematic_roles.items():
        role_penalties[role] = {
            "count": len(penalties),
            "avg_penalty": np.mean(penalties),
            "max_penalty": max(penalties)
        }
    
    report = {
        "total_shapes": total_shapes,
        "unsafe_shapes": unsafe_shapes,
        "blocked_shapes": blocked_shapes,
        "unsafe_coverage_ratio": unsafe_ratio,
        "role_penalties": role_penalties,
        "recommendations": []
    }
    
    # Generate recommendations
    if unsafe_ratio > 0.3:
        report["recommendations"].append(
            f"High unsafe coverage ({unsafe_ratio:.1%}) - consider using a different template"
        )
    
    if blocked_shapes > 0:
        report["recommendations"].append(
            f"{blocked_shapes} shapes are blocked - content may not fit properly"
        )
    
    for role, stats in role_penalties.items():
        if stats["avg_penalty"] > 0.7:
            report["recommendations"].append(
                f"Avoid placing content in {role} areas (avg penalty: {stats['avg_penalty']:.2f})"
            )
    
    return report