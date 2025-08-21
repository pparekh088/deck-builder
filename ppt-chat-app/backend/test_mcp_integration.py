#!/usr/bin/env python3
"""
Test script to verify MCP PowerPoint Server integration
"""

import asyncio
import sys
from pathlib import Path

# Add the app directory to the path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.mcp_client import mcp_client
from app.services.ppt_service import ppt_service
from app.services.simple_slide_tools import simple_slide_tools

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

async def test_ppt_service():
    """Test the updated ppt_service with MCP"""
    print("\nTesting ppt_service integration...")
    try:
        # Test markdown to PPTX conversion
        markdown = """
# Introduction
- Welcome to the presentation
- This is a test slide
- Created using MCP server

# Features
- MCP Server integration
- Automatic slide generation
- Template support

# Conclusion
- Thank you for watching
- Questions?
"""
        output_path, previews = ppt_service.markdown_to_pptx(
            markdown=markdown,
            session_id="test_session"
        )
        print(f"✓ Created presentation from markdown: {output_path}")
        print(f"✓ Generated {len(previews)} slide previews")
        return True
    except Exception as e:
        print(f"✗ Failed to test ppt_service: {e}")
        return False

async def test_simple_slide_tools():
    """Test the updated simple_slide_tools with MCP"""
    print("\nTesting simple_slide_tools integration...")
    try:
        # Create a test presentation
        template_path = Path("/workspace/ppt-chat-app/backend/uploads/test_template.pptx")
        output_path = Path("/workspace/ppt-chat-app/backend/uploads/test_tools_output.pptx")
        
        # First create a simple template if it doesn't exist
        if not template_path.exists():
            pres_id = await mcp_client.create_presentation()
            await mcp_client.add_slide(layout_index=0)  # Title slide
            await mcp_client.save_presentation(str(template_path), pres_id)
            print(f"✓ Created template: {template_path}")
        
        # Test creating presentation from template
        result = simple_slide_tools.create_presentation(
            template_path, output_path, "Create a test presentation"
        )
        print(f"✓ Created presentation: {result}")
        
        # Test adding a slide
        result = await simple_slide_tools.add_new_slide(
            output_path,
            "New Test Slide",
            ["Point 1", "Point 2", "Point 3"]
        )
        print(f"✓ Added slide: {result}")
        
        # Test editing a slide
        result = simple_slide_tools.edit_slide_content(
            output_path,
            slide_number=1,
            new_title="Updated Title",
            add_bullets=["Additional point"]
        )
        print(f"✓ Edited slide: {result}")
        
        return True
    except Exception as e:
        print(f"✗ Failed to test simple_slide_tools: {e}")
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
    
    # Test service integrations
    if not await test_ppt_service():
        all_passed = False
    
    if not await test_simple_slide_tools():
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