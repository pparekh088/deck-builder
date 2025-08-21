#!/usr/bin/env python3
"""
CLI tool for end-to-end accuracy validation
"""

import sys
import os
import json
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tests.accuracy.utils import (
    create_fixture_pptx, APIClient, simple_spec, wait_for_api, get_env_flag
)


def print_header(text: str):
    """Print a formatted header"""
    print(f"\n{'='*60}")
    print(f" {text}")
    print(f"{'='*60}")


def print_section(text: str):
    """Print a section header"""
    print(f"\n{'-'*40}")
    print(f" {text}")
    print(f"{'-'*40}")


def validate_accuracy():
    """Run end-to-end accuracy validation"""
    print_header("ACCURACY++ VALIDATION CLI")
    
    # Check API availability
    print("\n🔍 Checking API availability...")
    if not wait_for_api():
        print("❌ API not available at http://localhost:8006")
        print("   Please start the API with: uvicorn app.main:app --reload")
        return 1
    print("✅ API is available")
    
    # Check feature flags
    print_section("Feature Flags")
    features = {
        "HYBRID_VISION_ENABLED": get_env_flag("HYBRID_VISION_ENABLED"),
        "ACCURATE_SOLVER_ENABLED": get_env_flag("ACCURATE_SOLVER_ENABLED"),
        "RENDER_MEASURE_ENABLED": get_env_flag("RENDER_MEASURE_ENABLED"),
        "ARCHETYPE_ALIGNMENT_ENABLED": get_env_flag("ARCHETYPE_ALIGNMENT_ENABLED"),
        "SAFETY_MAP_ENABLED": get_env_flag("SAFETY_MAP_ENABLED")
    }
    
    for flag, enabled in features.items():
        status = "✅ ON" if enabled else "❌ OFF"
        print(f"  {flag}: {status}")
    
    # Create API client
    client = APIClient()
    
    try:
        # Step 1: Create and ingest fixture template
        print_section("Step 1: Template Ingestion")
        print("Creating fixture PPTX with decor and two-column layout...")
        pptx_path = create_fixture_pptx(include_decor=True, include_two_column=True)
        print(f"✅ Created fixture: {pptx_path}")
        
        print("Uploading template...")
        response = client.ingest_template(pptx_path)
        
        if "template_id" not in response:
            print(f"❌ Failed to get template_id: {response}")
            return 1
        
        template_id = response["template_id"]
        print(f"✅ Template uploaded: {template_id}")
        
        # Step 2: Fetch and analyze profile
        print_section("Step 2: Template Profile Analysis")
        print("Fetching template profile...")
        profile = client.get_template_profile(template_id)
        
        if "layouts" not in profile:
            print(f"❌ Profile missing layouts: {profile.keys()}")
            return 1
        
        print(f"✅ Profile contains {len(profile['layouts'])} layouts")
        
        # Analyze profile features
        vision_count = 0
        archetype_count = 0
        safety_count = 0
        
        for layout in profile["layouts"]:
            if "archetype_hint" in layout and layout["archetype_hint"]:
                archetype_count += 1
                print(f"   Layout '{layout.get('name', 'unnamed')}': archetype={layout['archetype_hint']}")
            
            for shape in layout.get("shapes", []):
                if any(k in shape for k in ["vision", "vision_role", "place_content"]):
                    vision_count += 1
                if "safety_penalty" in shape:
                    safety_count += 1
        
        if features["HYBRID_VISION_ENABLED"] and vision_count == 0:
            print("⚠️  Warning: HYBRID_VISION_ENABLED but no vision labels found")
        elif vision_count > 0:
            print(f"✅ Found {vision_count} shapes with vision labels")
        
        if features["ARCHETYPE_ALIGNMENT_ENABLED"] and archetype_count == 0:
            print("⚠️  Warning: ARCHETYPE_ALIGNMENT_ENABLED but no archetypes found")
        elif archetype_count > 0:
            print(f"✅ Found {archetype_count} layouts with archetype hints")
        
        if features["SAFETY_MAP_ENABLED"] and safety_count == 0:
            print("⚠️  Warning: SAFETY_MAP_ENABLED but no safety penalties found")
        elif safety_count > 0:
            print(f"✅ Found {safety_count} shapes with safety penalties")
        
        # Step 3: Generate presentation
        print_section("Step 3: Presentation Generation")
        print("Generating presentation with overflow content...")
        content_spec = simple_spec(num_slides=3, include_overflow=True)
        
        response = client.generate_presentation(template_id, content_spec)
        
        if "session_id" not in response:
            print(f"❌ Failed to get session_id: {response}")
            return 1
        
        session_id = response["session_id"]
        print(f"✅ Generated presentation: {session_id}")
        
        # Step 4: Analyze placements
        print_section("Step 4: Placement Analysis")
        
        if "placements" in response:
            placements = response["placements"]
            print(f"✅ Response includes {len(placements)} placements")
            
            # Sample placement
            if placements:
                sample = placements[0]
                print("\n📋 Sample placement:")
                print(f"   {json.dumps(sample, indent=4)}")
            
            # Check safety
            if features["SAFETY_MAP_ENABLED"]:
                unsafe = [p for p in placements if p.get("safety_ok") == False]
                if unsafe:
                    print(f"⚠️  Warning: {len(unsafe)} unsafe placements found")
                else:
                    print(f"✅ All placements are in safe areas")
        else:
            if features["ACCURATE_SOLVER_ENABLED"]:
                print("⚠️  Warning: ACCURATE_SOLVER_ENABLED but no placements in response")
                print("   API may need update to include placements")
            else:
                print("ℹ️  No placements (solver disabled)")
        
        # Step 5: Analyze render metrics
        print_section("Step 5: Render Metrics Analysis")
        
        if "render_metrics" in response:
            metrics = response["render_metrics"]
            print(f"✅ Response includes render_metrics")
            
            print("\n📊 Render metrics:")
            print(f"   {json.dumps(metrics, indent=4)}")
            
            font_shrink = metrics.get("font_shrink_events", 0)
            slides_added = metrics.get("continuation_slides_added", 0)
            
            if features["RENDER_MEASURE_ENABLED"]:
                if font_shrink > 0 or slides_added > 0:
                    print(f"✅ Overflow handled: {font_shrink} shrinks, {slides_added} splits")
                else:
                    print("ℹ️  No overflow corrections needed")
        else:
            if features["RENDER_MEASURE_ENABLED"]:
                print("⚠️  Warning: RENDER_MEASURE_ENABLED but no render_metrics in response")
                print("   API may need update to include render_metrics")
            else:
                print("ℹ️  No render metrics (measurement disabled)")
        
        # Summary
        print_header("VALIDATION SUMMARY")
        
        all_good = True
        
        # Check each acceptance criteria
        criteria = []
        
        if features["HYBRID_VISION_ENABLED"]:
            passed = vision_count > 0
            criteria.append(("Vision labels present", passed))
            all_good = all_good and passed
        
        if features["ARCHETYPE_ALIGNMENT_ENABLED"]:
            passed = archetype_count > 0
            criteria.append(("Archetype hints present", passed))
            all_good = all_good and passed
        
        if features["ACCURATE_SOLVER_ENABLED"]:
            passed = "placements" in response
            criteria.append(("Placements generated", passed))
            if passed and features["SAFETY_MAP_ENABLED"]:
                unsafe = any(p.get("safety_ok") == False for p in response["placements"])
                passed_safety = not unsafe
                criteria.append(("All placements safe", passed_safety))
                all_good = all_good and passed_safety
            all_good = all_good and passed
        
        if features["RENDER_MEASURE_ENABLED"]:
            passed = "render_metrics" in response
            criteria.append(("Render metrics present", passed))
            all_good = all_good and passed
        
        for criterion, passed in criteria:
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"  {criterion}: {status}")
        
        if all_good:
            print("\n🎉 All validation checks passed!")
            return 0
        else:
            print("\n⚠️  Some validation checks failed or need attention")
            return 1
        
    except Exception as e:
        print(f"\n❌ Error during validation: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    finally:
        client.close()
        if 'pptx_path' in locals():
            pptx_path.unlink(missing_ok=True)


if __name__ == "__main__":
    sys.exit(validate_accuracy())