"""
Canonical layout archetypes for slide classification and alignment
"""

from dataclasses import dataclass
from typing import List, Literal, Dict, Any, Optional
import numpy as np
import logging

logger = logging.getLogger(__name__)

# Define archetype types
Archetype = Literal[
    "TitleSlide",
    "TitleBody", 
    "TwoColumn",
    "Comparison",
    "SectionHeader",
    "Quote",
    "Table",
    "Chart",
    "ImageLeftTextRight",
    "ImageRightTextLeft",
    "FullImage",
    "Grid",
    "Unknown"
]

# Define shape kinds
ShapeKind = Literal[
    "TITLE",
    "SUBTITLE",
    "BODY",
    "TABLE",
    "CHART",
    "PICTURE",
    "TEXTBOX",
    "NONE"
]


@dataclass
class ShapeSig:
    """Shape signature for archetype matching"""
    kind: ShapeKind
    role: Optional[str]
    bbox_norm: tuple[float, float, float, float]  # (left, top, width, height) in 0..1
    
    def to_vector(self) -> np.ndarray:
        """Convert shape to feature vector"""
        l, t, w, h = self.bbox_norm
        cx, cy = l + w/2, t + h/2
        
        # Map shape kind to numeric ID
        type_map = {
            "TITLE": 1,
            "SUBTITLE": 2,
            "BODY": 3,
            "TABLE": 4,
            "CHART": 5,
            "PICTURE": 6,
            "TEXTBOX": 7,
            "NONE": 0
        }
        type_id = type_map.get(self.kind, 0)
        
        return np.array([cx, cy, w, h, type_id])


@dataclass
class LayoutSig:
    """Layout signature with archetype and shapes"""
    archetype: Archetype
    shapes: List[ShapeSig]
    
    def to_vector(self) -> np.ndarray:
        """Convert layout to feature vector"""
        return layout_vector(self.shapes)


# Define canonical archetypes
CANONICAL: Dict[Archetype, LayoutSig] = {
    "TitleSlide": LayoutSig("TitleSlide", [
        ShapeSig("TITLE", "Title", (0.1, 0.18, 0.8, 0.18)),
        ShapeSig("SUBTITLE", "Subtitle", (0.18, 0.38, 0.64, 0.14)),
    ]),
    
    "TitleBody": LayoutSig("TitleBody", [
        ShapeSig("TITLE", "Title", (0.08, 0.10, 0.84, 0.16)),
        ShapeSig("BODY", "Bullets", (0.10, 0.32, 0.80, 0.52)),
    ]),
    
    "TwoColumn": LayoutSig("TwoColumn", [
        ShapeSig("TITLE", "Title", (0.08, 0.08, 0.84, 0.12)),
        ShapeSig("BODY", "BulletsLeft", (0.08, 0.24, 0.40, 0.60)),
        ShapeSig("BODY", "BulletsRight", (0.52, 0.24, 0.40, 0.60)),
    ]),
    
    "Comparison": LayoutSig("Comparison", [
        ShapeSig("TITLE", "Title", (0.08, 0.08, 0.84, 0.12)),
        ShapeSig("SUBTITLE", "LeftHeader", (0.08, 0.22, 0.40, 0.08)),
        ShapeSig("SUBTITLE", "RightHeader", (0.52, 0.22, 0.40, 0.08)),
        ShapeSig("BODY", "LeftContent", (0.08, 0.32, 0.40, 0.52)),
        ShapeSig("BODY", "RightContent", (0.52, 0.32, 0.40, 0.52)),
    ]),
    
    "SectionHeader": LayoutSig("SectionHeader", [
        ShapeSig("TITLE", "SectionTitle", (0.15, 0.35, 0.70, 0.20)),
        ShapeSig("SUBTITLE", "SectionSubtitle", (0.20, 0.58, 0.60, 0.12)),
    ]),
    
    "Quote": LayoutSig("Quote", [
        ShapeSig("TEXTBOX", "Quote", (0.15, 0.30, 0.70, 0.30)),
        ShapeSig("SUBTITLE", "Attribution", (0.25, 0.65, 0.50, 0.10)),
    ]),
    
    "Table": LayoutSig("Table", [
        ShapeSig("TITLE", "Title", (0.08, 0.08, 0.84, 0.12)),
        ShapeSig("TABLE", "Table", (0.10, 0.25, 0.80, 0.60)),
    ]),
    
    "Chart": LayoutSig("Chart", [
        ShapeSig("TITLE", "Title", (0.08, 0.08, 0.84, 0.12)),
        ShapeSig("CHART", "Chart", (0.10, 0.25, 0.80, 0.60)),
    ]),
    
    "ImageLeftTextRight": LayoutSig("ImageLeftTextRight", [
        ShapeSig("TITLE", "Title", (0.08, 0.08, 0.84, 0.12)),
        ShapeSig("PICTURE", "Image", (0.08, 0.24, 0.42, 0.60)),
        ShapeSig("BODY", "Text", (0.52, 0.24, 0.40, 0.60)),
    ]),
    
    "ImageRightTextLeft": LayoutSig("ImageRightTextLeft", [
        ShapeSig("TITLE", "Title", (0.08, 0.08, 0.84, 0.12)),
        ShapeSig("BODY", "Text", (0.08, 0.24, 0.40, 0.60)),
        ShapeSig("PICTURE", "Image", (0.50, 0.24, 0.42, 0.60)),
    ]),
    
    "FullImage": LayoutSig("FullImage", [
        ShapeSig("PICTURE", "FullImage", (0.0, 0.0, 1.0, 1.0)),
    ]),
    
    "Grid": LayoutSig("Grid", [
        ShapeSig("TITLE", "Title", (0.08, 0.08, 0.84, 0.12)),
        ShapeSig("BODY", "TopLeft", (0.08, 0.24, 0.42, 0.35)),
        ShapeSig("BODY", "TopRight", (0.52, 0.24, 0.40, 0.35)),
        ShapeSig("BODY", "BottomLeft", (0.08, 0.62, 0.42, 0.30)),
        ShapeSig("BODY", "BottomRight", (0.52, 0.62, 0.40, 0.30)),
    ]),
}


