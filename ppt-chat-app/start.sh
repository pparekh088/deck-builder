#!/bin/bash

# PowerPoint AI Generator - Startup Script

echo "🚀 Starting PowerPoint AI Generator..."
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if running on Windows
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
    PYTHON_CMD="python"
    ACTIVATE_CMD="venv/Scripts/activate"
else
    PYTHON_CMD="python3"
    ACTIVATE_CMD="venv/bin/activate"
fi

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to prompt user
prompt_user() {
    local prompt_text="$1"
    local var_name="$2"
    local default_value="$3"
    
    if [ -n "$default_value" ]; then
        read -p "$prompt_text [$default_value]: " user_input
        if [ -z "$user_input" ]; then
            eval "$var_name='$default_value'"
        else
            eval "$var_name='$user_input'"
        fi
    else
        read -p "$prompt_text: " user_input
        eval "$var_name='$user_input'"
    fi
}

# Check prerequisites
echo -e "${BLUE}📋 Checking prerequisites...${NC}"

if ! command_exists python3 && ! command_exists python; then
    echo -e "${RED}❌ Python is not installed. Please install Python 3.9+${NC}"
    exit 1
fi

if ! command_exists node; then
    echo -e "${RED}❌ Node.js is not installed. Please install Node.js 16+${NC}"
    exit 1
fi

if ! command_exists npm; then
    echo -e "${RED}❌ npm is not installed. Please install npm${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Prerequisites check passed${NC}"
echo ""

# Backend setup
echo -e "${BLUE}🔧 Setting up backend...${NC}"
cd backend

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    $PYTHON_CMD -m venv venv
fi

# Activate virtual environment and install dependencies
echo "Activating virtual environment..."
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
    source venv/Scripts/activate
else
    source venv/bin/activate
fi

# Install/upgrade pip first
echo "Upgrading pip..."
pip install --upgrade pip -q

# Install backend dependencies
if [ ! -f ".deps_installed" ] || [ "requirements.txt" -nt ".deps_installed" ]; then
    echo "Installing backend dependencies (this may take a few minutes)..."
    pip install -r requirements.txt
    if [ $? -eq 0 ]; then
        touch .deps_installed
        echo -e "${GREEN}✅ Backend dependencies installed${NC}"
    else
        echo -e "${RED}❌ Failed to install backend dependencies${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✅ Backend dependencies already installed${NC}"
fi

# Check for .env file and configure
if [ ! -f ".env" ]; then
    echo ""
    echo -e "${YELLOW}⚠️  No .env file found. Let's configure your environment...${NC}"
    echo ""
    
    # Create .env file with default template
    cat > .env << 'EOF'
# Azure OpenAI Configuration
AZURE_OPENAI_API_KEY=your_api_key_here
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4-turbo
AZURE_OPENAI_API_VERSION=2024-02-01

# Application Settings
SECRET_KEY=your-secret-key-here

# Redis Configuration (Optional - leave blank to use in-memory storage)
REDIS_URL=redis://localhost:6379
REDIS_PASSWORD=

# CORS Settings (Development)
CORS_ORIGINS=http://localhost:5174,http://localhost:3000

