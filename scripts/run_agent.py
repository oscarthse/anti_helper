"""
Headless Agent Pipeline - Plan → Code

Runs the full PlannerAgent → CoderAgent pipeline for E2E testing.
This mirrors the real production workflow, where planning comes first.
"""

import asyncio
import json
import os
import shutil
import sys
import logging
import argparse
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv

# Ensure project root is in path
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))
sys.path.append(str(project_root / "libs"))

from libs.gravity_core.agents.planner import PlannerAgent
from libs.gravity_core.agents.coder import CoderAgent
from libs.gravity_core.llm.client import LLMClient

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("AgentPipeline")

DEBUG_WORKSPACE = project_root / "debug_workspace"


def setup_workspace():
    """Create a clean sandbox."""
    if DEBUG_WORKSPACE.exists():
        shutil.rmtree(DEBUG_WORKSPACE)
    DEBUG_WORKSPACE.mkdir(exist_ok=True)
    logger.info(f"📂 Workspace reset: {DEBUG_WORKSPACE}")


def scan_workspace() -> bool:
    """Scan debug_workspace and report results."""
    files = list(DEBUG_WORKSPACE.rglob("*"))
    files = [f for f in files if f.is_file() and f.name != ".DS_Store"]

    print("\n" + "=" * 60)
    print("📦 WORKSPACE REPORT")
    print("=" * 60)

    if not files:
        print("❌ FAILURE: No files created.")
        return False

    # Group by directory
    file_tree = {}
    for f in files:
        rel_path = f.relative_to(DEBUG_WORKSPACE)
        parent = str(rel_path.parent) if rel_path.parent != Path(".") else "(root)"
        if parent not in file_tree:
            file_tree[parent] = []
        file_tree[parent].append((rel_path.name, f.stat().st_size))

    for directory, file_list in sorted(file_tree.items()):
        print(f"\n📁 {directory}/")
        for name, size in file_list:
            print(f"   📄 {name} ({size} bytes)")

    print(f"\n✅ Total: {len(files)} files created")
    return True


async def run_pipeline(prompt: str):
    """Run the full Planner → Coder pipeline."""
    setup_workspace()

    # Load environment
    load_dotenv()
    if not os.getenv("OPENAI_API_KEY"):
        logger.error("❌ SKIPPING: No OPENAI_API_KEY found.")
        return

    llm_client = LLMClient()
    task_id = uuid4()
    repo_path = str(DEBUG_WORKSPACE)

    # =========================================================================
    # PHASE 1: PLANNING
    # =========================================================================
    print("\n" + "=" * 60)
    print("🧠 PHASE 1: PLANNING")
    print("=" * 60)
    logger.info(f"📋 User Request: '{prompt}'")

    planner = PlannerAgent(llm_client=llm_client, model_name="gpt-4o")

    planner_context = {
        "user_request": prompt,
        "repo_path": repo_path,
    }

    plan_output = await planner.execute(task_id=task_id, context=planner_context)

    # Parse the plan
    try:
        plan_data = json.loads(plan_output.technical_reasoning)
        task_plan = plan_data.get("task_plan", {})
        steps = task_plan.get("steps", [])
    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"❌ Failed to parse plan: {e}")
        print(f"Raw output: {plan_output.technical_reasoning[:500]}")
        return

    print(f"\n📋 Plan Generated: {len(steps)} steps")
    for i, step in enumerate(steps, 1):
        title = step.get("title", "Untitled")
        agent = step.get("agent", "unknown")
        files = step.get("files_affected", [])
        print(f"   {i}. [{agent.upper()}] {title}")
        for f in files:
            print(f"      → {f}")

    # =========================================================================
    # PHASE 2: EXECUTION
    # =========================================================================
    print("\n" + "=" * 60)
    print("💻 PHASE 2: EXECUTION")
    print("=" * 60)

    coder = CoderAgent(
        specialty="be",
        llm_client=llm_client,
        model_name="gpt-4o"
    )

    # Execute each step that requires the coder agent
    for i, step in enumerate(steps, 1):
        agent_type = step.get("agent", "coder")
        if agent_type not in ("coder", "coder_be", "coder_fe"):
            logger.info(f"⏭️  Skipping step {i} (agent: {agent_type})")
            continue

        print(f"\n--- Step {i}/{len(steps)}: {step.get('title', 'Untitled')} ---")

        coder_context = {
            "repo_path": repo_path,
            "task_description": prompt,
            "step": {
                "description": step.get("description", step.get("title", "")),
                "files_affected": step.get("files_affected", []),
            },
            "plan": task_plan,  # Give coder full plan context
        }

        try:
            coder_output = await coder.execute(task_id=task_id, context=coder_context)
            logger.info(f"✅ Step {i} complete (confidence: {coder_output.confidence_score:.2f})")
        except Exception as e:
            logger.error(f"❌ Step {i} failed: {e}")
            continue

    # =========================================================================
    # PHASE 3: REPORT
    # =========================================================================
    scan_workspace()


def main():
    parser = argparse.ArgumentParser(description="Run Agent Pipeline (Plan → Code)")
    parser.add_argument(
        "prompt",
        nargs="?",
        default="Create a simple calculator module with add, subtract, multiply, divide functions.",
        help="Task prompt for the agent"
    )
    args = parser.parse_args()

    asyncio.run(run_pipeline(args.prompt))


if __name__ == "__main__":
    main()
