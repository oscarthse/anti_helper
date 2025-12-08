"""
PLANNER Agent - The Product Manager

The Strategic Architect that analyzes user requests, consults the RAG
context engine (ProjectMap), and generates atomic, dependency-aware
execution plans. This is the entry point for all task workflows.

Key Responsibilities:
1. Retrieve relevant codebase context via ProjectMap (RAG)
2. Construct system prompt with architectural understanding
3. Generate structured TaskPlan via LLMClient
4. Wrap output in AgentOutput with explainability

Security Constraints:
- NO file manipulation tools (edit_file_snippet, run_shell_command)
- Planning only - no execution
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

import structlog

from gravity_core.base import BaseAgent
from gravity_core.llm import LLMClient, LLMClientError, LLMValidationError
from gravity_core.memory.project_map import ProjectMap
from gravity_core.schema import (
    AgentOutput,
    AgentPersona,
    TaskPlan,
    ToolCall,
)

logger = structlog.get_logger(__name__)


# =============================================================================
# System Prompt - The Planner's Mindset
# =============================================================================

PLANNER_SYSTEM_PROMPT = """You are a **Senior System Architect** acting as the PLANNER agent.

## Your Role
You create **atomic, dependency-aware execution plans** that prevent system errors.
You do NOT write code - you only create strategic plans for other agents to execute.

## Critical Constraints

### 1. Atomic Steps
Each step must be a single, verifiable action:
- ✅ "Add `email_verified` field to User model in `models.py`"
- ✅ "Create Pydantic schema `UserUpdateRequest` in `schemas.py`"
- ❌ "Update the user system" (too vague)
- ❌ "Add validation and tests" (multiple actions)

### 2. Sequential Dependencies
Steps must respect logical order:
1. ORM model changes before API route changes
2. Schema definitions before endpoint implementations
3. Core logic before tests
4. Implementation before documentation

### 3. Agent Assignment
Assign each step to the correct specialist:
- `planner` - Only for analysis steps (you rarely assign to yourself)
- `coder_be` - Backend Python/database changes
- `coder_fe` - Frontend TypeScript/React changes
- `coder_infra` - Infrastructure, Docker, CI/CD, and NEW documentation files (README, etc.)
- `qa` - Testing and verification
- `docs` - Updates to EXISTING documentation only (cannot create files)

### 4. Affected Files
For each step, explicitly list which files will be modified:
- Be specific: `backend/app/db/models.py`, not "the models"
- Include new files to create: `[NEW] backend/app/schemas/user.py`

### 5. Risk Assessment
Identify potential issues:
- Breaking changes to existing APIs
- Migration requirements
- External service dependencies
- Complex logic requiring extra testing

## Your Output
Generate a TaskPlan with:
- `summary`: One-sentence description of the overall change
- `steps`: Ordered list of atomic TaskSteps
- `estimated_complexity`: 1-10 scale (based on scope and risk)
- `affected_files`: Complete list of files that will change
- `risks`: List of identified risks

## Formatting Requirements
Return ONLY valid JSON matching the TaskPlan schema.
No markdown, no explanations outside the JSON structure."""


# =============================================================================
# TaskPlan Generation Schema (for LLM)
# =============================================================================

TASK_PLAN_GENERATION_PROMPT = """## USER REQUEST
{user_request}

## PROJECT CONTEXT
{project_context}

## REFERENCE CODE / ARCHITECTURAL CONTEXT
{rag_context}

## INSTRUCTIONS
Based on the user request and the architectural context above, create a detailed execution plan.

Consider:
1. Which existing files/classes need modification?
2. What new files need to be created?
3. What is the correct order of operations?
4. What could go wrong?

