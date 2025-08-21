# Port Configuration Update

## 🔄 Port Changes Summary

All services have been updated to use new ports to avoid conflicts:

| Service | Old Port | New Port | Status |
|---------|----------|----------|--------|
| MCP PowerPoint Server | 8000 | **8005** | ✅ Updated |
| Backend API (FastAPI) | 8001 | **8006** | ✅ Updated |
| Frontend (Vue.js) | 5174 | **5155** | ✅ Updated |

## 📁 Files Updated

### Core Configuration Files
- ✅ `/backend/app/services/mcp.py` - MCP client port configuration
- ✅ `/frontend/vite.config.js` - Frontend dev server port
- ✅ `/frontend/src/services/api.js` - API base URL
- ✅ `/frontend/src/services/websocket.js` - WebSocket URL

### Startup Scripts
- ✅ `/start.sh` - Linux/Mac startup script
- ✅ `/start.bat` - Windows startup script
- ✅ `/backend/start_mcp_server.sh` - MCP server startup script

### Docker Configuration
- ✅ `/backend/Dockerfile` - Backend container port
- ✅ `/frontend/Dockerfile` - Frontend container port
- ✅ `/compose.e2e.yml` - Docker Compose ports

### Test Configuration
- ✅ `/backend/tests/accuracy/utils.py` - Test API client
- ✅ `/backend/app/cli/validate_accuracy.py` - CLI validation
- ✅ `/frontend/tests/e2e/playwright.config.ts` - E2E test config
- ✅ `/scripts/e2e_frontend.sh` - E2E frontend script

### Documentation
- ✅ `/README.md` - Main documentation
- ✅ `/STARTUP_WITH_MCP.md` - MCP startup guide
- ✅ `/END_TO_END_FLOW.md` - Flow documentation

## 🚀 Quick Start with New Ports

### Option 1: Single Command Startup
```bash
# Linux/Mac
./start.sh

# Windows
start.bat
```

This will automatically start:
- MCP Server on port **8005**
- Backend API on port **8006**
- Frontend on port **5155**

### Option 2: Manual Startup

#### Terminal 1 - MCP Server:
```bash
cd /workspace/Office-PowerPoint-MCP-Server
python ppt_mcp_server.py --transport http --port 8005
```

#### Terminal 2 - Backend:
```bash
cd /workspace/ppt-chat-app/backend
source venv/bin/activate  # or venv\Scripts\activate on Windows
uvicorn app.main:app --reload --port 8006
```

#### Terminal 3 - Frontend:
```bash
cd /workspace/ppt-chat-app/frontend
npm run dev
```

## 🌐 Access URLs

| Service | URL |
|---------|-----|
| **Application** | http://localhost:5155 |
| **API Documentation** | http://localhost:8006/docs |
| **Health Check** | http://localhost:8006/health |
| **MCP Server** | http://localhost:8005 |

## 🔧 Environment Variables

If you need to override the default ports, you can set these environment variables:

### Frontend (.env)
```env
VITE_API_URL=http://localhost:8006
VITE_WS_URL=ws://localhost:8006
```

### Backend
The MCP client in `/backend/app/services/mcp.py` is configured to use port 8005:
```python
class MCPConfig:
    http_port: int = 8005
```

## 🐳 Docker Configuration

### Docker Run Commands
```bash
# MCP Server (if containerized)
docker run -p 8005:8005 mcp-server

# Backend
docker run -p 8006:8006 backend

# Frontend
docker run -p 5155:5155 frontend
```

### Docker Compose
```yaml
services:
  mcp-server:
    ports: ["8005:8005"]
  
  backend:
    ports: ["8006:8006"]
    
  frontend:
    ports: ["5155:5155"]
```

## ⚠️ Important Notes

1. **Port Availability**: Ensure ports 8005, 8006, and 5155 are not in use by other applications
2. **Firewall**: If running remotely, ensure these ports are open in your firewall
3. **MCP Connection**: The backend automatically connects to MCP server on port 8005
4. **API Proxy**: Frontend dev server proxies `/api` requests to backend on port 8006

## 🔍 Verification

To verify all services are running on correct ports:

```bash
# Check MCP Server
curl http://localhost:8005/health

# Check Backend API
curl http://localhost:8006/health

# Check Frontend
curl http://localhost:5155
```

## 🛠️ Troubleshooting

### Port Already in Use
If you get a "port already in use" error:
```bash
# Find process using port (Linux/Mac)
lsof -i :8005  # or 8006, 5155

# Find process using port (Windows)
netstat -ano | findstr :8005
```

### Connection Refused
- Ensure MCP server is started before backend
- Check logs in `backend/mcp_server.log`
- Verify firewall settings

### Frontend Can't Connect to Backend
- Check VITE_API_URL is set to http://localhost:8006
- Ensure backend is running on port 8006
- Check browser console for CORS errors

## ✅ Summary

All port references have been successfully updated throughout the codebase:
- **8000 → 8005** (MCP Server)
- **8001 → 8006** (Backend API)
- **5174 → 5155** (Frontend)

The system is fully configured to work with the new ports!