def layout_vector(shapes: List[ShapeSig], max_shapes: int = 8) -> np.ndarray:
    """
    Convert layout shapes to a fixed-size feature vector
    
    Args:
        shapes: List of shape signatures
        max_shapes: Maximum number of shapes to consider
    
    Returns:
        Flattened feature vector
    """
    # Sort shapes by area (largest first)
    sorted_shapes = sorted(
        shapes,
        key=lambda s: s.bbox_norm[2] * s.bbox_norm[3],
        reverse=True
    )[:max_shapes]
    
    # Convert to feature vectors
    vectors = [s.to_vector() for s in sorted_shapes]
    
    # Pad with zeros if needed
    while len(vectors) < max_shapes:
        vectors.append(np.zeros(5))
    
    # Stack and flatten
    arr = np.vstack(vectors)
    return arr.flatten()


def nearest_archetype(
    layout_shapes: List[ShapeSig],
    threshold: float = 2.0
) -> Archetype:
    """
    Find the nearest canonical archetype for a layout
    
    Args:
        layout_shapes: List of shape signatures in the layout
        threshold: Maximum distance to consider a match
    
    Returns:
        Matched archetype name or "Unknown"
    """
    if not layout_shapes:
        return "Unknown"
    
    v = layout_vector(layout_shapes)
    best_archetype = "Unknown"
    best_score = float("inf")
    
    for name, sig in CANONICAL.items():
        canonical_v = layout_vector(sig.shapes)
        score = np.linalg.norm(v - canonical_v)
        
        if score < best_score:
            best_score = score
            best_archetype = name
    
    # Only return match if below threshold
    if best_score > threshold:
        logger.debug(f"No archetype match found (best score: {best_score:.2f})")
        return "Unknown"
    
    logger.debug(f"Matched archetype: {best_archetype} (score: {best_score:.2f})")
    return best_archetype


