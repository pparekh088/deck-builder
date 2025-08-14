# PowerPoint AI Generator

A full-stack web application that enables users to generate PowerPoint presentations through AI-powered chat interactions. Upload a custom template and chat with Azure OpenAI GPT-4.1 to create professional presentations in real-time.

## Features

- 🤖 **AI-Powered Content Generation**: Leverage Azure OpenAI GPT-4.1 to generate presentation content
- 📁 **Custom Template Support**: Upload your own PowerPoint templates (.pptx) for consistent branding
- 💬 **Interactive Chat Interface**: Natural conversation flow for creating and refining presentations
- 🔄 **Real-time Updates**: WebSocket integration for live preview updates as you chat
- 👁️ **Live Preview Panel**: See your presentation take shape with each message
- 📥 **Instant Download**: Download your completed presentation at any time
- 🎨 **Modern UI**: Beautiful, responsive interface built with Vue 3 and Tailwind CSS

## Tech Stack

### Frontend
- **Vue 3**: Progressive JavaScript framework
- **Pinia**: State management
- **Tailwind CSS**: Utility-first CSS framework
- **Axios**: HTTP client
- **Socket.io Client**: WebSocket communication
- **Heroicons**: Beautiful hand-crafted SVG icons

### Backend
- **FastAPI**: Modern Python web framework
- **Azure OpenAI SDK**: GPT-4.1 integration
- **python-pptx**: PowerPoint generation
- **WebSockets**: Real-time communication
- **Redis**: Session management (optional)
- **Pydantic**: Data validation

## Prerequisites

- Python 3.9+
- Node.js 16+
- Azure OpenAI API access
- Redis (optional, for production - supports authentication)

## Installation

### Quick Start (Recommended)

The easiest way to get started is using the automated startup scripts:

#### Linux/macOS:
```bash
chmod +x start.sh
./start.sh
```

#### Windows:
```cmd
start.bat
```

**The startup scripts will:**
- ✅ Check all prerequisites (Python, Node.js, npm)
- ✅ Create and activate virtual environments
- ✅ Install all dependencies automatically
- ✅ Create `.env` file and guide you through configuration
- ✅ Prompt for Azure OpenAI credentials
- ✅ Generate secure secret keys
- ✅ Start both backend and frontend servers
- ✅ Monitor service health
- ✅ Display logs if errors occur
- ✅ Provide colored output for better readability

### Manual Setup (Alternative)

If you prefer manual setup or the scripts don't work for your environment:

1. Navigate to the backend directory:
```bash
cd backend
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file based on `.env.example`:
```bash
cp .env.example .env
```

5. Configure your Azure OpenAI credentials in `.env`:
```env
AZURE_OPENAI_API_KEY=your_api_key_here
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4-turbo
AZURE_OPENAI_API_VERSION=2024-02-01
```

6. Configure Redis (optional):
```env
# For local Redis without authentication
REDIS_URL=redis://localhost:6379
REDIS_PASSWORD=
REDIS_DB=0

# For Redis with authentication
REDIS_URL=redis://localhost:6379
REDIS_PASSWORD=your_secure_password
REDIS_DB=0

# For Redis Cloud or remote Redis
REDIS_URL=redis://redis-server.example.com:6379
REDIS_PASSWORD=your_secure_password
REDIS_DB=0
```

**Note**: If Redis is not available or misconfigured, the application will automatically fall back to in-memory session storage.

### Frontend Setup

1. Navigate to the frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

3. Configure API endpoint (optional):
Create a `.env` file if you need to change the default API URL:
```env
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000
```

## Running the Application

### Start the Backend

```bash
cd backend
python -m uvicorn app.main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`
API documentation: `http://localhost:8000/docs`

### Start the Frontend

```bash
cd frontend
npm run dev
```

The application will be available at `http://localhost:5173`

## Usage Guide

### 1. Starting a Session

When you open the application, a new session is automatically created. You'll see your session ID in the header.

### 2. Uploading a Template

- Click the "Upload PowerPoint template" area in the chat interface
- Select your `.pptx` template file
- The template will be used for all subsequent presentation generation

### 3. Creating Your Presentation

Start chatting with the AI to create your presentation:

**Example prompts:**
- "Create a presentation about artificial intelligence with 5 slides"
- "Add a slide about machine learning applications"
- "Make the title slide more engaging"
- "Add bullet points about the benefits of AI in healthcare"

### 4. Preview and Download

- The preview panel shows your slides in real-time
- Click on any slide to view details
- Use the "Download" button to save your presentation

## API Endpoints

### Session Management
- `POST /api/session/create` - Create a new session
- `GET /api/session/{session_id}` - Get session information
- `DELETE /api/session/{session_id}` - Delete a session

