# Development Guidelines

## Code Quality Standards

### Documentation Requirements
- **Module Docstrings**: Every Python module must start with a triple-quoted docstring explaining its purpose, key responsibilities, and architecture context
- **Class Docstrings**: All classes require docstrings describing their role and key features
- **Function Docstrings**: Public methods and functions must have docstrings with Args, Returns, and Raises sections
- **Inline Comments**: Use comments sparingly - prefer self-documenting code with clear variable names

### Type Annotations
- **Mandatory Type Hints**: All function signatures must include complete type annotations for parameters and return values
- **Modern Type Syntax**: Use `from __future__ import annotations` for forward references
- **Union Types**: Use `Type | None` syntax (Python 3.10+) instead of `Optional[Type]`
- **Generic Types**: Use TypeVar for generic Pydantic models: `T = TypeVar("T", bound=BaseModel)`
- **Strict Mypy**: Code must pass `mypy --strict` checks

### Code Structure
- **Class-Based Design**: Prefer classes with private helper methods over flat function collections
- **Private Methods**: Use `_method_name` prefix for internal implementation details
- **No Placeholders**: Never use `pass`, `...`, or `NotImplementedError` in production code paths
- **Minimum Code Volume**: Non-trivial files should exceed 100 lines of meaningful logic
- **Complete Implementations**: All functions must have real logic, not TODO comments or stubs

### Error Handling
- **Defensive Programming**: Wrap all I/O and network operations in try/except blocks
- **Structured Logging**: Use structlog with context fields instead of print statements
- **Graceful Degradation**: Log warnings for non-critical failures, raise exceptions for blocking errors
- **Custom Exceptions**: Define domain-specific exception classes (e.g., `LLMClientError`, `RealityCheckError`)

## Architectural Patterns

### Brain-Body-Face Separation
- **Brain (GravityCore)**: Pure intelligence layer - stateless, no database access, only LLM and tool logic
- **Body (Backend)**: State management - handles database, task queue, and orchestration
- **Face (Frontend)**: Presentation layer - React components with TanStack Query for server state

### Agent Design Pattern
```python
class MyAgent(BaseAgent):
    """All agents inherit from BaseAgent."""
    
    persona = AgentPersona.CODER_BE
    system_prompt = "..."
    available_tools = ["tool1", "tool2"]
    
    async def execute(self, task_id: UUID, context: dict) -> AgentOutput:
        """Main execution method - returns structured AgentOutput."""
        # 1. Gather context
        # 2. Call LLM with tools
        # 3. Process tool calls
        # 4. Return AgentOutput with confidence score
        return self.build_output(
            ui_title="User-friendly title",
            ui_subtitle="Plain English explanation",
            technical_reasoning=json.dumps(details),
            confidence_score=0.85,
        )
```

### Explainability Contract
Every agent action must produce an `AgentOutput` with:
- `ui_title`: Emoji-prefixed, user-friendly title (e.g., "💻 Code Updated")
- `ui_subtitle`: Plain English explanation of what happened
- `technical_reasoning`: JSON-serialized technical details for debugging
- `confidence_score`: Float 0.0-1.0 indicating certainty
- `requires_review`: Boolean flag for human review threshold

### Database Patterns
- **Async SQLAlchemy**: All database operations use `async with session` context managers
- **UUID Primary Keys**: Use `uuid4()` for all primary keys, not auto-increment integers
- **Enum Status Fields**: Define state machines with Python enums (e.g., `TaskStatus`)
- **Relationships**: Use `relationship()` with `back_populates` for bidirectional navigation
- **Timestamps**: Include `created_at` and `updated_at` fields with `datetime.utcnow()` defaults

### Tool Registry Pattern
```python
# Tool definitions for LLM function calling
TOOL_DEFINITION = {
    "name": "tool_name",
    "description": "What this tool does",
    "parameters": {
        "type": "object",
        "properties": {
            "param1": {"type": "string", "description": "..."},
        },
        "required": ["param1"],
    },
}

# Tool execution in agent
async def _process_tool_call(self, tool_call: dict, repo_path: str):
    tool_name = tool_call.get("name")
    arguments = tool_call.get("arguments", {})
    
    if tool_name == "my_tool":
        result = await self.call_tool("my_tool", **arguments)
        if result.success:
            # Process successful result
            pass
```

### Retry and Fallback Logic
```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type(LLMRateLimitError),
)
async def _attempt():
    # Operation with automatic retry
    pass
```

## Internal API Usage