def shape_from_dict(shape_data: Dict[str, Any]) -> ShapeSig:
    """
    Create ShapeSig from shape dictionary
    
    Args:
        shape_data: Dictionary with shape information including bbox_norm
    
    Returns:
        ShapeSig instance
    """
    # Map placeholder types to shape kinds
    ph_type = shape_data.get("ph_type", "NONE")
    kind_map = {
        "TITLE": "TITLE",
        "SUBTITLE": "SUBTITLE",
        "BODY": "BODY",
        "TABLE": "TABLE",
        "CHART": "CHART",
        "PICTURE": "PICTURE",
        "TEXTBOX": "TEXTBOX",
        "CONTENT": "BODY",
        "OBJECT": "TEXTBOX"
    }
    kind = kind_map.get(ph_type, "NONE")
    
    # Get normalized bbox
    bbox_norm = shape_data.get("bbox_norm")
    if not bbox_norm:
        # Calculate from pixel bbox if available
        bbox_px = shape_data.get("bbox_px", {})
        slide_width = shape_data.get("slide_width", 1920)
        slide_height = shape_data.get("slide_height", 1080)
        
        if bbox_px:
            left = bbox_px.get("left", 0) / slide_width
            top = bbox_px.get("top", 0) / slide_height
            width = bbox_px.get("width", 0) / slide_width
            height = bbox_px.get("height", 0) / slide_height
            bbox_norm = (left, top, width, height)
        else:
            bbox_norm = (0, 0, 0, 0)
    
    role = shape_data.get("role") or shape_data.get("vision_role")
    
    return ShapeSig(kind=kind, role=role, bbox_norm=bbox_norm)


def align_to_archetype(
    layout_shapes: List[Dict[str, Any]],
    archetype: Optional[Archetype] = None
) -> Dict[str, Any]:
    """
    Align layout shapes to canonical archetype and compute alignment score
    
    Args:
        layout_shapes: List of shape dictionaries
        archetype: Optional specific archetype to align to
    
    Returns:
        Dictionary with alignment info including archetype, score, and mapping
    """
    # Convert to ShapeSig objects
    shape_sigs = [shape_from_dict(s) for s in layout_shapes]
    
    # Find nearest archetype if not specified
    if not archetype:
        archetype = nearest_archetype(shape_sigs)
    
    if archetype == "Unknown" or archetype not in CANONICAL:
        return {
            "archetype": archetype,
            "score": 0.0,
            "mapping": {},
            "aligned": False
        }
    
    # Get canonical layout
    canonical = CANONICAL[archetype]
    
    # Create mapping between layout shapes and canonical shapes
    mapping = {}
    used_canonical = set()
    
    for layout_shape in layout_shapes:
        shape_sig = shape_from_dict(layout_shape)
        best_match = None
        best_score = float("inf")
        
        for i, canonical_shape in enumerate(canonical.shapes):
            if i in used_canonical:
                continue
            
            # Compare shape types
            if shape_sig.kind != canonical_shape.kind:
                continue
            
            # Compare positions (center distance)
            l1, t1, w1, h1 = shape_sig.bbox_norm
            l2, t2, w2, h2 = canonical_shape.bbox_norm
            cx1, cy1 = l1 + w1/2, t1 + h1/2
            cx2, cy2 = l2 + w2/2, t2 + h2/2
            
            distance = np.sqrt((cx1 - cx2)**2 + (cy1 - cy2)**2)
            
            if distance < best_score:
                best_score = distance
                best_match = i
        
        if best_match is not None and best_score < 0.3:  # Threshold for matching
            shape_id = layout_shape.get("id") or layout_shape.get("sid")
            mapping[shape_id] = {
                "canonical_index": best_match,
                "canonical_role": canonical.shapes[best_match].role,
                "distance": best_score
            }
            used_canonical.add(best_match)
    
    # Calculate alignment score
    alignment_score = len(mapping) / max(len(layout_shapes), len(canonical.shapes))
    
    return {
        "archetype": archetype,
        "score": alignment_score,
        "mapping": mapping,
        "aligned": alignment_score > 0.5
    }