# File Upload Settings
MAX_FILE_SIZE=10485760
UPLOAD_DIR=uploads
TEMPLATES_DIR=templates
EOF
    
    # Check if user wants to configure now
    echo -e "${BLUE}Would you like to configure your Azure OpenAI settings now?${NC}"
    read -p "Configure now? (y/n) [y]: " configure_now
    configure_now=${configure_now:-y}
    
    if [[ "$configure_now" == "y" || "$configure_now" == "Y" ]]; then
        echo ""
        echo -e "${BLUE}Azure OpenAI Configuration:${NC}"
        echo "You can get these values from your Azure OpenAI resource in the Azure Portal"
        echo ""
        
        prompt_user "Enter your Azure OpenAI API Key" AZURE_API_KEY ""
        prompt_user "Enter your Azure OpenAI Endpoint (e.g., https://your-resource.openai.azure.com/)" AZURE_ENDPOINT ""
        prompt_user "Enter your deployment name" AZURE_DEPLOYMENT "gpt-4-turbo"
        prompt_user "Enter API version" API_VERSION "2024-02-01"
        
        echo ""
        echo -e "${BLUE}Redis Configuration (Optional):${NC}"
        echo "Leave blank to use in-memory storage (fine for development)"
        echo ""
        
        prompt_user "Redis URL" REDIS_URL "redis://localhost:6379"
        prompt_user "Redis Password (leave blank for no auth)" REDIS_PASSWORD ""
        
        # Generate a secure secret key
        SECRET_KEY=$($PYTHON_CMD -c 'import secrets; print(secrets.token_hex(32))')
        
        # Update .env file
        if [[ "$OSTYPE" == "darwin"* ]]; then
            # macOS
            sed -i '' "s|AZURE_OPENAI_API_KEY=.*|AZURE_OPENAI_API_KEY=$AZURE_API_KEY|" .env
            sed -i '' "s|AZURE_OPENAI_ENDPOINT=.*|AZURE_OPENAI_ENDPOINT=$AZURE_ENDPOINT|" .env
            sed -i '' "s|AZURE_OPENAI_DEPLOYMENT_NAME=.*|AZURE_OPENAI_DEPLOYMENT_NAME=$AZURE_DEPLOYMENT|" .env
            sed -i '' "s|AZURE_OPENAI_API_VERSION=.*|AZURE_OPENAI_API_VERSION=$API_VERSION|" .env
            sed -i '' "s|SECRET_KEY=.*|SECRET_KEY=$SECRET_KEY|" .env
            sed -i '' "s|REDIS_URL=.*|REDIS_URL=$REDIS_URL|" .env
            sed -i '' "s|REDIS_PASSWORD=.*|REDIS_PASSWORD=$REDIS_PASSWORD|" .env
        else
            # Linux/Windows
            sed -i "s|AZURE_OPENAI_API_KEY=.*|AZURE_OPENAI_API_KEY=$AZURE_API_KEY|" .env
            sed -i "s|AZURE_OPENAI_ENDPOINT=.*|AZURE_OPENAI_ENDPOINT=$AZURE_ENDPOINT|" .env
            sed -i "s|AZURE_OPENAI_DEPLOYMENT_NAME=.*|AZURE_OPENAI_DEPLOYMENT_NAME=$AZURE_DEPLOYMENT|" .env
            sed -i "s|AZURE_OPENAI_API_VERSION=.*|AZURE_OPENAI_API_VERSION=$API_VERSION|" .env
            sed -i "s|SECRET_KEY=.*|SECRET_KEY=$SECRET_KEY|" .env
            sed -i "s|REDIS_URL=.*|REDIS_URL=$REDIS_URL|" .env
            sed -i "s|REDIS_PASSWORD=.*|REDIS_PASSWORD=$REDIS_PASSWORD|" .env
        fi
        
        echo ""
        echo -e "${GREEN}✅ Configuration saved to backend/.env${NC}"
    else
        echo ""
        echo -e "${YELLOW}⚠️  Please edit backend/.env with your Azure OpenAI credentials before using the app${NC}"
        echo -e "${YELLOW}   You can edit it now in another terminal or stop this script with Ctrl+C${NC}"
        echo ""
        read -p "Press Enter to continue anyway (the app may not work properly)..."
    fi
else
    echo -e "${GREEN}✅ .env file found${NC}"
    
    # Check if Azure OpenAI is configured
    if grep -q "AZURE_OPENAI_API_KEY=your_api_key_here" .env; then
        echo -e "${YELLOW}⚠️  Azure OpenAI credentials not configured in .env${NC}"
        echo -e "${YELLOW}   The app will run but won't be able to generate content${NC}"
    fi
fi

# Start backend in background
echo ""
echo "Starting backend server..."
$PYTHON_CMD -m uvicorn app.main:app --reload --port 8001 > backend.log 2>&1 &
BACKEND_PID=$!
echo "Backend started with PID: $BACKEND_PID"

cd ..

# Frontend setup
echo ""
echo -e "${BLUE}🎨 Setting up frontend...${NC}"
cd frontend

# Install frontend dependencies if node_modules doesn't exist
if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies (this may take a few minutes)..."
    npm install
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Frontend dependencies installed${NC}"
    else
        echo -e "${RED}❌ Failed to install frontend dependencies${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✅ Frontend dependencies already installed${NC}"
