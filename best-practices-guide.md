# Best Practices Guide for Advanced PowerPoint AI Agent Development

## Table of Contents
1. [Architecture Best Practices](#architecture-best-practices)
2. [AI Integration Best Practices](#ai-integration-best-practices)
3. [Performance Optimization](#performance-optimization)
4. [Security Best Practices](#security-best-practices)
5. [Error Handling & Reliability](#error-handling--reliability)
6. [Testing Strategies](#testing-strategies)
7. [Deployment Best Practices](#deployment-best-practices)
8. [Monitoring & Observability](#monitoring--observability)
9. [User Experience Guidelines](#user-experience-guidelines)
10. [Maintenance & Updates](#maintenance--updates)

## Architecture Best Practices

### 1. Microservices Design
```python
# ✅ GOOD: Separated concerns
class PresentationService:
    def __init__(self):
        self.ai_service = AIService()
        self.template_service = TemplateService()
        self.media_service = MediaService()
    
    async def create(self, request):
        # Orchestrate services
        outline = await self.ai_service.generate_outline(request)
        template = await self.template_service.select(request)
        media = await self.media_service.process(outline)
        return await self.build(outline, template, media)

# ❌ BAD: Monolithic approach
class PowerPointAgent:
    def create_everything(self, request):
        # All logic in one place
        # Hard to maintain, test, and scale
```

### 2. Abstraction Layers
```python
# ✅ GOOD: Abstract backend implementation
class PowerPointBackend(ABC):
    @abstractmethod
    async def create_slide(self, content): pass

class COMBackend(PowerPointBackend):
    async def create_slide(self, content):
        # Windows-specific implementation
        
class CloudBackend(PowerPointBackend):
    async def create_slide(self, content):
        # Cloud API implementation

# Usage
backend = BackendFactory.create(platform.system())
```

### 3. Dependency Injection
```python
# ✅ GOOD: Configurable dependencies
class PresentationService:
    def __init__(
        self,
        ai_service: AIServiceInterface,
        storage: StorageInterface,
        cache: CacheInterface
    ):
        self.ai_service = ai_service
        self.storage = storage
        self.cache = cache

# ❌ BAD: Hard-coded dependencies
class PresentationService:
    def __init__(self):
        self.ai_service = OpenAIService()  # Hard to test/swap
        self.storage = S3Storage()
        self.cache = RedisCache()
```

## AI Integration Best Practices

### 1. Prompt Engineering
```python
# ✅ GOOD: Structured, versioned prompts
class PromptManager:
    PROMPTS = {
        "outline_v1": """
        Role: You are an expert presentation designer.
        
        Task: Create a presentation outline for "{topic}"
        
        Requirements:
        - {num_slides} slides
        - Style: {style}
        - Audience: {audience}
        
        Output Format:
        ```json
        {
            "slides": [
                {
                    "title": "...",
                    "bullet_points": [...],
                    "notes": "..."
                }
            ]
        }
        ```
        """,
        "outline_v2": "..."  # Improved version
    }
    
    def get_prompt(self, name: str, version: str = "v1"):
        return self.PROMPTS.get(f"{name}_{version}")

# ❌ BAD: Inline, unversioned prompts
async def generate_outline(topic):
    prompt = f"Create outline for {topic}"  # Too simple, no structure
```

### 2. Response Validation
```python
# ✅ GOOD: Validate and parse AI responses
class AIResponseValidator:
    def validate_outline(self, response: str) -> Dict:
        try:
            data = json.loads(response)
            
            # Validate structure
            assert "slides" in data
            assert isinstance(data["slides"], list)
            
            for slide in data["slides"]:
                assert "title" in slide
                assert "bullet_points" in slide
                assert isinstance(slide["bullet_points"], list)
            
            return data
            
        except (json.JSONDecodeError, AssertionError) as e:
            # Fallback to regex parsing or retry
            return self.fallback_parse(response)

# ❌ BAD: Trust AI output blindly
def parse_response(response):
    return json.loads(response)  # Will crash on malformed JSON
```

### 3. Rate Limiting & Retries
```python
# ✅ GOOD: Implement smart retries with backoff
from tenacity import retry, stop_after_attempt, wait_exponential

class AIService:
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        retry_error_callback=lambda retry_state: self.use_fallback()
    )
    async def generate_content(self, prompt: str):
        try:
            return await self.client.complete(prompt)
        except RateLimitError:
            await self.handle_rate_limit()
            raise
        except APIError as e:
            logger.error(f"API error: {e}")
            raise

    async def use_fallback(self):
        # Use cached responses or simpler model
        return await self.fallback_generator.generate()
```

### 4. Context Management
```python
# ✅ GOOD: Maintain conversation context
class ContextAwareAI:
    def __init__(self):
        self.context_store = {}
    
    async def generate_with_context(self, session_id: str, prompt: str):
        # Retrieve context
        context = self.context_store.get(session_id, [])
        
        # Build messages with context
        messages = [
            {"role": "system", "content": "You are a presentation expert."},
            *context,
            {"role": "user", "content": prompt}
        ]
        
        response = await self.client.chat.complete(messages)
        
        # Update context
        context.append({"role": "user", "content": prompt})
        context.append({"role": "assistant", "content": response})
        
        # Trim context if too long
        if len(context) > 10:
            context = context[-10:]
        
        self.context_store[session_id] = context
        
        return response
```

## Performance Optimization

### 1. Caching Strategy
```python
# ✅ GOOD: Multi-level caching
class CacheStrategy:
    def __init__(self):
        self.memory_cache = {}  # L1: In-memory
        self.redis_cache = Redis()  # L2: Redis
        self.disk_cache = DiskCache()  # L3: Disk
    
    async def get_or_generate(self, key: str, generator_func):
        # Check L1 cache
        if key in self.memory_cache:
            return self.memory_cache[key]
        
        # Check L2 cache
        redis_value = await self.redis_cache.get(key)
        if redis_value:
            self.memory_cache[key] = redis_value
            return redis_value
        
        # Check L3 cache
        disk_value = await self.disk_cache.get(key)
        if disk_value:
            await self.redis_cache.set(key, disk_value, ttl=3600)
            self.memory_cache[key] = disk_value
            return disk_value
        
        # Generate new value
        value = await generator_func()
        
        # Update all cache levels
        self.memory_cache[key] = value
        await self.redis_cache.set(key, value, ttl=3600)
        await self.disk_cache.set(key, value)
        
        return value
```

### 2. Parallel Processing
```python
# ✅ GOOD: Process slides in parallel
async def create_slides_parallel(slide_contents: List[SlideContent]):
    # Create tasks for parallel processing
    tasks = []
    for content in slide_contents:
        task = asyncio.create_task(process_slide(content))
        tasks.append(task)
    
    # Wait for all tasks with timeout
    results = await asyncio.wait_for(
        asyncio.gather(*tasks, return_exceptions=True),
        timeout=30.0
    )
    
    # Handle results
    processed_slides = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            # Use fallback for failed slides
            processed_slides.append(
                await create_simple_slide(slide_contents[i])
            )
        else:
            processed_slides.append(result)
    
    return processed_slides

# ❌ BAD: Sequential processing
async def create_slides_sequential(slide_contents):
    slides = []
    for content in slide_contents:
        slide = await process_slide(content)  # Slow!
        slides.append(slide)
    return slides
```

### 3. Resource Pooling
```python
# ✅ GOOD: Connection pooling
class ConnectionPool:
    def __init__(self, max_connections: int = 10):
        self.pool = asyncio.Queue(maxsize=max_connections)
        self.semaphore = asyncio.Semaphore(max_connections)
        
    async def acquire(self):
        async with self.semaphore:
            if self.pool.empty():
                return await self.create_connection()
            return await self.pool.get()
    
    async def release(self, conn):
        await self.pool.put(conn)
    
    async def create_connection(self):
        # Create new connection
        return await create_db_connection()

# Usage
pool = ConnectionPool()

async def query_database(query):
    conn = await pool.acquire()
    try:
        return await conn.execute(query)
    finally:
        await pool.release(conn)
```

### 4. Lazy Loading
```python
# ✅ GOOD: Load resources on demand
class LazyTemplateLoader:
    def __init__(self):
        self._templates = {}
        self._metadata = self.load_metadata()
    
    def load_metadata(self):
        # Load only metadata, not full templates
        return load_template_metadata()
    
    async def get_template(self, template_id: str):
        if template_id not in self._templates:
            # Load template only when needed
            self._templates[template_id] = await self.load_template(template_id)
        return self._templates[template_id]
    
    def list_templates(self):
        # Return metadata without loading templates
        return self._metadata
```

## Security Best Practices

### 1. Input Validation
```python
# ✅ GOOD: Comprehensive input validation
class InputValidator:
    @staticmethod
    def validate_presentation_request(request: Dict) -> Dict:
        # Sanitize topic
        topic = request.get('topic', '').strip()
        if not topic or len(topic) > 500:
            raise ValueError("Invalid topic")
        
        # Validate number of slides
        num_slides = request.get('num_slides', 10)
        if not isinstance(num_slides, int) or num_slides < 1 or num_slides > 100:
            raise ValueError("Invalid number of slides")
        
        # Sanitize user input to prevent injection
        topic = bleach.clean(topic, tags=[], strip=True)
        
        # Validate file uploads
        if 'template_file' in request:
            file = request['template_file']
            if not file.filename.endswith('.pptx'):
                raise ValueError("Invalid file type")
            if file.size > 50 * 1024 * 1024:  # 50MB limit
                raise ValueError("File too large")
        
        return {
            'topic': topic,
            'num_slides': num_slides,
            # ... other validated fields
        }
```

### 2. API Security
```python
# ✅ GOOD: Implement API security
from fastapi import Security, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

class SecurityHandler:
    security = HTTPBearer()
    
    def __init__(self, secret_key: str):
        self.secret_key = secret_key
    
    def verify_token(self, credentials: HTTPAuthorizationCredentials = Security(security)):
        token = credentials.credentials
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=["HS256"])
            return payload
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=403, detail="Invalid token")
    
    def rate_limit(self, user_id: str):
        # Implement rate limiting per user
        key = f"rate_limit:{user_id}"
        count = redis_client.incr(key)
        if count == 1:
            redis_client.expire(key, 60)  # Reset every minute
        if count > 10:  # Max 10 requests per minute
            raise HTTPException(status_code=429, detail="Rate limit exceeded")

# Usage
security = SecurityHandler(SECRET_KEY)

@app.post("/api/presentations")
async def create_presentation(
    request: PresentationRequest,
    user = Depends(security.verify_token)
):
    security.rate_limit(user['id'])
    # Process request
```

### 3. Data Privacy
```python
# ✅ GOOD: Handle sensitive data properly
class DataPrivacyHandler:
    @staticmethod
    def anonymize_logs(data: Dict) -> Dict:
        """Remove sensitive information from logs"""
        sensitive_fields = ['email', 'api_key', 'password', 'token']
        
        anonymized = data.copy()
        for field in sensitive_fields:
            if field in anonymized:
                anonymized[field] = "***REDACTED***"
        
        return anonymized
    
    @staticmethod
    def encrypt_storage(data: bytes, key: bytes) -> bytes:
        """Encrypt data before storage"""
        from cryptography.fernet import Fernet
        f = Fernet(key)
        return f.encrypt(data)
    
    @staticmethod
    def cleanup_temporary_files(session_id: str):
        """Clean up temporary files after processing"""
        temp_dir = Path(f"/tmp/presentations/{session_id}")
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)
```

## Error Handling & Reliability

### 1. Graceful Degradation
```python
# ✅ GOOD: Fallback mechanisms
class ResilientPresentationService:
    async def create_slide_with_image(self, content: SlideContent):
        try:
            # Try to generate AI image
            image = await self.generate_ai_image(content.image_prompt)
        except AIServiceError:
            try:
                # Fallback to stock image
                image = await self.find_stock_image(content.image_prompt)
            except StockImageError:
                # Fallback to placeholder
                image = self.create_placeholder_image()
        
        # Continue with slide creation
        return self.create_slide(content, image)
    
    async def generate_content(self, topic: str):
        try:
            # Try primary AI service
            return await self.primary_ai.generate(topic)
        except Exception:
            try:
                # Try secondary AI service
                return await self.secondary_ai.generate(topic)
            except Exception:
                # Use template-based generation
                return self.template_generator.generate(topic)
```

### 2. Circuit Breaker Pattern
```python
# ✅ GOOD: Prevent cascading failures
class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half-open
    
    async def call(self, func, *args, **kwargs):
        if self.state == "open":
            if time.time() - self.last_failure_time > self.timeout:
                self.state = "half-open"
            else:
                raise ServiceUnavailableError("Circuit breaker is open")
        
        try:
            result = await func(*args, **kwargs)
            if self.state == "half-open":
                self.state = "closed"
                self.failure_count = 0
            return result
        
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.failure_count >= self.failure_threshold:
                self.state = "open"
            
            raise e

# Usage
ai_circuit_breaker = CircuitBreaker()

async def get_ai_content(prompt):
    return await ai_circuit_breaker.call(ai_service.generate, prompt)
```

### 3. Comprehensive Error Handling
```python
# ✅ GOOD: Detailed error handling
class ErrorHandler:
    @staticmethod
    def handle_presentation_error(error: Exception, context: Dict) -> Dict:
        error_response = {
            "error_type": type(error).__name__,
            "message": str(error),
            "timestamp": datetime.now().isoformat(),
            "context": context
        }
        
        if isinstance(error, ValidationError):
            error_response["status_code"] = 400
            error_response["user_message"] = "Invalid input provided"
            error_response["details"] = error.errors()
        
        elif isinstance(error, AIServiceError):
            error_response["status_code"] = 503
            error_response["user_message"] = "AI service temporarily unavailable"
            error_response["retry_after"] = 60
        
        elif isinstance(error, TemplateNotFoundError):
            error_response["status_code"] = 404
            error_response["user_message"] = "Template not found"
            error_response["suggestions"] = get_similar_templates()
        
        else:
            error_response["status_code"] = 500
            error_response["user_message"] = "An unexpected error occurred"
            # Log full error for debugging
            logger.error(f"Unexpected error: {error}", exc_info=True)
        
        return error_response
```

## Testing Strategies

### 1. Unit Testing
```python
# ✅ GOOD: Comprehensive unit tests
import pytest
from unittest.mock import Mock, patch, AsyncMock

class TestAIContentGenerator:
    @pytest.fixture
    def generator(self):
        return AIContentGenerator(api_key="test_key")
    
    @pytest.mark.asyncio
    async def test_generate_outline_success(self, generator):
        # Mock AI response
        mock_response = {
            "slides": [
                {
                    "title": "Introduction",
                    "bullet_points": ["Point 1", "Point 2"],
                    "notes": "Speaker notes"
                }
            ]
        }
        
        with patch.object(generator.client, 'complete', new_callable=AsyncMock) as mock:
            mock.return_value = json.dumps(mock_response)
            
            result = await generator.generate_outline("Test Topic")
            
            assert len(result) == 1
            assert result[0].title == "Introduction"
            mock.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_generate_outline_retry_on_failure(self, generator):
        with patch.object(generator.client, 'complete', new_callable=AsyncMock) as mock:
            # First call fails, second succeeds
            mock.side_effect = [
                APIError("Service unavailable"),
                json.dumps({"slides": []})
            ]
            
            result = await generator.generate_outline("Test Topic")
            
            assert result is not None
            assert mock.call_count == 2
```

### 2. Integration Testing
```python
# ✅ GOOD: Test component integration
@pytest.mark.integration
class TestPresentationCreation:
    @pytest.fixture
    async def test_client(self):
        from httpx import AsyncClient
        async with AsyncClient(app=app, base_url="http://test") as client:
            yield client
    
    @pytest.mark.asyncio
    async def test_end_to_end_presentation_creation(self, test_client):
        # Create presentation request
        request = {
            "topic": "Test Presentation",
            "num_slides": 5,
            "style": "professional"
        }
        
        # Submit request
        response = await test_client.post("/api/presentations", json=request)
        assert response.status_code == 202
        
        presentation_id = response.json()["id"]
        
        # Poll for completion
        max_attempts = 30
        for _ in range(max_attempts):
            status_response = await test_client.get(f"/api/presentations/{presentation_id}")
            if status_response.json()["status"] == "completed":
                break
            await asyncio.sleep(1)
        
        # Download presentation
        download_response = await test_client.get(
            f"/api/presentations/{presentation_id}/download"
        )
        assert download_response.status_code == 200
        assert download_response.headers["content-type"] == "application/vnd.openxmlformats-officedocument.presentationml.presentation"
```

### 3. Load Testing
```python
# ✅ GOOD: Performance testing
import locust

class PresentationUser(locust.HttpUser):
    wait_time = locust.between(1, 3)
    
    @locust.task
    def create_presentation(self):
        response = self.client.post("/api/presentations", json={
            "topic": f"Load Test {random.randint(1, 1000)}",
            "num_slides": 10,
            "style": "professional"
        })
        
        if response.status_code == 202:
            presentation_id = response.json()["id"]
            
            # Poll for completion
            for _ in range(30):
                status = self.client.get(f"/api/presentations/{presentation_id}")
                if status.json().get("status") == "completed":
                    break
                time.sleep(1)
    
    @locust.task
    def get_templates(self):
        self.client.get("/api/templates")
```

## Deployment Best Practices

### 1. Container Optimization
```dockerfile
# ✅ GOOD: Multi-stage build for smaller images
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Runtime stage
FROM python:3.11-slim

WORKDIR /app

# Copy Python packages from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Copy application
COPY . .

# Non-root user
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 2. Environment Configuration
```python
# ✅ GOOD: Environment-based configuration
from pydantic import BaseSettings

class Settings(BaseSettings):
    # API Configuration
    api_key: str
    api_version: str = "v1"
    
    # Database
    database_url: str
    database_pool_size: int = 20
    
    # Redis
    redis_url: str
    redis_ttl: int = 3600
    
    # Service URLs
    ai_service_url: str
    template_service_url: str
    
    # Performance
    max_workers: int = 10
    request_timeout: int = 30
    
    # Security
    secret_key: str
    cors_origins: list = ["*"]
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()

# Usage
app = FastAPI(title="PowerPoint AI", version=settings.api_version)
```

### 3. Graceful Shutdown
```python
# ✅ GOOD: Handle shutdown gracefully
import signal
import asyncio

class GracefulShutdown:
    def __init__(self):
        self.shutdown_event = asyncio.Event()
        signal.signal(signal.SIGTERM, self.handle_signal)
        signal.signal(signal.SIGINT, self.handle_signal)
    
    def handle_signal(self, signum, frame):
        logger.info(f"Received signal {signum}, initiating graceful shutdown")
        self.shutdown_event.set()
    
    async def cleanup(self):
        logger.info("Starting cleanup...")
        
        # Stop accepting new requests
        app.state.accepting_requests = False
        
        # Wait for ongoing requests to complete
        await self.wait_for_requests()
        
        # Close database connections
        await database.disconnect()
        
        # Close Redis connections
        await redis_client.close()
        
        # Clean up temporary files
        self.cleanup_temp_files()
        
        logger.info("Cleanup completed")
    
    async def wait_for_requests(self, timeout: int = 30):
        start_time = time.time()
        while app.state.active_requests > 0:
            if time.time() - start_time > timeout:
                logger.warning("Timeout waiting for requests to complete")
                break
            await asyncio.sleep(0.1)
```

## Monitoring & Observability

### 1. Structured Logging
```python
# ✅ GOOD: Structured, contextual logging
import structlog

logger = structlog.get_logger()

class StructuredLogger:
    @staticmethod
    def log_presentation_creation(presentation_id: str, config: Dict):
        logger.info(
            "presentation_creation_started",
            presentation_id=presentation_id,
            topic=config.get("topic"),
            num_slides=config.get("num_slides"),
            style=config.get("style"),
            timestamp=datetime.now().isoformat()
        )
    
    @staticmethod
    def log_error(error: Exception, context: Dict):
        logger.error(
            "error_occurred",
            error_type=type(error).__name__,
            error_message=str(error),
            context=context,
            stack_trace=traceback.format_exc()
        )
    
    @staticmethod
    def log_performance(operation: str, duration: float):
        logger.info(
            "performance_metric",
            operation=operation,
            duration_seconds=duration,
            timestamp=datetime.now().isoformat()
        )
```

### 2. Metrics Collection
```python
# ✅ GOOD: Comprehensive metrics
from prometheus_client import Counter, Histogram, Gauge, Summary

# Define metrics
presentation_counter = Counter(
    'presentations_created_total',
    'Total presentations created',
    ['style', 'status']
)

generation_duration = Histogram(
    'presentation_generation_duration_seconds',
    'Time to generate presentation',
    ['style'],
    buckets=[1, 5, 10, 30, 60, 120, 300]
)

active_generations = Gauge(
    'active_presentation_generations',
    'Currently active generations'
)

ai_api_latency = Summary(
    'ai_api_latency_seconds',
    'AI API call latency',
    ['endpoint', 'model']
)

class MetricsCollector:
    @staticmethod
    def track_presentation(func):
        async def wrapper(*args, **kwargs):
            active_generations.inc()
            start_time = time.time()
            
            try:
                result = await func(*args, **kwargs)
                presentation_counter.labels(
                    style=kwargs.get('style', 'unknown'),
                    status='success'
                ).inc()
                return result
            
            except Exception as e:
                presentation_counter.labels(
                    style=kwargs.get('style', 'unknown'),
                    status='failure'
                ).inc()
                raise
            
            finally:
                duration = time.time() - start_time
                generation_duration.labels(
                    style=kwargs.get('style', 'unknown')
                ).observe(duration)
                active_generations.dec()
        
        return wrapper
```

### 3. Distributed Tracing
```python
# ✅ GOOD: Implement distributed tracing
from opentelemetry import trace
from opentelemetry.exporter.jaeger import JaegerExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# Setup tracing
trace.set_tracer_provider(TracerProvider())
tracer = trace.get_tracer(__name__)

jaeger_exporter = JaegerExporter(
    agent_host_name="localhost",
    agent_port=6831,
)

span_processor = BatchSpanProcessor(jaeger_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)

class TracedService:
    @staticmethod
    async def create_presentation(request: Dict):
        with tracer.start_as_current_span("create_presentation") as span:
            span.set_attribute("presentation.topic", request["topic"])
            span.set_attribute("presentation.slides", request["num_slides"])
            
            # Generate outline
            with tracer.start_as_current_span("generate_outline"):
                outline = await ai_service.generate_outline(request)
            
            # Select template
            with tracer.start_as_current_span("select_template"):
                template = await template_service.select(request)
            
            # Build presentation
            with tracer.start_as_current_span("build_presentation"):
                presentation = await build_presentation(outline, template)
            
            span.set_attribute("presentation.id", presentation.id)
            
            return presentation
```

## User Experience Guidelines

### 1. Progress Feedback
```python
# ✅ GOOD: Real-time progress updates
class ProgressTracker:
    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self.steps = []
        self.current_step = 0
    
    async def update(self, progress: float, message: str, details: Dict = None):
        update = {
            "progress": progress,
            "message": message,
            "details": details or {},
            "timestamp": datetime.now().isoformat()
        }
        
        await self.websocket.send_json(update)
        
        # Store for recovery
        self.steps.append(update)
    
    async def complete(self, result: Dict):
        await self.websocket.send_json({
            "progress": 100,
            "message": "Presentation ready!",
            "result": result,
            "timestamp": datetime.now().isoformat()
        })

# Usage
@app.websocket("/ws/presentations/{presentation_id}")
async def websocket_endpoint(websocket: WebSocket, presentation_id: str):
    await websocket.accept()
    tracker = ProgressTracker(websocket)
    
    try:
        await tracker.update(10, "Starting presentation generation...")
        # ... generate presentation with progress updates
        await tracker.update(50, "Creating slides...")
        # ... more updates
        await tracker.complete({"download_url": "..."})
    except WebSocketDisconnect:
        pass
```

### 2. User-Friendly Error Messages
```python
# ✅ GOOD: Clear, actionable error messages
class UserErrorHandler:
    ERROR_MESSAGES = {
        "topic_too_short": {
            "message": "The topic is too short. Please provide at least 3 words.",
            "suggestion": "Try being more specific about your presentation topic."
        },
        "template_not_found": {
            "message": "The selected template could not be found.",
            "suggestion": "Please choose a different template or use the default."
        },
        "ai_unavailable": {
            "message": "Our AI service is temporarily unavailable.",
            "suggestion": "Please try again in a few minutes or use our template-based option."
        },
        "rate_limit": {
            "message": "You've reached your usage limit for this hour.",
            "suggestion": "Please wait {retry_after} minutes or upgrade your plan."
        }
    }
    
    @classmethod
    def get_user_message(cls, error_code: str, **kwargs) -> Dict:
        error_info = cls.ERROR_MESSAGES.get(
            error_code,
            {
                "message": "An unexpected error occurred.",
                "suggestion": "Please try again or contact support."
            }
        )
        
        return {
            "error": error_info["message"].format(**kwargs),
            "suggestion": error_info["suggestion"].format(**kwargs),
            "error_code": error_code
        }
```

## Maintenance & Updates

### 1. Version Management
```python
# ✅ GOOD: API versioning strategy
from fastapi import APIRouter

# Version 1 endpoints
v1_router = APIRouter(prefix="/api/v1")

@v1_router.post("/presentations")
async def create_presentation_v1(request: PresentationRequestV1):
    # V1 implementation
    pass

# Version 2 endpoints with improvements
v2_router = APIRouter(prefix="/api/v2")

@v2_router.post("/presentations")
async def create_presentation_v2(request: PresentationRequestV2):
    # V2 implementation with new features
    pass

# Register both versions
app.include_router(v1_router)
app.include_router(v2_router)

# Deprecation notice for v1
@v1_router.post("/presentations")
async def create_presentation_v1_deprecated(request: PresentationRequestV1):
    headers = {
        "X-API-Deprecation": "true",
        "X-API-Deprecation-Date": "2025-12-31",
        "X-API-Upgrade-To": "/api/v2/presentations"
    }
    # Process request...
    return Response(content=result, headers=headers)
```

### 2. Database Migrations
```python
# ✅ GOOD: Safe database migrations
from alembic import op
import sqlalchemy as sa

def upgrade():
    """Apply migration"""
    # Add new column with default value
    op.add_column(
        'presentations',
        sa.Column('version', sa.Integer(), nullable=True, server_default='1')
    )
    
    # Backfill existing records
    op.execute("UPDATE presentations SET version = 1 WHERE version IS NULL")
    
    # Make column non-nullable
    op.alter_column('presentations', 'version', nullable=False)
    
    # Add index for performance
    op.create_index('ix_presentations_version', 'presentations', ['version'])

def downgrade():
    """Revert migration"""
    op.drop_index('ix_presentations_version', 'presentations')
    op.drop_column('presentations', 'version')
```

### 3. Feature Flags
```python
# ✅ GOOD: Feature flag management
class FeatureFlags:
    def __init__(self):
        self.flags = {
            "ai_image_generation": True,
            "advanced_templates": False,
            "smart_art": False,
            "collaboration": False
        }
    
    def is_enabled(self, feature: str, user_id: str = None) -> bool:
        # Check global flag
        if feature not in self.flags:
            return False
        
        # Check user-specific override
        if user_id:
            user_flags = self.get_user_flags(user_id)
            if feature in user_flags:
                return user_flags[feature]
        
        return self.flags[feature]
    
    def enable_for_percentage(self, feature: str, percentage: int):
        """Gradual rollout"""
        def should_enable(user_id: str) -> bool:
            return hash(user_id) % 100 < percentage
        
        self.flags[feature] = should_enable

# Usage
feature_flags = FeatureFlags()

async def create_presentation(request: Dict):
    if feature_flags.is_enabled("ai_image_generation", request["user_id"]):
        # Use AI image generation
        images = await generate_ai_images(request)
    else:
        # Use stock images
        images = await get_stock_images(request)
```

## Summary

These best practices ensure:

1. **Reliability**: Through error handling, fallbacks, and circuit breakers
2. **Performance**: Via caching, parallel processing, and optimization
3. **Security**: With input validation, authentication, and data privacy
4. **Maintainability**: Through clean architecture and testing
5. **Scalability**: Using microservices and proper resource management
6. **Observability**: With comprehensive logging and monitoring
7. **User Experience**: Through clear feedback and error messages

Following these guidelines will result in a robust, production-ready PowerPoint AI agent that can handle enterprise-scale demands while maintaining high quality and reliability.