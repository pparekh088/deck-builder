# E2E Frontend ↔ Backend Testing Suite

## 🎯 Overview

Complete end-to-end testing suite for the PowerPoint Chat Application with:
- ✅ WebSocket real-time updates
- ✅ Template upload and analysis
- ✅ AI-powered deck generation
- ✅ Preview and download functionality
- ✅ Feature flag testing
- ✅ Placements and render metrics validation

## 🚀 Quick Start

### 1. Run with Stub Provider (No API Keys Required)

```bash
# From repository root
./scripts/e2e_frontend.sh
```

This will:
1. Create `.env.e2e` from sample
2. Start Redis, Backend, and Frontend via Docker Compose
3. Run Playwright E2E tests
4. Generate test artifacts

### 2. Run with Real Azure OpenAI

```bash
# Edit .env.e2e with your credentials
vim .env.e2e

# Add your Azure OpenAI credentials:
AZURE_OPENAI_API_KEY=your-key-here
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-4o-mini
AZURE_OPENAI_API_VERSION=2024-02-15-preview

# Run tests
./scripts/e2e_frontend.sh
```

### 3. Run with Standard OpenAI

```bash
# Edit .env.e2e
vim .env.e2e

# Add your OpenAI API key:
OPENAI_API_KEY=sk-your-key-here

# Run tests
./scripts/e2e_frontend.sh
```

## 📁 Project Structure

```
ppt-chat-app/
├── .env.e2e.sample              # Environment configuration template
├── compose.e2e.yml              # Docker Compose for E2E stack
├── scripts/
│   └── e2e_frontend.sh         # Main E2E test runner
├── backend/
│   ├── Dockerfile              # Backend container
│   └── app/
│       └── services/
│           └── providers/      # LLM provider factory
│               ├── __init__.py # Provider selection logic
│               ├── azure_openai.py
│               ├── openai.py
│               └── stub.py    # Deterministic test provider
├── frontend/
│   ├── Dockerfile              # Frontend container
│   └── tests/
│       ├── e2e/
│       │   ├── playwright.config.ts
│       │   └── ppt.e2e.spec.ts # E2E test scenarios
│       └── fixtures/
│           ├── create_template.py
│           └── template_min.pptx # Test template
└── e2e-artifacts/              # Test results (generated)
```

## 🧪 Test Scenarios

### 1. Full Flow Test
- Upload template → Analyze → Generate → Preview → Download
- Validates WebSocket status updates
- Checks placements and render_metrics
- Verifies all safety_ok=true

### 2. Feature Flag Test
- Tests with solver disabled (`?solver=off`)
- Verifies legacy path still works
- Ensures backward compatibility

### 3. WebSocket Real-time Test
- Monitors WebSocket messages
- Validates message sequence
- Checks status progression

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `HYBRID_VISION_ENABLED` | Enable vision analysis | `true` |
| `ACCURATE_SOLVER_ENABLED` | Use ILP solver | `true` |
| `RENDER_MEASURE_ENABLED` | Enable 3-pass rendering | `true` |
| `ARCHETYPE_ALIGNMENT_ENABLED` | Detect layout archetypes | `true` |
| `SAFETY_MAP_ENABLED` | Avoid logo/footer areas | `true` |
| `E2E_HEADLESS` | Run tests in headless mode | `true` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |
| `VITE_API_BASE` | Frontend API base URL | `http://localhost:8000` |

### Provider Selection Logic

```python
if AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT:
    → Use Azure OpenAI
elif OPENAI_API_KEY:
    → Use Standard OpenAI
else:
    → Use Stub Provider (deterministic)
```

## 📊 Test Artifacts

After running tests, artifacts are saved in `./e2e-artifacts/`:
- Screenshots (on failure)
- Videos (on failure)
- Traces (on failure)
- Test results
- HTML report

View the HTML report:
```bash
npx playwright show-report e2e-artifacts/playwright-report
```

## 🐛 Debugging

### View Service Logs
```bash
# Keep services running after tests
KEEP_SERVICES=true ./scripts/e2e_frontend.sh

# View logs
docker compose -f compose.e2e.yml logs backend
docker compose -f compose.e2e.yml logs frontend
```

### Run Tests in Headed Mode
```bash
# Edit .env.e2e
E2E_HEADLESS=false

# Run tests
./scripts/e2e_frontend.sh
```

### Manual Service Start
```bash
# Start services
docker compose -f compose.e2e.yml up -d

# Run tests manually
cd frontend
npx playwright test --config tests/e2e/playwright.config.ts --ui
```

## ✅ Acceptance Criteria

All the following criteria are met:

- ✅ **Frontend boots and can upload a template**
- ✅ **WebSocket statuses appear in order** (Planning → Composing → Validating)
- ✅ **At least 3 thumbnails visible** for the test deck
- ✅ **Download produces a .pptx file**
- ✅ **Backend /api/preview/{session_id}** returns placements and render_metrics
- ✅ **All safety_ok=true** in placements
- ✅ **With solver off**, generation still succeeds (legacy path)
- ✅ **All Playwright tests pass** in headless mode
- ✅ **Tests work without API keys** using StubLLM provider

## 🎉 Success Indicators

When everything is working correctly:
1. All tests pass (green checkmarks)
2. Test artifacts are generated
3. Downloaded PPTX files are valid
4. WebSocket messages flow correctly
5. Feature flags control behavior as expected

## 📝 Notes

- The stub provider returns deterministic responses for consistent testing
- LibreOffice is included in the backend Docker image for PDF conversion
- Tests automatically retry on failure in CI mode
- The system gracefully degrades when features are disabled