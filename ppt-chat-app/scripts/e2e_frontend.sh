#!/usr/bin/env bash
set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}   E2E Frontend Testing Suite${NC}"
echo -e "${GREEN}========================================${NC}"

# 0) Setup environment
echo -e "\n${YELLOW}Step 1: Setting up environment...${NC}"
cp -n .env.e2e.sample .env.e2e 2>/dev/null || true

# Check if .env.e2e exists
if [ ! -f .env.e2e ]; then
    echo -e "${YELLOW}Creating .env.e2e from sample...${NC}"
    cp .env.e2e.sample .env.e2e
fi

# Source the environment file
export $(cat .env.e2e | grep -v '^#' | xargs)

# 1) Create test fixture if needed
echo -e "\n${YELLOW}Step 2: Creating test fixtures...${NC}"
if [ ! -f frontend/tests/fixtures/template_min.pptx ]; then
    echo "Creating minimal test template..."
    cd frontend/tests/fixtures
    python3 create_template.py || {
        echo -e "${YELLOW}Python template creation failed, using fallback...${NC}"
        # Create a simple binary file as fallback
        echo "PK" > template_min.pptx
    }
    cd ../../..
fi

# 2) Start the stack
echo -e "\n${YELLOW}Step 3: Starting Docker services...${NC}"
docker compose -f compose.e2e.yml down 2>/dev/null || true
docker compose -f compose.e2e.yml up -d --build

# Wait for services
echo -e "\n${YELLOW}Step 4: Waiting for services to be ready...${NC}"
echo -n "Waiting for backend..."
attempts=0
max_attempts=60
until curl -sf http://localhost:8000/api/health >/dev/null 2>&1 || curl -sf http://localhost:8000/docs >/dev/null 2>&1; do
    sleep 1
    echo -n "."
    attempts=$((attempts + 1))
    if [ $attempts -ge $max_attempts ]; then
        echo -e "\n${RED}Backend failed to start after ${max_attempts} seconds${NC}"
        docker compose -f compose.e2e.yml logs backend
        exit 1
    fi
done
echo -e " ${GREEN}Ready!${NC}"

echo -n "Waiting for frontend..."
attempts=0
until curl -sf http://localhost:5155 >/dev/null 2>&1; do
    sleep 1
    echo -n "."
    attempts=$((attempts + 1))
    if [ $attempts -ge $max_attempts ]; then
        echo -e "\n${RED}Frontend failed to start after ${max_attempts} seconds${NC}"
        docker compose -f compose.e2e.yml logs frontend
        exit 1
    fi
done
echo -e " ${GREEN}Ready!${NC}"

# 3) Run Playwright tests
echo -e "\n${YELLOW}Step 5: Running Playwright E2E tests...${NC}"
cd frontend

# Install dependencies if needed
if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm ci
fi

# Install Playwright browsers if needed
if [ ! -d "$HOME/.cache/ms-playwright" ]; then
    echo "Installing Playwright browsers..."
    npx playwright install --with-deps chromium
fi

# Run the tests
E2E_BASE_URL=${E2E_BASE_URL:-http://localhost:5155} \
E2E_HEADLESS=${E2E_HEADLESS:-true} \
npx playwright test --config tests/e2e/playwright.config.ts --reporter=list || TEST_FAILED=1

cd ..

# 4) Collect artifacts
echo -e "\n${YELLOW}Step 6: Collecting test artifacts...${NC}"
mkdir -p e2e-artifacts
if [ -d frontend/test-results ]; then
    cp -r frontend/test-results e2e-artifacts/ 2>/dev/null || true
fi
if [ -d frontend/playwright-report ]; then
    cp -r frontend/playwright-report e2e-artifacts/ 2>/dev/null || true
fi

# 5) Show logs if tests failed
if [ "${TEST_FAILED:-0}" = "1" ]; then
    echo -e "\n${RED}Tests failed! Showing service logs...${NC}"
    echo -e "\n${YELLOW}Backend logs:${NC}"
    docker compose -f compose.e2e.yml logs --tail=50 backend
    echo -e "\n${YELLOW}Frontend logs:${NC}"
    docker compose -f compose.e2e.yml logs --tail=50 frontend
fi

# 6) Cleanup (optional)
if [ "${KEEP_SERVICES:-false}" != "true" ]; then
    echo -e "\n${YELLOW}Step 7: Cleaning up services...${NC}"
    docker compose -f compose.e2e.yml down
fi

# Final status
if [ "${TEST_FAILED:-0}" = "1" ]; then
    echo -e "\n${RED}========================================${NC}"
    echo -e "${RED}   E2E Tests Failed${NC}"
    echo -e "${RED}========================================${NC}"
    echo -e "Artifacts saved in ./e2e-artifacts"
    echo -e "To view the HTML report: ${YELLOW}npx playwright show-report e2e-artifacts/playwright-report${NC}"
    exit 1
else
    echo -e "\n${GREEN}========================================${NC}"
    echo -e "${GREEN}   E2E Tests Passed! ✅${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo -e "Artifacts saved in ./e2e-artifacts"
fi