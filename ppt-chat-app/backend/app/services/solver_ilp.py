"""
Integer Linear Programming (ILP) solver for optimal content-to-shape mapping
"""

import logging
from typing import List, Dict, Any, Callable, Optional, Tuple
import pulp
import numpy as np

logger = logging.getLogger(__name__)


def solve_assignment(
    content_items: List[Dict[str, Any]],
    shape_items: List[Dict[str, Any]],
    weight_fn: Callable[[Dict, Dict], float],
    compat_fn: Callable[[Dict, Dict], bool],
    timeout: int = 10,
    msg: bool = False
) -> Dict[str, str]:
    """
    Solve the content-to-shape assignment problem using ILP
    
    Args:
        content_items: List of content items with 'id', 'type', 'required', etc.
        shape_items: List of shape items with 'sid', 'ph_type', 'role', 'bbox_px', etc.
        weight_fn: Function that returns weight (higher is better) for content-shape pair
        compat_fn: Function that returns True if content-shape pair is compatible
        timeout: Solver timeout in seconds
        msg: Whether to show solver messages
    
    Returns:
        Mapping from content_id to shape_sid
    """
    if not content_items or not shape_items:
        logger.warning("Empty content or shape items for ILP solver")
        return {}
    
    # Create the optimization problem
    prob = pulp.LpProblem("ContentShapeMapping", pulp.LpMaximize)
    
    # Create binary variables for each valid content-shape pair
    x_vars = {}
    valid_pairs = []
    
    for c_item in content_items:
        for s_item in shape_items:
            if compat_fn(c_item, s_item):
                var_name = f"x_{c_item['id']}_{s_item['sid']}"
                x_vars[(c_item['id'], s_item['sid'])] = pulp.LpVariable(
                    var_name, 
                    lowBound=0, 
                    upBound=1, 
                    cat='Binary'
                )
                valid_pairs.append((c_item, s_item))
    
    if not x_vars:
        logger.warning("No compatible content-shape pairs found")
        return {}
    
    # Objective function: maximize total weight
    objective = pulp.lpSum(
        weight_fn(c_item, s_item) * x_vars[(c_item['id'], s_item['sid'])]
        for c_item, s_item in valid_pairs
    )
    prob += objective, "Total Weight"
    
    # Constraint 1: Each content item assigned to at most one shape
    for c_item in content_items:
        constraint = pulp.lpSum(
            x_vars[(c_item['id'], s_item['sid'])]
            for s_item in shape_items
            if (c_item['id'], s_item['sid']) in x_vars
        )
        if c_item.get('required', False):
            # Required content must be assigned
            prob += constraint == 1, f"Content_{c_item['id']}_required"
        else:
            # Optional content may or may not be assigned
            prob += constraint <= 1, f"Content_{c_item['id']}_optional"
    
    # Constraint 2: Each shape assigned to at most one content item
    for s_item in shape_items:
        constraint = pulp.lpSum(
            x_vars[(c_item['id'], s_item['sid'])]
            for c_item in content_items
            if (c_item['id'], s_item['sid']) in x_vars
        )
        prob += constraint <= 1, f"Shape_{s_item['sid']}_unique"
    
    # Solve the problem
    try:
        solver = pulp.PULP_CBC_CMD(msg=msg, timeLimit=timeout)
        status = prob.solve(solver)
        
        if status != pulp.LpStatusOptimal:
            logger.warning(f"ILP solver returned non-optimal status: {pulp.LpStatus[status]}")
            if status == pulp.LpStatusInfeasible:
                logger.error("Problem is infeasible - check constraints")
                return {}
    except Exception as e:
        logger.error(f"ILP solver failed: {e}")
        return {}
    
    # Extract the solution
    mapping = {}
    total_weight = 0.0
    
    for (c_id, s_id), var in x_vars.items():
        if var.value() and var.value() > 0.5:  # Binary variable should be 0 or 1
            mapping[c_id] = s_id
            # Find the items for logging
            c_item = next(c for c in content_items if c['id'] == c_id)
            s_item = next(s for s in shape_items if s['sid'] == s_id)
            weight = weight_fn(c_item, s_item)
            total_weight += weight
            logger.debug(f"Mapped {c_id} -> {s_id} (weight: {weight:.2f})")
    
    logger.info(f"ILP solver found mapping with total weight: {total_weight:.2f}")
    return mapping