### Template Management
- `POST /api/template/upload` - Upload a PowerPoint template

### Chat & Generation
- `POST /api/chat` - Send a chat message and generate content
- `GET /api/preview/{session_id}` - Get presentation preview
- `GET /api/download/{session_id}` - Download the presentation

### WebSocket
- `WS /ws/{session_id}` - Real-time updates

## Project Structure

```
ppt-chat-app/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI application
│   │   ├── config.py            # Configuration settings
│   │   ├── models.py            # Pydantic models
│   │   └── services/
│   │       ├── openai_service.py    # Azure OpenAI integration
│   │       ├── ppt_service.py       # PowerPoint generation
│   │       └── session_service.py   # Session management
│   ├── uploads/                 # Generated presentations
│   ├── templates/               # Uploaded templates
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── ChatInterface.vue    # Chat UI component
│   │   │   └── PreviewPanel.vue     # Preview component
│   │   ├── services/
│   │   │   ├── api.js              # API client
│   │   │   └── websocket.js        # WebSocket client
│   │   ├── stores/
│   │   │   └── chat.js             # Pinia store
│   │   ├── App.vue                 # Main component
│   │   └── main.js                 # Application entry
│   └── package.json
│
└── README.md
```

## Configuration

### Backend Configuration

Key settings in `.env`:

- `AZURE_OPENAI_API_KEY`: Your Azure OpenAI API key
- `AZURE_OPENAI_ENDPOINT`: Azure OpenAI endpoint URL
- `AZURE_OPENAI_DEPLOYMENT_NAME`: Model deployment name
- `SECRET_KEY`: JWT secret for session management
- `REDIS_URL`: Redis connection URL (optional)
- `REDIS_PASSWORD`: Redis authentication password (optional)
- `REDIS_DB`: Redis database number (default: 0)
- `MAX_FILE_SIZE`: Maximum template file size (bytes)

### Frontend Configuration

Environment variables in `.env`:

- `VITE_API_URL`: Backend API URL
- `VITE_WS_URL`: WebSocket URL

## Redis Setup (Optional but Recommended for Production)

### Local Redis with Password

1. Install Redis:
```bash
# Ubuntu/Debian
sudo apt-get install redis-server

# macOS
brew install redis

# Docker
docker run -d -p 6379:6379 --name redis redis:alpine --requirepass your_password
```

2. Configure Redis password:
```bash
# Edit redis.conf
requirepass your_secure_password
```

3. Update `.env`:
```env
REDIS_URL=redis://localhost:6379
REDIS_PASSWORD=your_secure_password
```

### Redis Cloud Setup

1. Create account at [Redis Cloud](https://redis.com/try-free/)
2. Create a database
3. Copy connection details to `.env`:
```env
REDIS_URL=redis://redis-12345.c1.us-east-1-2.ec2.cloud.redislabs.com:12345
REDIS_PASSWORD=your_redis_cloud_password
```

### Testing Redis Connection

Check Redis connection status via the health endpoint:
```bash
curl http://localhost:8000/health
```

Response will show Redis status:
```json
{
  "status": "healthy",
  "services": {
    "session_storage": {
      "status": "healthy",
      "storage": "redis",
      "redis_version": "7.0.5"
    }
  }
}
```

If Redis is unavailable:
```json
{
  "status": "degraded",
  "services": {
    "session_storage": {
      "status": "degraded",
      "storage": "in-memory",
      "warning": "Redis not available, using in-memory storage"
    }
  }
}
```

## Development

### Running Tests

Backend tests:
```bash
cd backend
pytest
```

Frontend tests:
```bash
cd frontend
npm run test
```

### Building for Production

Frontend build:
```bash
cd frontend
npm run build
```

Backend deployment:
```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Troubleshooting

### Common Issues

1. **WebSocket Connection Failed**
   - Ensure the backend is running
   - Check CORS settings in backend configuration
   - Verify WebSocket URL in frontend configuration

2. **Template Upload Failed**
   - Check file size limits
   - Ensure the file is a valid .pptx format
   - Verify upload directory permissions

3. **Azure OpenAI Errors**
   - Verify API credentials
   - Check deployment name and endpoint
   - Ensure sufficient API quota

### Debug Mode

Enable debug logging:

Backend:
```python
logging.basicConfig(level=logging.DEBUG)
```

Frontend:
```javascript
console.log('Debug mode enabled');
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

MIT License - see LICENSE file for details

## Support

For issues and questions:
- Create an issue on GitHub
- Check existing documentation
- Review API documentation at `/docs`

## Acknowledgments

- Azure OpenAI for GPT-4.1
- FastAPI community
- Vue.js ecosystem
- python-pptx library maintainers