#!/bin/bash

# PowerPoint AI Generator - Startup Script

echo "🚀 Starting PowerPoint AI Generator..."
echo ""

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

# Check prerequisites
echo "📋 Checking prerequisites..."

if ! command_exists python3 && ! command_exists python; then
    echo "❌ Python is not installed. Please install Python 3.9+"
    exit 1
fi

if ! command_exists node; then
    echo "❌ Node.js is not installed. Please install Node.js 16+"
    exit 1
fi

if ! command_exists npm; then
    echo "❌ npm is not installed. Please install npm"
    exit 1
fi

echo "✅ Prerequisites check passed"
echo ""

# Backend setup
echo "🔧 Setting up backend..."
cd backend

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    $PYTHON_CMD -m venv venv
fi

# Activate virtual environment and install dependencies
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
    source venv/Scripts/activate
else
    source venv/bin/activate
fi

# Install backend dependencies
echo "Installing backend dependencies..."
pip install -q -r requirements.txt

# Check for .env file
if [ ! -f ".env" ]; then
    echo "⚠️  No .env file found. Creating from .env.example..."
    cp .env.example .env
    echo "📝 Please edit backend/.env with your Azure OpenAI credentials"
fi

# Start backend in background
echo "Starting backend server..."
python -m uvicorn app.main:app --reload --port 8000 &
BACKEND_PID=$!
echo "Backend started with PID: $BACKEND_PID"

cd ..

# Frontend setup
echo ""
echo "🎨 Setting up frontend..."
cd frontend

# Install frontend dependencies if node_modules doesn't exist
if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install
fi

# Start frontend
echo "Starting frontend server..."
npm run dev &
FRONTEND_PID=$!
echo "Frontend started with PID: $FRONTEND_PID"

cd ..

# Wait for services to start
echo ""
echo "⏳ Waiting for services to start..."
sleep 5

# Display access information
echo ""
echo "✨ PowerPoint AI Generator is running!"
echo ""
echo "🌐 Access the application at: http://localhost:5173"
echo "📚 API documentation at: http://localhost:8000/docs"
echo ""
echo "📋 Process IDs:"
echo "   Backend:  $BACKEND_PID"
echo "   Frontend: $FRONTEND_PID"
echo ""
echo "To stop the application, press Ctrl+C"
echo ""

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "🛑 Stopping services..."
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    echo "Services stopped"
    exit 0
}

# Set up trap to cleanup on script exit
trap cleanup INT TERM

# Keep script running
while true; do
    sleep 1
done