def default_weight_fn(
    content: Dict[str, Any],
    shape: Dict[str, Any]
) -> float:
    """
    Default weight function for content-shape pairing
    
    Higher weight = better match
    """
    weight = 0.0
    
    # 1. Designer tag match (highest priority)
    tags = shape.get('tags', [])
    for tag in tags:
        if tag.lower().startswith("slot:") and content['id'].lower() in tag.lower():
            weight += 3.0
            break
    
    # 2. Vision role match
    vision_role = shape.get('vision_role') or shape.get('role')
    if vision_role and shape.get('place_ok', True):
        if role_compatible(content.get('type'), vision_role):
            weight += 2.0
    
    # 3. Placeholder type match
    if type_compatible(content.get('type'), shape.get('ph_type')):
        weight += 1.0
    
    # 4. Archetype alignment bonus
    if shape.get('archetype_hint') and content.get('intent'):
        if shape['archetype_hint'] == content['intent']:
            weight += 0.5
    
    # 5. Geometric priors
    weight += geometric_bonus(content, shape)
    
    # 6. Safety penalty (negative weight)
    safety_penalty = shape.get('safety_penalty', 0.0)
    weight -= safety_penalty * 2.0
    
    # 7. Overflow risk (negative weight)
    overflow = estimate_overflow_risk(content, shape)
    weight -= overflow * 1.0
    
    # 8. Priority bonus (lower priority number = better)
    priority = shape.get('priority', 5)
    weight += max(0, (6 - priority)) * 0.1
    
    return max(0, weight)  # Ensure non-negative


def default_compat_fn(
    content: Dict[str, Any],
    shape: Dict[str, Any]
) -> bool:
    """
    Default compatibility function for content-shape pairing
    
    Returns True if the pair is compatible (hard constraint)
    """
    # Check if shape is placeable
    if not shape.get('place_ok', True):
        return False
    
    content_type = content.get('type', 'BODY')
    shape_type = shape.get('ph_type', 'BODY')
    
    # Type-specific compatibility rules
    if content_type == 'CHART':
        return shape_type in ['CHART', 'BODY', 'TEXTBOX', 'PICTURE', 'OBJECT']
    elif content_type == 'TABLE':
        return shape_type in ['TABLE', 'BODY', 'TEXTBOX', 'OBJECT']
    elif content_type == 'IMAGE':
        return shape_type in ['PICTURE', 'BODY', 'TEXTBOX', 'OBJECT']
    elif content_type in ['TITLE', 'SUBTITLE']:
        return shape_type in ['TITLE', 'SUBTITLE', 'BODY', 'TEXTBOX']
    elif content_type == 'BODY':
        return shape_type in ['BODY', 'TEXTBOX', 'CONTENT', 'OBJECT']
    else:
        # Default: allow most combinations except very specific types
        return shape_type not in ['CHART', 'TABLE', 'PICTURE']


def role_compatible(content_type: str, vision_role: str) -> bool:
    """Check if content type is compatible with vision-detected role"""
    role_lower = vision_role.lower()
    
    if content_type == 'TITLE':
        return 'title' in role_lower or 'heading' in role_lower
    elif content_type == 'SUBTITLE':
        return 'subtitle' in role_lower or 'subheading' in role_lower
    elif content_type == 'BODY':
        return any(x in role_lower for x in ['body', 'bullet', 'text', 'content'])
    elif content_type == 'CHART':
        return 'chart' in role_lower or 'graph' in role_lower
    elif content_type == 'TABLE':
        return 'table' in role_lower
    elif content_type == 'IMAGE':
        return any(x in role_lower for x in ['image', 'picture', 'photo'])
    
    return False


def type_compatible(content_type: str, placeholder_type: str) -> bool:
    """Check if content type is compatible with placeholder type"""
    if not placeholder_type:
        return False
    
    ph_lower = placeholder_type.lower()
    content_lower = content_type.lower()
    
    # Direct match
    if content_lower == ph_lower:
        return True
    
    # Semantic matches
    compat_map = {
        'title': ['title', 'heading'],
        'subtitle': ['subtitle', 'subheading'],
        'body': ['body', 'content', 'text', 'textbox'],
        'chart': ['chart', 'graph'],
        'table': ['table'],
        'image': ['picture', 'image', 'photo']
    }
    
    if content_lower in compat_map:
        return any(c in ph_lower for c in compat_map[content_lower])
    
    return False