### LLMClient Usage
```python
from gravity_core.llm import LLMClient

# Structured output (enforces Pydantic schema)
client = LLMClient(openai_api_key="...", enable_fallback=True)
result = await client.generate_structured_output(
    prompt="Analyze this task...",
    output_schema=AgentOutput,
    model_name="gpt-4o",
    temperature=0.7,
)

# Tool calling (for agents)
text, tool_calls = await client.generate_with_tools(
    prompt="Edit this file...",
    tools=CODER_TOOLS,
    tool_choice="required",  # or "auto" or specific tool dict
)
```

### Database Session Management
```python
from backend.app.db.session import get_session

# In API endpoints
async def endpoint(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Task).where(...))
    task = result.scalar_one_or_none()
    
    task.status = TaskStatus.COMPLETED
    await session.commit()

# In workers (create isolated engine)
async def worker_function():
    engine = await _create_worker_engine()
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    
    async with session_factory() as session:
        # Do work
        await session.commit()
    
    await engine.dispose()  # Always cleanup
```

### Event Bus (Redis Pub/Sub)
```python
from backend.app.core.events import get_event_bus

event_bus = get_event_bus()
await event_bus.publish_task_event(
    task_id=str(task_id),
    event_type="agent_log",
    data={
        "ui_title": "...",
        "step_number": 1,
    },
)
```

### Logging Patterns
```python
import structlog

logger = structlog.get_logger(__name__)

# Structured logging with context
logger.info(
    "agent_output_logged",
    task_id=str(task_id),
    agent=agent_output.agent_persona.value,
    step=step_number,
    confidence=agent_output.confidence_score,
)

# Error logging with exception
logger.exception(
    "worker_task_error",
    task_id=task_id,
    error_type=type(e).__name__,
)
```

## Code Idioms

### Path Sanitization
```python
from pathlib import Path

def _sanitize_path_and_create_dirs(self, repo_root: str, dirty_path: str) -> Path:
    """Clean LLM input and ensure directory exists."""
    # Remove [NEW] prefix and quotes
    clean_path = re.sub(r"^\[.*?\]\s*", "", dirty_path).strip().strip('"\'')
    
    # Security check - prevent path traversal
    full_path = Path(repo_root) / clean_path
    resolved = full_path.resolve()
    if not str(resolved).startswith(str(Path(repo_root).resolve())):
        raise ValueError(f"Path {clean_path} escapes repo boundary")
    
    # Create parent directories
    full_path.parent.mkdir(parents=True, exist_ok=True)
    return full_path
```

### Pydantic Schema Validation
```python
from pydantic import BaseModel, ValidationError

class MySchema(BaseModel):
    field1: str
    field2: int | None = None

try:
    validated = MySchema.model_validate(raw_data)
except ValidationError as e:
    errors = e.errors()
    logger.warning("validation_failed", errors=errors)
    raise
```

### Async Context Managers
```python
async def process_task():
    async with session_factory() as session:
        try:
            # Do work
            await session.commit()
        except Exception as e:
            await session.rollback()
            raise
```

### Tool Call Processing Loop
```python
async def _execute_code_generation_loop(self, user_prompt: str, files_affected: list[str]):
    """Iterative loop with retry logic for missing files."""
    remaining_files = set(files_affected)
    max_iterations = 3
    iteration = 0
    
    while remaining_files and iteration < max_iterations:
        iteration += 1
        
        # Generate with tools
        tool_calls = await self._generate_with_tools(user_prompt)
        
        # Process each tool call
        for tc in tool_calls:
            await self._process_tool_call(tc, repo_path)
        
        # Update remaining files
        created_files = {c.file_path for c in self._changes}
        remaining_files -= created_files
    
    if remaining_files:
        raise RuntimeError(f"Failed to create {len(remaining_files)} files")
```

## Testing Standards

### Test Structure
```python
class TestFeatureName:
    """Group related tests in classes."""
    
    @pytest.mark.asyncio
    async def test_specific_behavior(self, fixture1, fixture2):
        """
        TEST: One-line description of what's being tested.
        
        CLAIM BEING TESTED:
        "Specific claim about system behavior"
        """
        # GIVEN: Setup state
        initial_state = ...
        
        # WHEN: Perform action
        result = await function_under_test(...)
        
        # THEN: Verify outcome
        assert result.success
        assert expected_value in result.data
```

### Mock Strategy
- **Mock the Brain, Test the Body**: Mock LLM responses, test file system and database operations
- **Use AsyncMock**: For async functions: `mock_llm = AsyncMock(spec=LLMClient)`
- **Patch at Import**: `@patch("module.path.ClassName")` for dependency injection
- **Verify Calls**: Use `mock.assert_called_once()` and `mock.call_args` for verification

