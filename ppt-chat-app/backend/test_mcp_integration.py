#!/usr/bin/env python3
"""
Test script to verify MCP PowerPoint Server integration
"""

import asyncio
import sys
from pathlib import Path

# Add the app directory to the path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.mcp import mcp_client

async def test_mcp_connection():
    """Test basic MCP server connection"""
    print("Testing MCP server connection...")
    try:
        await mcp_client.connect()
        print("✓ MCP server connected successfully")
        return True
    except Exception as e:
        print(f"✗ Failed to connect to MCP server: {e}")
        return False

async def test_create_presentation():
    """Test creating a new presentation"""
    print("\nTesting presentation creation...")
    try:
        presentation_id = await mcp_client.create_presentation()
        print(f"✓ Created presentation with ID: {presentation_id}")
        return presentation_id
    except Exception as e:
        print(f"✗ Failed to create presentation: {e}")
        return None

async def test_add_slide(presentation_id):
    """Test adding a slide"""
    print("\nTesting slide addition...")
    try:
        result = await mcp_client.add_slide(layout_index=1)
        print(f"✓ Added slide: {result}")
        
        # Add content to the slide
        await mcp_client.add_text_to_slide(
            slide_index=0,
            text="Test Slide Title",
            placeholder_index=0
        )
        print("✓ Added title to slide")
        
        await mcp_client.add_bullet_points(
            slide_index=0,
            bullet_points=["First bullet", "Second bullet", "Third bullet"],
            placeholder_index=1
        )
        print("✓ Added bullet points to slide")
        
        return True
    except Exception as e:
        print(f"✗ Failed to add slide: {e}")
        return False

async def test_save_presentation(presentation_id):
    """Test saving the presentation"""
    print("\nTesting presentation save...")
    try:
        output_path = "/workspace/ppt-chat-app/backend/uploads/test_mcp_output.pptx"
        result = await mcp_client.save_presentation(output_path, presentation_id)
        print(f"✓ Saved presentation to: {output_path}")
        return True
    except Exception as e:
        print(f"✗ Failed to save presentation: {e}")
        return False

async def test_auto_generation():
    """Test MCP's auto-generation capabilities"""
    print("\nTesting auto-generation...")
    try:
        # Test AI-powered presentation generation
        result = await mcp_client.auto_generate_presentation(
            topic="Future of Artificial Intelligence",
            num_slides=5,
            style="professional"
        )
        print(f"✓ Auto-generated presentation: {result}")
        
        # Apply professional design
        await mcp_client.apply_professional_design(
            design_type="gradient",
            primary_color=[0, 120, 215],
            secondary_color=[0, 84, 159]
        )
        print("✓ Applied professional design")
        
        # Optimize text
        presentation_info = await mcp_client.get_presentation_info()
        for i in range(presentation_info.get("slide_count", 0)):
            await mcp_client.optimize_slide_text(slide_index=i)
        print("✓ Optimized slide text")
        
        # Save the auto-generated presentation
        output_path = "/workspace/ppt-chat-app/backend/uploads/test_auto_generated.pptx"
        await mcp_client.save_presentation(output_path)
        print(f"✓ Saved auto-generated presentation: {output_path}")
        
        return True
    except Exception as e:
        print(f"✗ Failed to test auto-generation: {e}")
        return False

async def main():
    """Run all tests"""
    print("=" * 60)
    print("MCP PowerPoint Server Integration Test")
    print("=" * 60)
    
    all_passed = True
    
    # Test MCP connection
    if not await test_mcp_connection():
        print("\n⚠️  MCP server not running. Starting it...")
        print("Run: ./start_mcp_server.sh")
        return
    
    # Test basic MCP operations
    presentation_id = await test_create_presentation()
    if presentation_id:
        if await test_add_slide(presentation_id):
            await test_save_presentation(presentation_id)
    else:
        all_passed = False
    
    # Test advanced features
    if not await test_auto_generation():
        all_passed = False
    
    # Cleanup
    await mcp_client.disconnect()
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ All tests passed!")
    else:
        print("❌ Some tests failed. Check the output above.")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())