fi

# Start frontend
echo "Starting frontend server..."
npm run dev > frontend.log 2>&1 &
FRONTEND_PID=$!
echo "Frontend started with PID: $FRONTEND_PID"

cd ..

# Wait for services to start
echo ""
echo -e "${BLUE}⏳ Waiting for services to start...${NC}"

# Check if backend is running
for i in {1..10}; do
    if curl -s http://localhost:8001/health > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Backend is running${NC}"
        break
    fi
    if [ $i -eq 10 ]; then
        echo -e "${RED}❌ Backend failed to start on port 8001. Check backend/backend.log for errors${NC}"
        echo "Last 20 lines of backend log:"
        tail -20 backend/backend.log
    else
        echo -n "."
        sleep 2
    fi
done

# Check if frontend is running
for i in {1..10}; do
    if curl -s http://localhost:5174 > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Frontend is running${NC}"
        break
    fi
    if [ $i -eq 10 ]; then
        echo -e "${RED}❌ Frontend failed to start on port 5174. Check frontend/frontend.log for errors${NC}"
        echo "Last 20 lines of frontend log:"
        tail -20 frontend/frontend.log
    else
        echo -n "."
        sleep 2
    fi
done

# Check health status
echo ""
echo -e "${BLUE}🔍 Checking system health...${NC}"
health_response=$(curl -s http://localhost:8001/health)
if [ $? -eq 0 ]; then
    health_status=$(echo $health_response | $PYTHON_CMD -c "import sys, json; data=json.load(sys.stdin); print(data.get('status', 'unknown'))" 2>/dev/null)
    
    if [[ "$health_status" == "healthy" ]]; then
        echo -e "${GREEN}✅ System is healthy${NC}"
    elif [[ "$health_status" == "degraded" ]]; then
        echo -e "${YELLOW}⚠️  System is running in degraded mode${NC}"
        echo "   - Redis might not be available (using in-memory storage)"
        echo "   - Check your Azure OpenAI configuration"
    else
        echo -e "${YELLOW}⚠️  Could not determine system health${NC}"
    fi
fi

# Display access information
echo ""
echo -e "${GREEN}✨ PowerPoint AI Generator is running!${NC}"
echo ""
echo -e "${BLUE}🌐 Access the application at:${NC} http://localhost:5174"
echo -e "${BLUE}📚 API documentation at:${NC} http://localhost:8001/docs"
echo -e "${BLUE}🏥 Health status at:${NC} http://localhost:8001/health"
echo ""
echo -e "${BLUE}📋 Process IDs:${NC}"
echo "   Backend:  $BACKEND_PID"
echo "   Frontend: $FRONTEND_PID"
echo ""
echo -e "${BLUE}📝 Logs:${NC}"
echo "   Backend:  backend/backend.log"
echo "   Frontend: frontend/frontend.log"
echo ""
echo -e "${YELLOW}To stop the application, press Ctrl+C${NC}"
echo ""

# Function to cleanup on exit
cleanup() {
    echo ""
    echo -e "${BLUE}🛑 Stopping services...${NC}"
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    
    # Wait a moment for processes to stop
    sleep 2
    
    # Force kill if still running
    kill -9 $BACKEND_PID 2>/dev/null
    kill -9 $FRONTEND_PID 2>/dev/null
    
    echo -e "${GREEN}Services stopped${NC}"
    exit 0
}

# Set up trap to cleanup on script exit
trap cleanup INT TERM EXIT

# Keep script running and show logs if there are errors
while true; do
    # Check if processes are still running
    if ! kill -0 $BACKEND_PID 2>/dev/null; then
        echo -e "${RED}❌ Backend process died unexpectedly${NC}"
        echo "Last 20 lines of backend log:"
        tail -20 backend/backend.log
        cleanup
    fi
    
    if ! kill -0 $FRONTEND_PID 2>/dev/null; then
        echo -e "${RED}❌ Frontend process died unexpectedly${NC}"
        echo "Last 20 lines of frontend log:"
        tail -20 frontend/frontend.log
        cleanup
    fi
    
    sleep 5
done