### Fixtures
```python
@pytest_asyncio.fixture
async def db_session():
    """Provide isolated database session for tests."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    
    await engine.dispose()
```

## Frontend Patterns

### Component Structure
```jsx
export function ComponentName({ prop1, prop2 }) {
  // 1. Hooks at top
  const { data, isLoading } = useQuery({ ... });
  const [localState, setLocalState] = useState(null);
  
  // 2. Event handlers
  const handleAction = useCallback(() => {
    // Logic
  }, [dependencies]);
  
  // 3. Early returns for loading/error states
  if (isLoading) return <Skeleton />;
  if (!data) return <EmptyState />;
  
  // 4. Main render
  return (
    <div className="flex flex-col gap-4">
      {/* Content */}
    </div>
  );
}
```

### TanStack Query Usage
```javascript
// Queries (GET)
const { data, isLoading, error } = useQuery({
  queryKey: ['tasks', taskId],
  queryFn: () => fetchTask(taskId),
  refetchInterval: 5000,  // Poll every 5 seconds
});

// Mutations (POST/PUT/DELETE)
const mutation = useMutation({
  mutationFn: (data) => createTask(data),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['tasks'] });
  },
});
```

### SSE Streaming
```javascript
function useTaskStream(taskId) {
  const [events, setEvents] = useState([]);
  
  useEffect(() => {
    const eventSource = new EventSource(`/api/tasks/${taskId}/stream`);
    
    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setEvents(prev => [...prev, data]);
    };
    
    return () => eventSource.close();
  }, [taskId]);
  
  return events;
}
```

## Security Practices

### Secret Encryption
```python
from gravity_core.utils.crypto import encrypt_secret, decrypt_secret

# Encrypt before storing
encrypted = encrypt_secret(api_key, encryption_key)

# Decrypt when needed
api_key = decrypt_secret(encrypted, encryption_key)
```

### Command Blocking
```python
DANGEROUS_PATTERNS = [
    r"rm\s+-rf",
    r"curl\s+.*\|.*sh",
    r"wget\s+.*\|.*sh",
    r"eval\s*\(",
]

def is_safe_command(cmd: str) -> bool:
    """Check if command contains dangerous patterns."""
    return not any(re.search(pattern, cmd) for pattern in DANGEROUS_PATTERNS)
```

### Path Traversal Prevention
```python
# Always resolve and check paths
resolved = Path(user_input).resolve()
if not str(resolved).startswith(str(safe_root.resolve())):
    raise SecurityError("Path traversal attempt detected")
```

## Performance Considerations

### Database Query Optimization
- Use `select()` with explicit column selection instead of loading entire objects
- Add indexes on frequently queried columns (task_id, status, created_at)
- Use `joinedload()` for eager loading relationships to avoid N+1 queries
- Batch operations with `session.execute()` instead of individual queries

### Async Best Practices
- Use `asyncio.gather()` for parallel operations: `results = await asyncio.gather(*tasks)`
- Avoid blocking calls in async functions - use `run_in_executor()` for CPU-bound work
- Set timeouts on external API calls: `async with timeout(30): await api_call()`

### Frontend Optimization
- Use React.memo() for expensive components that don't change often
- Implement virtual scrolling for long lists (react-window)
- Lazy load routes with React.lazy() and Suspense
- Debounce search inputs and API calls

## Common Annotations

### Python Decorators
```python
@dramatiq.actor(max_retries=3, time_limit=300_000)
def background_task(task_id: str):
    """Dramatiq actor for async task processing."""
    pass

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
async def resilient_operation():
    """Automatic retry with exponential backoff."""
    pass

@pytest.mark.asyncio
async def test_async_function():
    """Mark test as async for pytest-asyncio."""
    pass
```

### SQLAlchemy Mapped Columns
```python
class Model(Base):
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

## Configuration Management

### Environment Variables
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    redis_url: str
    openai_api_key: str | None = None
    
    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()
```

### Feature Flags
```python
# Use environment variables for feature toggles
ENABLE_LLM_FALLBACK = os.getenv("ENABLE_LLM_FALLBACK", "true").lower() == "true"
MAX_QA_RETRIES = int(os.getenv("MAX_QA_RETRIES", "3"))
```

## Migration Patterns

### Alembic Migrations
```python
# Create migration
# gravity db revision -m "add_new_column"

def upgrade():
    op.add_column('tasks', sa.Column('new_field', sa.String(255), nullable=True))

def downgrade():
    op.drop_column('tasks', 'new_field')
```

### Schema Synchronization
```bash
# Sync Pydantic models to TypeScript
sync-schema

# This generates TypeScript interfaces from Python Pydantic models
# Ensures frontend and backend share the same type definitions
```
