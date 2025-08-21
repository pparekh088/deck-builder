#!/bin/bash

# Stop the Office-PowerPoint-MCP-Server

if [ -f /tmp/mcp_server.pid ]; then
    PID=$(cat /tmp/mcp_server.pid)
    echo "Stopping MCP Server with PID $PID..."
    kill $PID 2>/dev/null
    rm /tmp/mcp_server.pid
    echo "MCP Server stopped."
else
    echo "MCP Server PID file not found. Server may not be running."
fi