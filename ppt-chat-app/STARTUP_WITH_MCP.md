# Integrated MCP Server Startup

## 🚀 Complete System Startup with MCP Server

The startup scripts (`start.sh` for Linux/Mac and `start.bat` for Windows) now **automatically start the MCP PowerPoint Server** along with the backend and frontend services.

## What Happens When You Run `./start.sh` or `start.bat`

### 1. Prerequisites Check
- Python 3.9+
- Node.js 16+
- npm

### 2. MCP Server Setup & Launch (NEW!)
```bash
# Automatically handled:
✅ Checks if Office-PowerPoint-MCP-Server exists
✅ Clones from GitHub if needed
✅ Installs fastmcp and python-pptx dependencies
✅ Sets PPT_TEMPLATE_PATH environment variable
✅ Starts MCP server on port 8000
✅ Waits for server to be ready
```

### 3. Backend Server Launch
```bash
✅ Creates/activates virtual environment
✅ Installs backend dependencies
✅ Configures .env if needed
✅ Starts FastAPI on port 8001
✅ Connects to MCP server automatically
```

### 4. Frontend Server Launch
```bash
✅ Installs npm dependencies
✅ Starts Vue.js dev server on port 5174
```

## 📋 Service Architecture

```
┌─────────────────────────────────────────┐
│           User Browser                   │
│         http://localhost:5174            │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│         Frontend (Vue.js)                │
│            Port: 5174                    │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│        Backend (FastAPI)                 │
│           Port: 8001                     │
│     • API endpoints                      │
│     • MCP client integration             │
│     • OpenAI integration                 │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│      MCP PowerPoint Server               │
│           Port: 8000                     │
│     • 33 PowerPoint tools                │
│     • python-pptx operations             │
│     • AI-powered generation              │
└─────────────────────────────────────────┘
```

## 🎯 Single Command Startup

### Linux/Mac:
```bash
cd /workspace/ppt-chat-app
./start.sh
```

### Windows:
```cmd
cd \workspace\ppt-chat-app
start.bat
```

## 📊 What You'll See

```
🚀 Starting PowerPoint AI Generator...

📋 Checking prerequisites...
✅ Prerequisites check passed

🔌 Starting MCP PowerPoint Server...
Starting MCP server on port 8000...
MCP Server started with PID: 12345
✅ MCP Server is running

🔧 Setting up backend...
Starting backend server...
Backend started with PID: 12346
✅ Backend is running

🎨 Setting up frontend...
Starting frontend server...
Frontend started with PID: 12347
✅ Frontend is running

🔍 Checking system health...
✅ System is healthy

✨ PowerPoint AI Generator is running!

🌐 Access the application at: http://localhost:5174
📚 API documentation at: http://localhost:8001/docs
🏥 Health status at: http://localhost:8001/health
🔌 MCP Server running at: http://localhost:8000

📋 Process IDs:
   MCP Server: 12345
   Backend:    12346
   Frontend:   12347

📝 Logs:
   MCP Server: backend/mcp_server.log
   Backend:    backend/backend.log
   Frontend:   frontend/frontend.log

To stop the application, press Ctrl+C
```

## 🛑 Stopping Everything

Press `Ctrl+C` and all three services will be stopped automatically:
- MCP Server
- Backend Server
- Frontend Server

## 🔧 Manual Control (if needed)

If you prefer to start services individually:

### Terminal 1 - MCP Server:
```bash
cd /workspace/Office-PowerPoint-MCP-Server
python ppt_mcp_server.py --transport http --port 8000
```

### Terminal 2 - Backend:
```bash
cd /workspace/ppt-chat-app/backend
source venv/bin/activate  # or venv\Scripts\activate on Windows
uvicorn app.main:app --reload --port 8001
```

### Terminal 3 - Frontend:
```bash
cd /workspace/ppt-chat-app/frontend
npm run dev
```

## 🐛 Troubleshooting

### MCP Server Issues
- Check `backend/mcp_server.log` for errors
- Ensure port 8000 is not in use
- Verify python-pptx and fastmcp are installed

### Connection Issues
- Backend automatically connects to MCP on startup
- Check `backend/backend.log` for connection errors
- Verify MCP server is running on port 8000

### Port Conflicts
- MCP Server: 8000
- Backend API: 8001  
- Frontend: 5174

Change ports in start scripts if needed.

## ✅ Benefits of Integrated Startup

1. **One Command**: Start everything with `./start.sh`
2. **Automatic Dependencies**: MCP server deps installed automatically
3. **Health Checks**: Verifies all services are running
4. **Clean Shutdown**: Ctrl+C stops all services
5. **Unified Logging**: All logs in one place
6. **No Manual Steps**: MCP server starts automatically

## 🎉 Result

With this integrated startup, you get:
- ✅ Full MCP server with 33 PowerPoint tools
- ✅ Clean architecture without redundant service layers
- ✅ Automatic connection management
- ✅ Professional PowerPoint generation
- ✅ AI-powered content creation
- ✅ Template support
- ✅ Everything working end-to-end!