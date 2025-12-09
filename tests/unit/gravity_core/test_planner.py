"""
Unit Tests for PlannerAgent

Tests the planning algorithm including:
- Happy path with mocked LLM and RAG
- RAG influence verification
- Error handling for validation failures
- Context retrieval and pattern extraction
"""

# Add project paths
# Add project paths
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from gravity_core.agents.planner import PlannerAgent
from gravity_core.llm import LLMClient, LLMValidationError
from gravity_core.schema import AgentOutput, AgentPersona, TaskPlan, TaskStep


class TestPlannerAgentInitialization:
    """Tests for PlannerAgent initialization."""

    def test_planner_initializes_with_defaults(self):
        """Test planner initializes with default LLMClient."""
        with patch.object(LLMClient, "__init__", return_value=None):
            planner = PlannerAgent()

            assert planner.persona == AgentPersona.PLANNER
            assert planner.llm_client is not None

    def test_planner_initializes_with_custom_client(self):
        """Test planner accepts custom LLMClient."""
        mock_client = MagicMock(spec=LLMClient)
        planner = PlannerAgent(llm_client=mock_client)

        assert planner.llm_client is mock_client

    def test_planner_initializes_with_project_map(self):
        """Test planner accepts ProjectMap for RAG."""
        from gravity_core.memory.project_map import ProjectMap

        mock_map = MagicMock(spec=ProjectMap)
        planner = PlannerAgent(project_map=mock_map)

        assert planner.project_map is mock_map

    def test_planner_has_no_manipulation_tools(self):
        """Test planner cannot access file manipulation tools."""
        planner = PlannerAgent()

        # Verify no manipulation tools
        assert "edit_file_snippet" not in planner.available_tools
        assert "create_new_module" not in planner.available_tools
        assert "run_shell_command" not in planner.available_tools

        # Verify has perception tools
        assert "scan_repo_structure" in planner.available_tools
        assert "search_codebase" in planner.available_tools
        assert "get_file_signatures" in planner.available_tools


class TestPlannerExecuteHappyPath:
    """Tests for successful plan generation."""

    @pytest.fixture
    def mock_llm_client(self):
        """Create a mock LLM client that returns valid TaskPlan."""
        mock = MagicMock(spec=LLMClient)

        # Create a valid TaskPlan response
        mock.generate_structured_output = AsyncMock(
            return_value=TaskPlan(
                summary="Add input validation to user endpoint",
                steps=[
                    TaskStep(
                        step_id="step-1",
                        order=1,
                        description="Update User Pydantic schema with validation",
                        agent_persona=AgentPersona.CODER_BE,
                        files_affected=["backend/app/schemas/user.py"],
                    ),
                    TaskStep(
                        step_id="step-2",
                        order=2,
                        description="Add validation logic to endpoint",
                        agent_persona=AgentPersona.CODER_BE,
                        depends_on=["step-1"],
                        files_affected=["backend/app/api/users.py"],
                    ),
                    TaskStep(
                        step_id="step-3",
                        order=3,
                        description="Add unit tests for validation",
                        agent_persona=AgentPersona.QA,
                        depends_on=["step-2"],
                        files_affected=["tests/test_users.py"],
                    ),
                ],
                estimated_complexity=4,
                affected_files=[
                    "backend/app/schemas/user.py",
                    "backend/app/api/users.py",
                    "tests/test_users.py",
                ],
                risks=["May require database migration for new constraints"],
            )
        )

        return mock

    @pytest.fixture
    def mock_project_map(self):
        """Create a mock ProjectMap with project context."""
        mock = MagicMock()
        mock.last_scan = True
        mock.files = {
            "backend/app/schemas/user.py": MagicMock(
                classes=["UserCreate", "UserUpdate"],
                functions=["validate_email"],
            ),
            "backend/app/api/users.py": MagicMock(
                classes=[],
                functions=["create_user", "update_user", "get_user"],
            ),
        }
        mock.get_summary.return_value = {
            "project_type": "python",
            "framework": "fastapi",
            "files": 42,
            "languages": {"python": 35, "typescript": 7},
        }
        mock.to_context.return_value = "## Project Architecture\n- backend/app/"

        return mock

    @pytest.mark.asyncio
    async def test_execute_returns_valid_agent_output(
        self,
        mock_llm_client,
        mock_project_map,
    ):
        """Test execute returns valid AgentOutput."""
        planner = PlannerAgent(
            llm_client=mock_llm_client,
            project_map=mock_project_map,
        )

        # Mock the call_tool method to return proper ToolCall
        from gravity_core.schema import ToolCall

        planner.call_tool = AsyncMock(
            return_value=ToolCall(
                tool_name="search_codebase",
                arguments={"pattern": "validation"},
                success=True,
                result="search results",
            )
        )

        result = await planner.execute(
            task_id=uuid4(),
            context={
                "user_request": "Add input validation to user endpoint",
                "repo_path": "/app",
            },
        )

        assert isinstance(result, AgentOutput)
        assert result.agent_persona == AgentPersona.PLANNER
        assert "📋" in result.ui_title
        assert "3 Steps" in result.ui_title

    @pytest.mark.asyncio
    async def test_execute_calls_llm_with_structured_output(
        self,
        mock_llm_client,
        mock_project_map,
    ):
        """Test execute uses LLMClient with TaskPlan schema."""
        planner = PlannerAgent(
            llm_client=mock_llm_client,
            project_map=mock_project_map,
        )

        from gravity_core.schema import ToolCall

        planner.call_tool = AsyncMock(
            return_value=ToolCall(
                tool_name="search_codebase",
                arguments={"pattern": "validation"},
                success=True,
                result="",
            )
        )

        await planner.execute(
            task_id=uuid4(),
            context={
                "user_request": "Add validation",
                "repo_path": "/app",
            },
        )

        # Verify LLM was called with TaskPlan schema
        mock_llm_client.generate_structured_output.assert_called_once()
        call_kwargs = mock_llm_client.generate_structured_output.call_args.kwargs
        assert call_kwargs["output_schema"] == TaskPlan

    @pytest.mark.asyncio
    async def test_execute_includes_tool_calls_in_output(
        self,
        mock_llm_client,
        mock_project_map,
    ):
        """Test that tool calls are tracked in output."""
        planner = PlannerAgent(
            llm_client=mock_llm_client,
            project_map=mock_project_map,
        )

        # Mock tool call to return a ToolCall object
        from gravity_core.schema import ToolCall

        planner.call_tool = AsyncMock(
            return_value=ToolCall(
                tool_name="search_codebase",
                arguments={"pattern": "user"},
                success=True,
                result="Found matches",
            )
        )

        result = await planner.execute(
            task_id=uuid4(),
            context={
                "user_request": "Add user validation",
                "repo_path": "/app",
            },
        )

        assert len(result.tool_calls) > 0


