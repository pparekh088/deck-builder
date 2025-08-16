@echo off
setlocal enabledelayedexpansion

echo.
echo ===================================================
echo    PowerPoint AI Generator - Windows Startup
echo ===================================================
echo.

:: Check prerequisites
echo Checking prerequisites...

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.9+ from https://www.python.org
    pause
    exit /b 1
)

where node >nul 2>nul
if %errorlevel% neq 0 (
    echo ERROR: Node.js is not installed or not in PATH
    echo Please install Node.js 16+ from https://nodejs.org
    pause
    exit /b 1
)

where npm >nul 2>nul
if %errorlevel% neq 0 (
    echo ERROR: npm is not installed
    pause
    exit /b 1
)

echo Prerequisites check passed!
echo.

:: Backend setup
echo Setting up backend...
cd backend

:: Create virtual environment if it doesn't exist
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

:: Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

:: Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip >nul 2>&1

:: Install backend dependencies
if not exist ".deps_installed" (
    echo Installing backend dependencies (this may take a few minutes^)...
    pip install -r requirements.txt
    if %errorlevel% equ 0 (
        echo. > .deps_installed
        echo Backend dependencies installed successfully!
    ) else (
        echo ERROR: Failed to install backend dependencies
        pause
        exit /b 1
    )
) else (
    echo Backend dependencies already installed
)

:: Check for .env file
if not exist ".env" (
    echo.
    echo No .env file found. Creating from template...
    copy .env.example .env >nul
    echo.
    echo ===================================================
    echo    CONFIGURATION REQUIRED
    echo ===================================================
    echo.
    echo Would you like to configure Azure OpenAI settings now?
    set /p configure="Configure now? (y/n) [y]: "
    if "!configure!"=="" set configure=y
    
    if /i "!configure!"=="y" (
        echo.
        echo Azure OpenAI Configuration:
        echo ^(You can get these from your Azure Portal^)
        echo.
        
        set /p azure_key="Enter Azure OpenAI API Key: "
        set /p azure_endpoint="Enter Azure OpenAI Endpoint: "
        set /p azure_deployment="Enter Deployment Name [gpt-4-turbo]: "
        if "!azure_deployment!"=="" set azure_deployment=gpt-4-turbo
        
        echo.
        echo Redis Configuration (Optional - press Enter to skip^):
        set /p redis_url="Redis URL [redis://localhost:6379]: "
        if "!redis_url!"=="" set redis_url=redis://localhost:6379
        set /p redis_password="Redis Password (leave blank for no auth): "
        
        :: Generate secret key
        for /f "delims=" %%i in ('python -c "import secrets; print(secrets.token_hex(32))"') do set secret_key=%%i
        
        :: Update .env file using Python
        python -c "import re; content = open('.env', 'r').read(); content = re.sub(r'AZURE_OPENAI_API_KEY=.*', 'AZURE_OPENAI_API_KEY=!azure_key!', content); content = re.sub(r'AZURE_OPENAI_ENDPOINT=.*', 'AZURE_OPENAI_ENDPOINT=!azure_endpoint!', content); content = re.sub(r'AZURE_OPENAI_DEPLOYMENT_NAME=.*', 'AZURE_OPENAI_DEPLOYMENT_NAME=!azure_deployment!', content); content = re.sub(r'SECRET_KEY=.*', 'SECRET_KEY=!secret_key!', content); content = re.sub(r'REDIS_URL=.*', 'REDIS_URL=!redis_url!', content); content = re.sub(r'REDIS_PASSWORD=.*', 'REDIS_PASSWORD=!redis_password!', content); open('.env', 'w').write(content)"
        
        echo.
        echo Configuration saved to backend\.env
    ) else (
        echo.
        echo WARNING: Please edit backend\.env with your Azure OpenAI credentials
        echo The app will not work properly without configuration
        echo.
        pause
    )
) else (
    echo .env file found
)

:: Start backend
echo.
echo Starting backend server...
start /b cmd /c "python -m uvicorn app.main:app --reload --port 8000 > backend.log 2>&1"
echo Backend server started on port 8000

cd ..

:: Frontend setup
echo.
echo Setting up frontend...
cd frontend

:: Install frontend dependencies
if not exist "node_modules" (
    echo Installing frontend dependencies (this may take a few minutes^)...
    call npm install
    if %errorlevel% equ 0 (
        echo Frontend dependencies installed successfully!
    ) else (
        echo ERROR: Failed to install frontend dependencies
        pause
        exit /b 1
    )
) else (
    echo Frontend dependencies already installed
)

:: Start frontend
echo.
echo Starting frontend server...
start /b cmd /c "npm run dev > frontend.log 2>&1"
echo Frontend server started

cd ..

:: Wait for services
echo.
echo Waiting for services to start...
timeout /t 5 /nobreak >nul

:: Check if services are running
echo.
echo Checking service status...

curl -s http://localhost:8000/health >nul 2>&1
if %errorlevel% equ 0 (
    echo Backend: RUNNING
) else (
    echo Backend: NOT RESPONDING - Check backend\backend.log for errors
)

curl -s http://localhost:5173 >nul 2>&1
if %errorlevel% equ 0 (
    echo Frontend: RUNNING
) else (
    echo Frontend: NOT RESPONDING - Check frontend\frontend.log for errors
)

:: Display access information
echo.
echo ===================================================
echo    PowerPoint AI Generator is running!
echo ===================================================
echo.
echo Application URL: http://localhost:5173
echo API Documentation: http://localhost:8000/docs
echo Health Status: http://localhost:8000/health
echo.
echo Logs:
echo   Backend:  backend\backend.log
echo   Frontend: frontend\frontend.log
echo.
echo Press Ctrl+C to stop the application
echo.

:: Keep window open
:loop
timeout /t 5 /nobreak >nul
goto loop