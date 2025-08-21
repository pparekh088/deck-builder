#!/bin/bash

# Start the Office-PowerPoint-MCP-Server
# This script starts the MCP server in HTTP mode for the backend to connect to

echo "Starting Office-PowerPoint-MCP-Server..."

# Set the template path environment variable (optional)
export PPT_TEMPLATE_PATH="/workspace/ppt-chat-app/backend/uploads/templates"

# Navigate to the MCP server directory
cd /workspace/Office-PowerPoint-MCP-Server

# Start the server in HTTP mode
python ppt_mcp_server.py --transport http --port 8000 &

# Save the PID for later shutdown
echo $! > /tmp/mcp_server.pid

echo "MCP Server started with PID $(cat /tmp/mcp_server.pid)"
echo "Server running on http://localhost:8000"