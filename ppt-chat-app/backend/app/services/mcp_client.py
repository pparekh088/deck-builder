"""
MCP Client Service for PowerPoint Server Integration
Provides a client interface to communicate with the Office-PowerPoint-MCP-Server
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
    transport: str = "stdio"  # "stdio" or "http"
    server_path: str = "/workspace/Office-PowerPoint-MCP-Server/ppt_mcp_server.py"
    http_port: int = 8000
    http_host: str = "localhost"

class MCPPowerPointClient:
    """Client for interacting with the Office-PowerPoint-MCP-Server"""
    
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
        # Create server parameters
        server_params = StdioServerParameters(
            command=sys.executable,
            args=[self.config.server_path]
        )
        
        # Create and initialize session
        async with stdio_client(server_params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                self.session = session
                await session.initialize()
                
                # Keep the session alive
                # Note: In production, you'd want to manage this differently
                logger.info("MCP stdio session initialized")
    
    async def _connect_http(self):
        """Connect to MCP server via HTTP"""
        # Start the MCP server in HTTP mode if not already running
        await self._start_http_server()
        
        # Create HTTP client
        self.http_client = httpx.AsyncClient(
            base_url=f"http://{self.config.http_host}:{self.config.http_port}",
            timeout=30.0
        )
        
        # Test connection
        response = await self.http_client.get("/health")
        if response.status_code != 200:
            raise ConnectionError("Failed to connect to MCP HTTP server")
    
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
        
        # Wait for server to start
        await asyncio.sleep(2)
        
        if self._server_process.poll() is not None:
            stdout, stderr = self._server_process.communicate()
            raise RuntimeError(f"MCP server failed to start: {stderr.decode()}")
    
    async def disconnect(self):
        """Disconnect from the MCP server"""
        try:
            if self.session:
                # Session cleanup handled by context manager
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
    
    # High-level PowerPoint operations
    
    async def create_presentation(self, template_path: Optional[str] = None) -> str:
        """Create a new PowerPoint presentation"""
        args = {}
        if template_path:
            args["template_path"] = template_path
        
        result = await self.call_tool("create_presentation", args)
        self.current_presentation_id = result.get("presentation_id")
        return self.current_presentation_id
    
    async def open_presentation(self, file_path: str) -> str:
        """Open an existing PowerPoint presentation"""
        result = await self.call_tool("open_presentation", {"file_path": file_path})
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
    
    async def add_slide(self, layout_index: int = 1, position: Optional[int] = None) -> Dict[str, Any]:
        """Add a new slide to the presentation"""
        args = {"layout_index": layout_index}
        if position is not None:
            args["position"] = position
        
        return await self.call_tool("add_slide", args)
    
    async def delete_slide(self, slide_index: int) -> Dict[str, Any]:
        """Delete a slide from the presentation"""
        return await self.call_tool("delete_slide", {"slide_index": slide_index})
    
    async def add_text_to_slide(
        self, 
        slide_index: int, 
        text: str,
        placeholder_index: int = 0,
        font_name: Optional[str] = None,
        font_size: Optional[int] = None,
        bold: bool = False,
        italic: bool = False,
        color: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """Add text to a slide"""
        args = {
            "slide_index": slide_index,
            "text": text,
            "placeholder_index": placeholder_index,
            "bold": bold,
            "italic": italic
        }
        
        if font_name:
            args["font_name"] = font_name
        if font_size:
            args["font_size"] = font_size
        if color:
            args["color"] = color
        
        return await self.call_tool("add_text_to_slide", args)
    
    async def add_bullet_points(
        self,
        slide_index: int,
        bullet_points: List[str],
        placeholder_index: int = 1
    ) -> Dict[str, Any]:
        """Add bullet points to a slide"""
        args = {
            "slide_index": slide_index,
            "bullet_points": bullet_points,
            "placeholder_index": placeholder_index
        }
        
        return await self.call_tool("add_bullet_points", args)
    
    async def update_slide_title(self, slide_index: int, title: str) -> Dict[str, Any]:
        """Update the title of a slide"""
        # Use add_text_to_slide with placeholder_index 0 (title placeholder)
        return await self.add_text_to_slide(slide_index, title, placeholder_index=0)
    
    async def get_slide_info(self, slide_index: int) -> Dict[str, Any]:
        """Get information about a specific slide"""
        return await self.call_tool("get_slide_info", {"slide_index": slide_index})
    
    async def list_slides(self) -> List[Dict[str, Any]]:
        """List all slides in the presentation"""
        result = await self.call_tool("list_slides", {})
        return result.get("slides", [])
    
    async def duplicate_slide(self, slide_index: int, position: Optional[int] = None) -> Dict[str, Any]:
        """Duplicate a slide"""
        args = {"slide_index": slide_index}
        if position is not None:
            args["position"] = position
        
        return await self.call_tool("duplicate_slide", args)
    
    async def apply_template(self, template_path: str) -> Dict[str, Any]:
        """Apply a template to the current presentation"""
        return await self.call_tool("apply_template", {"template_path": template_path})
    
    async def add_image(
        self,
        slide_index: int,
        image_path: str,
        left: float = 1.0,
        top: float = 1.0,
        width: Optional[float] = None,
        height: Optional[float] = None
    ) -> Dict[str, Any]:
        """Add an image to a slide"""
        args = {
            "slide_index": slide_index,
            "image_path": image_path,
            "left": left,
            "top": top
        }
        
        if width:
            args["width"] = width
        if height:
            args["height"] = height
        
        return await self.call_tool("add_image", args)
    
    async def add_table(
        self,
        slide_index: int,
        rows: int,
        cols: int,
        left: float = 1.0,
        top: float = 2.0,
        width: float = 8.0,
        height: float = 4.0,
        data: Optional[List[List[str]]] = None
    ) -> Dict[str, Any]:
        """Add a table to a slide"""
        args = {
            "slide_index": slide_index,
            "rows": rows,
            "cols": cols,
            "left": left,
            "top": top,
            "width": width,
            "height": height
        }
        
        if data:
            args["data"] = data
        
        return await self.call_tool("add_table", args)
    
    async def add_chart(
        self,
        slide_index: int,
        chart_type: str,
        chart_data: Dict[str, Any],
        left: float = 1.0,
        top: float = 2.0,
        width: float = 8.0,
        height: float = 4.5
    ) -> Dict[str, Any]:
        """Add a chart to a slide"""
        args = {
            "slide_index": slide_index,
            "chart_type": chart_type,
            "chart_data": chart_data,
            "left": left,
            "top": top,
            "width": width,
            "height": height
        }
        
        return await self.call_tool("add_chart", args)

# Singleton instance with HTTP transport for easier integration
mcp_client = MCPPowerPointClient(MCPServerConfig(transport="http"))

# Alternative stdio client for when needed
mcp_stdio_client = MCPPowerPointClient(MCPServerConfig(transport="stdio"))