def geometric_bonus(content: Dict[str, Any], shape: Dict[str, Any]) -> float:
    """Calculate geometric preference bonus"""
    bonus = 0.0
    bbox = shape.get('bbox_px', {})
    
    if not bbox:
        return bonus
    
    # Get normalized position
    slide_width = shape.get('slide_width', 1920)
    slide_height = shape.get('slide_height', 1080)
    
    left = bbox.get('left', 0) / slide_width
    top = bbox.get('top', 0) / slide_height
    width = bbox.get('width', 0) / slide_width
    height = bbox.get('height', 0) / slide_height
    
    cx = left + width / 2
    cy = top + height / 2
    area = width * height
    
    content_type = content.get('type', 'BODY')
    
    # Title prefers top-center
    if content_type == 'TITLE':
        if cy < 0.25:  # Top quarter
            bonus += 0.3
        if abs(cx - 0.5) < 0.2:  # Centered
            bonus += 0.2
    
    # Subtitle prefers below title
    elif content_type == 'SUBTITLE':
        if 0.2 < cy < 0.4:  # Upper-middle
            bonus += 0.2
    
    # Body prefers larger areas
    elif content_type == 'BODY':
        if area > 0.3:  # Large area
            bonus += 0.3
        elif area > 0.15:  # Medium area
            bonus += 0.15
    
    # Charts/Tables prefer center-large
    elif content_type in ['CHART', 'TABLE']:
        if area > 0.25:
            bonus += 0.3
        if 0.3 < cx < 0.7 and 0.3 < cy < 0.7:  # Central
            bonus += 0.2
    
    # Images can be anywhere but prefer sides
    elif content_type == 'IMAGE':
        if cx < 0.3 or cx > 0.7:  # Sides
            bonus += 0.1
    
    return bonus


def estimate_overflow_risk(
    content: Dict[str, Any],
    shape: Dict[str, Any]
) -> float:
    """
    Estimate risk of content overflowing the shape
    
    Returns risk score from 0 (no risk) to 1 (high risk)
    """
    # Get content size hint
    size_hint = content.get('size_hint', 'M')
    size_map = {'XS': 0.1, 'S': 0.3, 'M': 0.5, 'L': 0.7, 'XL': 0.9}
    content_size = size_map.get(size_hint, 0.5)
    
    # Get shape area
    bbox = shape.get('bbox_px', {})
    if not bbox:
        return 0.5  # Unknown risk
    
    slide_width = shape.get('slide_width', 1920)
    slide_height = shape.get('slide_height', 1080)
    
    width = bbox.get('width', 0) / slide_width
    height = bbox.get('height', 0) / slide_height
    shape_area = width * height
    
    # Estimate overflow risk
    if shape_area < 0.1:  # Very small shape
        if content_size > 0.3:
            return 0.8
        return 0.4
    elif shape_area < 0.2:  # Small shape
        if content_size > 0.5:
            return 0.6
        return 0.2
    elif shape_area < 0.4:  # Medium shape
        if content_size > 0.7:
            return 0.4
        return 0.1
    else:  # Large shape
        if content_size > 0.9:
            return 0.2
        return 0.0