Generate the TaskPlan now."""


# =============================================================================
# PlannerAgent Implementation
# =============================================================================


class PlannerAgent(BaseAgent):
    """
    The PLANNER agent - Product Manager persona.

    Creates strategic, atomic execution plans by:
    1. Querying ProjectMap for codebase context (RAG)
    2. Constructing context-aware prompts
    3. Generating structured TaskPlan via LLM
    4. Validating and wrapping in AgentOutput

    Security: Has NO access to manipulation or runtime tools.
    """

    persona = AgentPersona.PLANNER
    system_prompt = PLANNER_SYSTEM_PROMPT

    # Perception and knowledge tools ONLY - no file manipulation
    available_tools = [
        # Perception tools (read-only)
        "scan_repo_structure",
        "search_codebase",
        "get_file_signatures",
        # Knowledge tools (external research)
        "web_search_docs",
        "check_dependency_version",
    ]

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        project_map: ProjectMap | None = None,
        model_name: str = "gpt-4o",
    ):
        """
        Initialize the Planner agent.

        Args:
            llm_client: LLMClient instance for structured generation
            project_map: ProjectMap for RAG context
            model_name: LLM model to use for planning
        """
        super().__init__()

        # Initialize LLM client (uses env vars if not provided)
        self.llm_client = llm_client or LLMClient()
        self.project_map = project_map
        self.model_name = model_name

        logger.info(
            "planner_initialized",
            model=model_name,
            has_project_map=project_map is not None,
        )

    async def execute(
        self,
        task_id: UUID,
        context: dict[str, Any],
    ) -> AgentOutput:
        """
        Analyze the task and create an execution plan.

        The Planning Algorithm:
        1. Initial Context Retrieval (RAG Query)
        2. System Prompt Construction
        3. Structured Generation & Verification

        Args:
            task_id: The task being planned
            context: Must contain:
                - 'user_request': The natural language request
                - 'repo_path': Path to the repository

        Returns:
            AgentOutput containing TaskPlan in technical_reasoning
        """
        user_request = context.get("user_request", "")
        repo_path = context.get("repo_path", ".")

        if not user_request:
            return self.build_output(
                ui_title="❌ Planning Failed",
                ui_subtitle="No user request provided.",
                technical_reasoning="Error: 'user_request' is required in context.",
                confidence_score=0.0,
            )

        logger.info(
            "planner_starting",
            task_id=str(task_id),
            request_preview=user_request[:100],
            repo_path=repo_path,
        )

        tool_calls: list[ToolCall] = []

        try:
            # =========================================================
            # STEP 1: Initial Context Retrieval (The "Think First" Phase)
            # =========================================================

            project_context, rag_context, rag_tool_calls = await self._retrieve_context(
                user_request=user_request,
                repo_path=repo_path,
            )
            tool_calls.extend(rag_tool_calls)

            # =========================================================
            # STEP 2: Construct the Generation Prompt
            # =========================================================

            generation_prompt = TASK_PLAN_GENERATION_PROMPT.format(
                user_request=user_request,
                project_context=project_context,
                rag_context=rag_context or "No specific code context retrieved.",
            )

            # =========================================================
            # STEP 3: Generate Structured TaskPlan via LLM
            # =========================================================

            task_plan = await self._generate_plan(
                prompt=generation_prompt,
                user_request=user_request,
            )

            # =========================================================
            # STEP 4: Calculate Confidence and Build Output
            # =========================================================

            confidence = self._calculate_confidence(
                plan=task_plan,
                has_rag_context=bool(rag_context),
            )

            return self.build_output(
                ui_title=f"📋 Strategic Plan: {len(task_plan.steps)} Steps",
                ui_subtitle=self._generate_subtitle(task_plan),
                technical_reasoning=json.dumps({
                    "task_plan": task_plan.model_dump(mode='json'),
                    "rag_influence": {
                        "context_retrieved": bool(rag_context),
                        "context_length": len(rag_context) if rag_context else 0,
                    },
                    "model_used": self.model_name,
                }, indent=2),
                confidence_score=confidence,
                tool_calls=tool_calls,
            )

        except LLMValidationError as e:
            logger.warning(
                "planner_validation_error",
                task_id=str(task_id),
                errors=e.validation_errors,
            )
            return self.build_output(
                ui_title="⚠️ Plan Requires Review",
                ui_subtitle="I generated a plan but it needs human verification.",
                technical_reasoning=json.dumps({
                    "error": "LLM output validation failed",
                    "validation_errors": e.validation_errors,
                    "raw_response": e.raw_response[:1000],
                }),
                confidence_score=0.3,  # Low confidence triggers review
                tool_calls=tool_calls,
            )

        except LLMClientError as e:
            logger.error(
                "planner_llm_error",
                task_id=str(task_id),
                error=str(e),
                provider=e.provider,
            )
            return self.build_output(
                ui_title="❌ Planning Failed",
                ui_subtitle="Could not connect to AI service. Please try again.",
                technical_reasoning=json.dumps({
                    "error": str(e),
                    "provider": e.provider,
                    "retryable": e.retryable,
                }),
                confidence_score=0.0,
                tool_calls=tool_calls,
            )

    # =========================================================================
    # Step 1: RAG Context Retrieval
    # =========================================================================

    async def _retrieve_context(
        self,
        user_request: str,
        repo_path: str,
    ) -> tuple[str, str | None, list[ToolCall]]:
        """
        Retrieve relevant context using ProjectMap and perception tools.

        Returns:
            Tuple of (project_context, rag_context, tool_calls)
        """
        tool_calls: list[ToolCall] = []
        rag_context_parts: list[str] = []

        # --- Get Project Summary from ProjectMap ---
        project_context = "Project: Unknown"
        if self.project_map:
            try:
                # Ensure the map is scanned
                if not self.project_map.last_scan:
                    await self.project_map.scan()

                summary = self.project_map.get_summary()
                project_context = (
                    f"Project Type: {summary.get('project_type', 'unknown')}\n"
                    f"Framework: {summary.get('framework', 'none')}\n"
                    f"Files: {summary.get('files', 0)}\n"
                    f"Languages: "
                    f"{', '.join(f'{k}={v}' for k, v in summary.get('languages', {}).items())}"
                )

                # Get architectural context
                arch_context = self.project_map.to_context(max_tokens=1500)
                if arch_context:
                    rag_context_parts.append(f"## Project Architecture\n{arch_context}")

            except Exception as e:
                logger.warning("project_map_error", error=str(e))

        # --- Extract Search Keywords from Request ---
        search_patterns = self._extract_search_patterns(user_request)

        # --- Search Codebase for Relevant Code ---
        for pattern in search_patterns[:3]:  # Limit to 3 searches
            try:
                result = await self.call_tool(
                    "search_codebase",
                    path=repo_path,
                    pattern=pattern,
                )
                tool_calls.append(result)

                if result.success and result.result:
                    rag_context_parts.append(
                        f"## Search Results for '{pattern}'\n{result.result[:1500]}"
                    )

            except Exception as e:
                logger.debug("search_failed", pattern=pattern, error=str(e))

        # --- Get Function Signatures for Relevant Files ---
        if self.project_map and search_patterns:
            # Find files that might be relevant
            relevant_files = []
            for pattern in search_patterns:
                for file_path, file_info in self.project_map.files.items():
                    if (
                        pattern.lower() in file_path.lower() or
                        any(pattern.lower() in c.lower() for c in file_info.classes) or
                        any(pattern.lower() in f.lower() for f in file_info.functions)
                    ):
                        relevant_files.append(file_path)

            # Get signatures for up to 3 relevant files
            for file_path in relevant_files[:3]:
                try:
                    result = await self.call_tool(
                        "get_file_signatures",
                        file_path=f"{repo_path}/{file_path}",
                    )
                    tool_calls.append(result)

                    if result.success and result.result:
                        rag_context_parts.append(
                            f"## Signatures from {file_path}\n{result.result[:1000]}"
                        )

                except Exception as e:
                    logger.debug("signature_failed", file=file_path, error=str(e))

        rag_context = "\n\n".join(rag_context_parts) if rag_context_parts else None

        logger.info(
            "context_retrieved",
            rag_parts=len(rag_context_parts),
            rag_length=len(rag_context) if rag_context else 0,
            tool_calls=len(tool_calls),
        )

        return project_context, rag_context, tool_calls

    def _extract_search_patterns(self, user_request: str) -> list[str]:
        """
        Extract search patterns from the user request.

        Identifies technical terms, class names, function names,
        file references, and domain concepts.
        """
        import re

        patterns: list[str] = []

        # Find quoted strings (explicit identifiers)
        quoted = re.findall(r'["\']([^"\']+)["\']', user_request)
        patterns.extend(quoted)

        # Find CamelCase words (likely class names)
        camel_case = re.findall(r'[A-Z][a-z]+(?:[A-Z][a-z]+)+', user_request)
        patterns.extend(camel_case)

        # Find snake_case words (likely function/file names)
        snake_case = re.findall(r'[a-z]+_[a-z][a-z_]*', user_request)
        patterns.extend(snake_case)

        # Find file extensions (likely file references)
        file_refs = re.findall(r'\b[\w/]+\.\w+\b', user_request)
        patterns.extend(file_refs)

        # Extract significant words (length > 4, not stopwords)
        stopwords = {
            'about', 'above', 'after', 'again', 'all', 'also', 'and', 'any',
            'because', 'been', 'before', 'being', 'between', 'both', 'but',
            'could', 'each', 'have', 'having', 'here', 'into', 'just', 'made',
            'make', 'more', 'most', 'need', 'only', 'other', 'over', 'please',
            'should', 'some', 'such', 'than', 'that', 'the', 'their', 'them',
            'then', 'there', 'these', 'they', 'this', 'through', 'want', 'what',
            'when', 'where', 'which', 'while', 'will', 'with', 'would',
        }
        words = re.findall(r'\b([a-zA-Z]{5,})\b', user_request.lower())
        significant = [w for w in words if w not in stopwords]
        patterns.extend(significant[:3])  # Limit to top 3

        # Deduplicate while preserving order
        seen = set()
        unique_patterns = []
        for p in patterns:
            if p.lower() not in seen:
                seen.add(p.lower())
                unique_patterns.append(p)

        return unique_patterns[:5]  # Return max 5 patterns

    # =========================================================================
    # Step 3: Structured Generation
    # =========================================================================

    async def _generate_plan(
        self,
        prompt: str,
        user_request: str,
    ) -> TaskPlan:
        """
        Generate a TaskPlan using the LLM client.

        Uses structured output to ensure valid Pydantic model.
        """
        logger.info("generating_plan", model=self.model_name)

        task_plan = await self.llm_client.generate_structured_output(
            prompt=prompt,
            output_schema=TaskPlan,
            model_name=self.model_name,
            system_prompt=PLANNER_SYSTEM_PROMPT,
            temperature=0.4,  # Lower temperature for more consistent plans
        )

        logger.info(
            "plan_generated",
            steps=len(task_plan.steps),
            complexity=task_plan.estimated_complexity,
            affected_files=len(task_plan.affected_files),
        )

        return task_plan

    # =========================================================================
    # Step 4: Confidence Calculation & Output
    # =========================================================================

    def _calculate_confidence(
        self,
        plan: TaskPlan,
        has_rag_context: bool,
    ) -> float:
        """
        Calculate confidence score based on plan quality and context.
        """
        confidence = 0.85  # Base confidence

        # Higher confidence with RAG context
        if has_rag_context:
            confidence += 0.05

        # Lower confidence for high complexity
        if plan.estimated_complexity >= 8:
            confidence -= 0.15
        elif plan.estimated_complexity >= 6:
            confidence -= 0.05

        # Lower confidence for many risks
        confidence -= 0.03 * min(len(plan.risks), 5)

        # Lower confidence if no affected files identified
        if not plan.affected_files:
            confidence -= 0.1

        # Ensure bounds
        return max(0.3, min(0.95, confidence))

    def _generate_subtitle(self, plan: TaskPlan) -> str:
        """Generate a user-friendly subtitle explaining the plan."""

        # Count agents involved
        agents = set(step.agent_persona for step in plan.steps)
        agent_names = {
            AgentPersona.PLANNER: "Planning",
            AgentPersona.CODER_BE: "Backend",
            AgentPersona.CODER_FE: "Frontend",
            AgentPersona.CODER_INFRA: "Infrastructure",
            AgentPersona.QA: "Testing",
            AgentPersona.DOCS: "Documentation",
        }
        involved = [agent_names.get(a, str(a)) for a in agents]

        # Build subtitle
        parts = [plan.summary]

        if plan.affected_files:
            parts.append(f"Modifying {len(plan.affected_files)} files.")

        if len(involved) > 1:
            parts.append(f"Involves: {', '.join(involved)}.")

        if plan.risks:
            parts.append(f"⚠️ {len(plan.risks)} risk(s) identified.")

        return " ".join(parts)
