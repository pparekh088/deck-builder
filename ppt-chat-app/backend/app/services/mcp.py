"""
MCP Client Service for PowerPoint Server Integration
Direct access to ALL 33 tools available in the Office-PowerPoint-MCP-Server
This is the primary interface for all PowerPoint operations.
"""

import asyncio
import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger(__name__)

@dataclass
class MCPServerConfig:
    """Configuration for MCP Server connection"""
    transport: str = "http"  # "stdio" or "http"
    server_path: str = "/workspace/Office-PowerPoint-MCP-Server/ppt_mcp_server.py"
    http_port: int = 8000
    http_host: str = "localhost"

class MCPPowerPointClient:
    """Complete MCP client with access to ALL server tools"""
    
    def __init__(self, config: Optional[MCPServerConfig] = None):
        self.config = config or MCPServerConfig()
        self.session: Optional[ClientSession] = None
        self.http_client: Optional[httpx.AsyncClient] = None
        self.current_presentation_id: Optional[str] = None
        self._server_process = None
        
    async def connect(self):
        """Connect to the MCP server"""
        try:
            if self.config.transport == "stdio":
                await self._connect_stdio()
            elif self.config.transport == "http":
                await self._connect_http()
            else:
                raise ValueError(f"Unsupported transport: {self.config.transport}")
                
            logger.info(f"Successfully connected to MCP server via {self.config.transport}")
        except Exception as e:
            logger.error(f"Failed to connect to MCP server: {e}")
            raise
    
    async def _connect_stdio(self):
        """Connect to MCP server via stdio"""
        server_params = StdioServerParameters(
            command=sys.executable,
            args=[self.config.server_path]
        )
        
        async with stdio_client(server_params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                self.session = session
                await session.initialize()
                logger.info("MCP stdio session initialized")
    
    async def _connect_http(self):
        """Connect to MCP server via HTTP"""
        await self._start_http_server()
        
        self.http_client = httpx.AsyncClient(
            base_url=f"http://{self.config.http_host}:{self.config.http_port}",
            timeout=30.0
        )
        
        # Test connection
        try:
            response = await self.http_client.get("/health")
            if response.status_code != 200:
                raise ConnectionError("Failed to connect to MCP HTTP server")
        except httpx.ConnectError:
            logger.warning("Health endpoint not available, server may still be functional")
    
    async def _start_http_server(self):
        """Start the MCP server in HTTP mode"""
        if self._server_process and self._server_process.poll() is None:
            logger.info("MCP server already running")
            return
            
        cmd = [
            sys.executable,
            self.config.server_path,
            "--transport", "http",
            "--port", str(self.config.http_port)
        ]
        
        logger.info(f"Starting MCP server: {' '.join(cmd)}")
        self._server_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        await asyncio.sleep(2)
        
        if self._server_process.poll() is not None:
            stdout, stderr = self._server_process.communicate()
            raise RuntimeError(f"MCP server failed to start: {stderr.decode()}")
    
    async def disconnect(self):
        """Disconnect from the MCP server"""
        try:
            if self.session:
                self.session = None
            
            if self.http_client:
                await self.http_client.aclose()
                self.http_client = None
            
            if self._server_process:
                self._server_process.terminate()
                self._server_process = None
                
            logger.info("Disconnected from MCP server")
        except Exception as e:
            logger.error(f"Error disconnecting from MCP server: {e}")
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool on the MCP server"""
        try:
            if self.config.transport == "stdio":
                return await self._call_tool_stdio(tool_name, arguments)
            elif self.config.transport == "http":
                return await self._call_tool_http(tool_name, arguments)
            else:
                raise ValueError(f"Unsupported transport: {self.config.transport}")
        except Exception as e:
            logger.error(f"Error calling tool {tool_name}: {e}")
            raise
    
    async def _call_tool_stdio(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool via stdio session"""
        if not self.session:
            raise RuntimeError("Not connected to MCP server")
        
        result = await self.session.call_tool(tool_name, arguments)
        return result.content if hasattr(result, 'content') else result
    
    async def _call_tool_http(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool via HTTP"""
        if not self.http_client:
            raise RuntimeError("Not connected to MCP server")
        
        response = await self.http_client.post(
            f"/tools/{tool_name}",
            json=arguments
        )
        response.raise_for_status()
        return response.json()
    
    # ========== CORE CONVENIENCE METHODS ==========
    
    async def create_presentation(self, template_path: Optional[str] = None, id: Optional[str] = None) -> str:
        """Create a new PowerPoint presentation"""
        if template_path:
            result = await self.create_presentation_from_template(template_path, id)
        else:
            args = {}
            if id:
                args["id"] = id
            result = await self.call_tool("create_presentation", args)
        self.current_presentation_id = result.get("presentation_id")
        return self.current_presentation_id
    
    async def open_presentation(self, file_path: str, id: Optional[str] = None) -> str:
        """Open an existing PowerPoint presentation"""
        args = {"file_path": file_path}
        if id:
            args["id"] = id
        result = await self.call_tool("open_presentation", args)
        self.current_presentation_id = result.get("presentation_id")
        return self.current_presentation_id
    
    async def save_presentation(self, file_path: str, presentation_id: Optional[str] = None) -> Dict[str, Any]:
        """Save the current presentation"""
        args = {"file_path": file_path}
        if presentation_id:
            args["presentation_id"] = presentation_id
        elif self.current_presentation_id:
            args["presentation_id"] = self.current_presentation_id
        return await self.call_tool("save_presentation", args)
    
    # ========== PRESENTATION TOOLS (7 tools) ==========
    
    async def create_presentation_from_template(self, template_path: str, id: Optional[str] = None) -> Dict[str, Any]:
        """Create a presentation from a template file"""
        args = {"template_path": template_path}
        if id:
            args["id"] = id
        return await self.call_tool("create_presentation_from_template", args)
    
    async def get_presentation_info(self, presentation_id: Optional[str] = None) -> Dict[str, Any]:
        """Get detailed information about the current presentation"""
        args = {}
        if presentation_id:
            args["presentation_id"] = presentation_id
        return await self.call_tool("get_presentation_info", args)
    
    async def get_template_file_info(self, template_path: str) -> Dict[str, Any]:
        """Get information about a template file"""
        return await self.call_tool("get_template_file_info", {"template_path": template_path})
    
    async def set_core_properties(
        self,
        title: Optional[str] = None,
        subject: Optional[str] = None,
        author: Optional[str] = None,
        keywords: Optional[str] = None,
        comments: Optional[str] = None,
        category: Optional[str] = None,
        presentation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Set core properties of the presentation"""
        args = {}
        if title: args["title"] = title
        if subject: args["subject"] = subject
        if author: args["author"] = author
        if keywords: args["keywords"] = keywords
        if comments: args["comments"] = comments
        if category: args["category"] = category
        if presentation_id: args["presentation_id"] = presentation_id
        return await self.call_tool("set_core_properties", args)
    
    # ========== CONTENT TOOLS (8 tools) ==========
    
    async def extract_slide_text(self, slide_index: int, presentation_id: Optional[str] = None) -> Dict[str, Any]:
        """Extract all text from a specific slide"""
        args = {"slide_index": slide_index}
        if presentation_id:
            args["presentation_id"] = presentation_id
        return await self.call_tool("extract_slide_text", args)
    
    async def extract_presentation_text(
        self, 
        presentation_id: Optional[str] = None,
        include_slide_info: bool = True
    ) -> Dict[str, Any]:
        """Extract all text from the entire presentation"""
        args = {"include_slide_info": include_slide_info}
        if presentation_id:
            args["presentation_id"] = presentation_id
        return await self.call_tool("extract_presentation_text", args)
    
    async def populate_placeholder(
        self,
        slide_index: int,
        placeholder_index: int,
        text: str,
        presentation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Populate a specific placeholder with text"""
        args = {
            "slide_index": slide_index,
            "placeholder_index": placeholder_index,
            "text": text
        }
        if presentation_id:
            args["presentation_id"] = presentation_id
        return await self.call_tool("populate_placeholder", args)
    
    async def manage_text(
        self,
        action: str,  # "add", "replace", "format", "delete"
        slide_index: int,
        text: Optional[str] = None,
        placeholder_index: Optional[int] = None,
        paragraph_index: Optional[int] = None,
        run_index: Optional[int] = None,
        font_name: Optional[str] = None,
        font_size: Optional[int] = None,
        bold: Optional[bool] = None,
        italic: Optional[bool] = None,
        underline: Optional[bool] = None,
        color: Optional[List[int]] = None,
        alignment: Optional[str] = None
    ) -> Dict[str, Any]:
        """Comprehensive text management tool"""
        args = {"action": action, "slide_index": slide_index}
        if text: args["text"] = text
        if placeholder_index is not None: args["placeholder_index"] = placeholder_index
        if paragraph_index is not None: args["paragraph_index"] = paragraph_index
        if run_index is not None: args["run_index"] = run_index
        if font_name: args["font_name"] = font_name
        if font_size: args["font_size"] = font_size
        if bold is not None: args["bold"] = bold
        if italic is not None: args["italic"] = italic
        if underline is not None: args["underline"] = underline
        if color: args["color"] = color
        if alignment: args["alignment"] = alignment
        return await self.call_tool("manage_text", args)
    
    async def manage_image(
        self,
        action: str,  # "add", "replace", "resize", "move", "delete"
        slide_index: int,
        image_path: Optional[str] = None,
        placeholder_index: Optional[int] = None,
        left: Optional[float] = None,
        top: Optional[float] = None,
        width: Optional[float] = None,
        height: Optional[float] = None,
        shape_index: Optional[int] = None
    ) -> Dict[str, Any]:
        """Comprehensive image management tool"""
        args = {"action": action, "slide_index": slide_index}
        if image_path: args["image_path"] = image_path
        if placeholder_index is not None: args["placeholder_index"] = placeholder_index
        if left is not None: args["left"] = left
        if top is not None: args["top"] = top
        if width is not None: args["width"] = width
        if height is not None: args["height"] = height
        if shape_index is not None: args["shape_index"] = shape_index
        return await self.call_tool("manage_image", args)
    
    # ========== STRUCTURAL TOOLS (4 tools) ==========
    
    async def format_table_cell(
        self,
        slide_index: int,
        table_index: int,
        row: int,
        col: int,
        text: Optional[str] = None,
        font_name: Optional[str] = None,
        font_size: Optional[int] = None,
        bold: Optional[bool] = None,
        italic: Optional[bool] = None,
        fill_color: Optional[List[int]] = None,
        text_color: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """Format a specific table cell"""
        args = {
            "slide_index": slide_index,
            "table_index": table_index,
            "row": row,
            "col": col
        }
        if text: args["text"] = text
        if font_name: args["font_name"] = font_name
        if font_size: args["font_size"] = font_size
        if bold is not None: args["bold"] = bold
        if italic is not None: args["italic"] = italic
        if fill_color: args["fill_color"] = fill_color
        if text_color: args["text_color"] = text_color
        return await self.call_tool("format_table_cell", args)
    
    async def add_shape(
        self,
        slide_index: int,
        shape_type: str,
        left: float,
        top: float,
        width: float,
        height: float,
        text: Optional[str] = None,
        fill_color: Optional[List[int]] = None,
        line_color: Optional[List[int]] = None,
        line_width: Optional[float] = None
    ) -> Dict[str, Any]:
        """Add a shape to a slide"""
        args = {
            "slide_index": slide_index,
            "shape_type": shape_type,
            "left": left,
            "top": top,
            "width": width,
            "height": height
        }
        if text: args["text"] = text
        if fill_color: args["fill_color"] = fill_color
        if line_color: args["line_color"] = line_color
        if line_width is not None: args["line_width"] = line_width
        return await self.call_tool("add_shape", args)
    
    # ========== TEMPLATE TOOLS (7 tools) ==========
    
    async def list_slide_templates(self) -> Dict[str, Any]:
        """List all available slide templates"""
        return await self.call_tool("list_slide_templates", {})
    
    async def apply_slide_template(
        self,
        slide_index: int,
        template_id: str,
        preserve_content: bool = True
    ) -> Dict[str, Any]:
        """Apply a template to a specific slide"""
        args = {
            "slide_index": slide_index,
            "template_id": template_id,
            "preserve_content": preserve_content
        }
        return await self.call_tool("apply_slide_template", args)
    
    async def create_slide_from_template(
        self,
        template_id: str,
        position: Optional[int] = None,
        content: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a new slide from a template"""
        args = {"template_id": template_id}
        if position is not None: args["position"] = position
        if content: args["content"] = content
        return await self.call_tool("create_slide_from_template", args)
    
    async def create_presentation_from_templates(
        self,
        template_specs: List[Dict[str, Any]],
        id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a presentation from multiple templates"""
        args = {"template_specs": template_specs}
        if id: args["id"] = id
        return await self.call_tool("create_presentation_from_templates", args)
    
    async def get_template_info(self, template_id: str) -> Dict[str, Any]:
        """Get detailed information about a template"""
        return await self.call_tool("get_template_info", {"template_id": template_id})
    
    async def auto_generate_presentation(
        self,
        topic: str,
        num_slides: int = 5,
        style: str = "professional",
        include_images: bool = False,
        template_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Auto-generate a presentation on a topic"""
        args = {
            "topic": topic,
            "num_slides": num_slides,
            "style": style,
            "include_images": include_images
        }
        if template_id: args["template_id"] = template_id
        return await self.call_tool("auto_generate_presentation", args)
    
    async def optimize_slide_text(
        self,
        slide_index: int,
        max_chars_per_line: int = 50,
        max_lines_per_bullet: int = 2,
        font_size_range: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """Optimize text on a slide for readability"""
        args = {
            "slide_index": slide_index,
            "max_chars_per_line": max_chars_per_line,
            "max_lines_per_bullet": max_lines_per_bullet
        }
        if font_size_range: args["font_size_range"] = font_size_range
        return await self.call_tool("optimize_slide_text", args)
    
    # ========== PROFESSIONAL TOOLS (3 tools) ==========
    
    async def apply_professional_design(
        self,
        design_type: str,  # "gradient", "pattern", "theme", etc.
        slide_index: Optional[int] = None,  # None for all slides
        primary_color: Optional[List[int]] = None,
        secondary_color: Optional[List[int]] = None,
        pattern: Optional[str] = None
    ) -> Dict[str, Any]:
        """Apply professional design elements"""
        args = {"design_type": design_type}
        if slide_index is not None: args["slide_index"] = slide_index
        if primary_color: args["primary_color"] = primary_color
        if secondary_color: args["secondary_color"] = secondary_color
        if pattern: args["pattern"] = pattern
        return await self.call_tool("apply_professional_design", args)
    
    async def apply_picture_effects(
        self,
        slide_index: int,
        picture_index: int,
        effect_type: str,  # "shadow", "reflection", "glow", "soft_edges", "3d_rotation"
        intensity: str = "medium"  # "subtle", "medium", "intense"
    ) -> Dict[str, Any]:
        """Apply effects to pictures"""
        args = {
            "slide_index": slide_index,
            "picture_index": picture_index,
            "effect_type": effect_type,
            "intensity": intensity
        }
        return await self.call_tool("apply_picture_effects", args)
    
    async def manage_fonts(
        self,
        action: str,  # "standardize", "replace", "list"
        target_font: Optional[str] = None,
        replacement_font: Optional[str] = None,
        apply_to: str = "all"  # "all", "titles", "body", "slide_index"
    ) -> Dict[str, Any]:
        """Manage fonts across the presentation"""
        args = {
            "action": action,
            "apply_to": apply_to
        }
        if target_font: args["target_font"] = target_font
        if replacement_font: args["replacement_font"] = replacement_font
        return await self.call_tool("manage_fonts", args)
    
    # ========== HYPERLINK TOOLS (1 tool) ==========
    
    async def manage_hyperlinks(
        self,
        action: str,  # "add", "update", "remove", "list"
        slide_index: Optional[int] = None,
        text: Optional[str] = None,
        url: Optional[str] = None,
        shape_index: Optional[int] = None
    ) -> Dict[str, Any]:
        """Manage hyperlinks in the presentation"""
        args = {"action": action}
        if slide_index is not None: args["slide_index"] = slide_index
        if text: args["text"] = text
        if url: args["url"] = url
        if shape_index is not None: args["shape_index"] = shape_index
        return await self.call_tool("manage_hyperlinks", args)
    
    # ========== CHART TOOLS (1 tool) ==========
    
    async def update_chart_data(
        self,
        slide_index: int,
        chart_index: int,
        categories: List[str],
        series_data: Dict[str, List[float]]
    ) -> Dict[str, Any]:
        """Update data in an existing chart"""
        args = {
            "slide_index": slide_index,
            "chart_index": chart_index,
            "categories": categories,
            "series_data": series_data
        }
        return await self.call_tool("update_chart_data", args)
    
    # ========== CONNECTOR TOOLS (1 tool) ==========
    
    async def add_connector(
        self,
        slide_index: int,
        connector_type: str,  # "straight", "elbow", "curved"
        start_x: float,
        start_y: float,
        end_x: float,
        end_y: float,
        line_color: Optional[List[int]] = None,
        line_width: Optional[float] = None,
        arrow_start: bool = False,
        arrow_end: bool = True
    ) -> Dict[str, Any]:
        """Add a connector line between points"""
        args = {
            "slide_index": slide_index,
            "connector_type": connector_type,
            "start_x": start_x,
            "start_y": start_y,
            "end_x": end_x,
            "end_y": end_y,
            "arrow_start": arrow_start,
            "arrow_end": arrow_end
        }
        if line_color: args["line_color"] = line_color
        if line_width is not None: args["line_width"] = line_width
        return await self.call_tool("add_connector", args)
    
    # ========== MASTER TOOLS (1 tool) ==========
    
    async def manage_slide_masters(
        self,
        action: str,  # "list", "apply", "modify", "create"
        master_index: Optional[int] = None,
        layout_index: Optional[int] = None,
        modifications: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Manage slide masters and layouts"""
        args = {"action": action}
        if master_index is not None: args["master_index"] = master_index
        if layout_index is not None: args["layout_index"] = layout_index
        if modifications: args["modifications"] = modifications
        return await self.call_tool("manage_slide_masters", args)
    
    # ========== TRANSITION TOOLS (1 tool) ==========
    
    async def manage_slide_transitions(
        self,
        action: str,  # "add", "remove", "list", "modify"
        slide_index: Optional[int] = None,  # None for all slides
        transition_type: Optional[str] = None,
        duration: Optional[float] = None,
        advance_on_click: bool = True,
        advance_after: Optional[float] = None
    ) -> Dict[str, Any]:
        """Manage slide transitions"""
        args = {
            "action": action,
            "advance_on_click": advance_on_click
        }
        if slide_index is not None: args["slide_index"] = slide_index
        if transition_type: args["transition_type"] = transition_type
        if duration is not None: args["duration"] = duration
        if advance_after is not None: args["advance_after"] = advance_after
        return await self.call_tool("manage_slide_transitions", args)
    
    # ========== UTILITY METHOD ==========
    
    async def call_any_tool(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """Call any MCP tool directly by name with keyword arguments"""
        return await self.call_tool(tool_name, kwargs)

# Create singleton instances
mcp_client = MCPPowerPointClient(MCPServerConfig(transport="http"))
mcp_stdio_client = MCPPowerPointClient(MCPServerConfig(transport="stdio"))