def choose_layout_and_mapping(
    layouts: List[Dict[str, Any]],
    content_spec: List[Dict[str, Any]],
    config: Optional[Dict[str, Any]] = None
) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """
    Choose the best layout and compute optimal content-shape mapping
    
    Args:
        layouts: List of candidate layouts with shapes
        content_spec: List of content items to place
        config: Optional configuration parameters
    
    Returns:
        Tuple of (chosen_layout, mapping)
        - chosen_layout: Best layout dictionary
        - mapping: Dict mapping content_id to shape_sid
    """
    if not layouts:
        logger.error("No layouts available for mapping")
        return {}, {}
    
    if not content_spec:
        logger.warning("No content to map")
        return layouts[0], {}
    
    config = config or {}
    timeout = config.get('timeout', 10)
    msg = config.get('msg', False)
    
    # Custom weight/compat functions if provided
    weight_fn = config.get('weight_fn', default_weight_fn)
    compat_fn = config.get('compat_fn', default_compat_fn)
    
    best_layout = None
    best_mapping = {}
    best_score = -float('inf')
    
    for layout in layouts:
        shapes = layout.get('shapes', [])
        if not shapes:
            continue
        
        # Prepare shape items with additional metadata
        shape_items = []
        for shape in shapes:
            shape_item = {
                'sid': shape.get('id') or shape.get('shape_id'),
                'ph_type': shape.get('ph_type'),
                'role': shape.get('role'),
                'vision_role': shape.get('vision_role'),
                'bbox_px': shape.get('bbox_px'),
                'bbox_norm': shape.get('bbox_norm'),
                'place_ok': shape.get('place_ok', True),
                'place_content': shape.get('place_content', True),
                'safety_penalty': shape.get('safety_penalty', 0.0),
                'priority': shape.get('priority', 5),
                'tags': shape.get('tags', []),
                'archetype_hint': layout.get('archetype_hint'),
                'slide_width': layout.get('slide_width', 1920),
                'slide_height': layout.get('slide_height', 1080)
            }
            shape_items.append(shape_item)
        
        # Solve assignment for this layout
        mapping = solve_assignment(
            content_spec,
            shape_items,
            weight_fn,
            compat_fn,
            timeout,
            msg
        )
        
        # Calculate total score for this solution
        total_score = 0.0
        mapped_count = 0
        required_mapped = 0
        required_total = sum(1 for c in content_spec if c.get('required', False))
        
        for c_item in content_spec:
            if c_item['id'] in mapping:
                s_id = mapping[c_item['id']]
                s_item = next(s for s in shape_items if s['sid'] == s_id)
                total_score += weight_fn(c_item, s_item)
                mapped_count += 1
                if c_item.get('required', False):
                    required_mapped += 1
        
        # Penalize if required items not mapped
        if required_total > 0:
            coverage_ratio = required_mapped / required_total
            total_score *= coverage_ratio
        
        # Bonus for mapping more items
        total_score += mapped_count * 0.1
        
        logger.debug(f"Layout {layout.get('name', 'unnamed')}: "
                    f"score={total_score:.2f}, mapped={mapped_count}/{len(content_spec)}")
        
        if total_score > best_score:
            best_score = total_score
            best_layout = layout
            best_mapping = mapping
    
    if best_layout:
        logger.info(f"Selected layout {best_layout.get('name', 'unnamed')} "
                   f"with score {best_score:.2f}")
    else:
        logger.warning("No suitable layout found, using first available")
        best_layout = layouts[0]
    
    return best_layout, best_mapping


def create_mapping_report(
    mapping: Dict[str, str],
    content_spec: List[Dict[str, Any]],
    shapes: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Create a detailed report of the mapping solution
    
    Args:
        mapping: Content ID to shape ID mapping
        content_spec: List of content items
        shapes: List of shape items
    
    Returns:
        Report dictionary with statistics and details
    """
    report = {
        'total_content': len(content_spec),
        'mapped_content': len(mapping),
        'unmapped_content': [],
        'mapping_details': [],
        'statistics': {}
    }
    
    # Find unmapped content
    for content in content_spec:
        if content['id'] not in mapping:
            report['unmapped_content'].append({
                'id': content['id'],
                'type': content.get('type'),
                'required': content.get('required', False)
            })
    
    # Detail each mapping
    for content_id, shape_id in mapping.items():
        content = next((c for c in content_spec if c['id'] == content_id), None)
        shape = next((s for s in shapes if s.get('id') == shape_id or s.get('sid') == shape_id), None)
        
        if content and shape:
            report['mapping_details'].append({
                'content_id': content_id,
                'content_type': content.get('type'),
                'shape_id': shape_id,
                'shape_type': shape.get('ph_type'),
                'shape_role': shape.get('role') or shape.get('vision_role'),
                'safety_penalty': shape.get('safety_penalty', 0),
                'priority': shape.get('priority', 5)
            })
    
    # Calculate statistics
    report['statistics'] = {
        'mapping_rate': len(mapping) / len(content_spec) if content_spec else 0,
        'required_mapped': sum(
            1 for c in content_spec 
            if c.get('required') and c['id'] in mapping
        ),
        'avg_safety_penalty': np.mean([
            d['safety_penalty'] for d in report['mapping_details']
        ]) if report['mapping_details'] else 0
    }
    
    return report