class TestPlannerRAGInfluence:
    """Tests verifying RAG context influences the plan."""

    @pytest.mark.asyncio
    async def test_plan_differs_with_rag_context(self):
        """
        Test that the plan is influenced by RAG context.

        Strategy: Use LLM mocks that return different plans based on whether
        architectural context is present in the prompt.
        """
        from gravity_core.schema import ToolCall

        # Track prompts for both runs
        prompts_received = []

        def create_mock_llm_client():
            """Create a mock that tracks prompts and returns conditional plans."""
            mock = MagicMock(spec=LLMClient)

            async def capture_prompt(prompt, **kwargs):
                prompts_received.append(prompt)

                # Return different plan based on context presence
                if "ARCHITECTURAL_CONTEXT" in prompt or "UserProfile" in prompt:
                    step_desc = "Update the UserProfile model with validation"
                else:
                    step_desc = "Update the User model with validation"

                return TaskPlan(
                    summary="Plan for validation",
                    steps=[
                        TaskStep(
                            step_id="step-1",
                            order=1,
                            description=step_desc,
                            agent_persona=AgentPersona.CODER_BE,
                        ),
                    ],
                    estimated_complexity=3,
                    affected_files=[],
                    risks=[],
                )

            mock.generate_structured_output = AsyncMock(side_effect=capture_prompt)
            return mock

        # --- Test 1: Run WITHOUT RAG context ---
        mock_llm_no_rag = create_mock_llm_client()
        planner_no_rag = PlannerAgent(
            llm_client=mock_llm_no_rag,
            project_map=None,  # No RAG
        )
        planner_no_rag.call_tool = AsyncMock(
            return_value=ToolCall(
                tool_name="search_codebase",
                arguments={"pattern": "validation"},
                success=False,
                result="",
            )
        )

        result_no_rag = await planner_no_rag.execute(
            task_id=uuid4(),
            context={
                "user_request": "Add validation",
                "repo_path": "/app",
            },
        )

        prompt_no_rag = prompts_received[0] if prompts_received else ""
        prompts_received.clear()

        # --- Test 2: Run WITH RAG context ---
        mock_llm_with_rag = create_mock_llm_client()
        mock_project_map = MagicMock()
        mock_project_map.last_scan = True
        mock_project_map.files = {
            "backend/models.py": MagicMock(
                classes=["UserProfile", "Post"],
                functions=["validate"],
            ),
        }
        mock_project_map.get_summary.return_value = {
            "project_type": "python",
            "framework": "fastapi",
            "files": 10,
            "languages": {"python": 10},
        }
        # Use unique marker to verify RAG injection
        mock_project_map.to_context.return_value = (
            "## Project Architecture\n"
            "ARCHITECTURAL_CONTEXT: The database model is named UserProfile and not User.\n"
            "- backend/models.py: classes: UserProfile, Post; functions: validate"
        )

        planner_with_rag = PlannerAgent(
            llm_client=mock_llm_with_rag,
            project_map=mock_project_map,
        )
        planner_with_rag.call_tool = AsyncMock(
            return_value=ToolCall(
                tool_name="search_codebase",
                arguments={"pattern": "validation"},
                success=True,
                result="Found: UserProfile class in models.py",
            )
        )

        result_with_rag = await planner_with_rag.execute(
            task_id=uuid4(),
            context={
                "user_request": "Add validation",
                "repo_path": "/app",
            },
        )

        prompt_with_rag = prompts_received[0] if prompts_received else ""

        # --- Assertions ---
        # 1. Verify RAG context was injected into prompt
        assert "Architecture" in prompt_with_rag
        assert "UserProfile" in prompt_with_rag or "ARCHITECTURAL_CONTEXT" in prompt_with_rag

        # 2. Verify prompt WITH RAG is substantially larger
        assert len(prompt_with_rag) > len(prompt_no_rag) + 50

        # 3. Both should return valid AgentOutput
        assert isinstance(result_no_rag, AgentOutput)
        assert isinstance(result_with_rag, AgentOutput)


class TestPlannerErrorHandling:
    """Tests for error handling in PlannerAgent."""

    @pytest.mark.asyncio
    async def test_handles_missing_user_request(self):
        """Test graceful handling of missing user_request."""
        planner = PlannerAgent()

        result = await planner.execute(
            task_id=uuid4(),
            context={
                "repo_path": "/app",
                # Missing user_request
            },
        )

        assert isinstance(result, AgentOutput)
        assert "❌" in result.ui_title
        assert result.confidence_score == 0.0

    @pytest.mark.asyncio
    async def test_handles_validation_error(self):
        """Test handling of LLM validation errors."""
        from gravity_core.schema import ToolCall

        mock_client = MagicMock(spec=LLMClient)
        mock_client.generate_structured_output = AsyncMock(
            side_effect=LLMValidationError(
                "Schema validation failed",
                raw_response='{"invalid": "json"}',
                validation_errors=[{"loc": ["steps"], "msg": "required"}],
            )
        )

        planner = PlannerAgent(llm_client=mock_client)
        planner.call_tool = AsyncMock(
            return_value=ToolCall(
                tool_name="search_codebase",
                arguments={"pattern": "validation"},
                success=False,
                result="",
            )
        )

        result = await planner.execute(
            task_id=uuid4(),
            context={
                "user_request": "Add validation",
                "repo_path": "/app",
            },
        )

        assert isinstance(result, AgentOutput)
        assert "⚠️" in result.ui_title
        assert result.confidence_score <= 0.4  # Low confidence


class TestSearchPatternExtraction:
    """Tests for search pattern extraction logic."""

    def test_extracts_quoted_strings(self):
        """Test extraction of quoted identifiers."""
        planner = PlannerAgent()

        patterns = planner._extract_search_patterns('Add validation to "UserCreate" schema')

        assert "UserCreate" in patterns

    def test_extracts_camel_case(self):
        """Test extraction of CamelCase identifiers."""
        planner = PlannerAgent()

        patterns = planner._extract_search_patterns("Update the UserRegistrationRequest model")

        assert "UserRegistrationRequest" in patterns

    def test_extracts_snake_case(self):
        """Test extraction of snake_case identifiers."""
        planner = PlannerAgent()

        patterns = planner._extract_search_patterns("Fix the validate_email function")

        assert "validate_email" in patterns

    def test_extracts_file_references(self):
        """Test extraction of file references."""
        planner = PlannerAgent()

        patterns = planner._extract_search_patterns("Update models.py with new field")

        assert "models.py" in patterns

    def test_limits_pattern_count(self):
        """Test that patterns are limited to prevent overload."""
        planner = PlannerAgent()

        patterns = planner._extract_search_patterns(
            "UserModel CustomerModel ProductModel OrderModel PaymentModel "
            "ShippingModel InventoryModel CategoryModel ReviewModel TagModel"
        )

        assert len(patterns) <= 5
