
import asyncio
import os
import shutil
import sys
import logging
from pathlib import Path
from unittest.mock import MagicMock

# Ensure project root is in path
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from libs.gravity_core.agents.coder import CoderAgent
from libs.gravity_core.llm.client import LLMClient

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(name)s - %(message)s')
logger = logging.getLogger("ForensicDebugger")

DEBUG_WORKSPACE = project_root / "debug_workspace"

def setup_workspace():
    """Create a clean sandbox."""
    if DEBUG_WORKSPACE.exists():
        shutil.rmtree(DEBUG_WORKSPACE)
    DEBUG_WORKSPACE.mkdir(exist_ok=True)
    print(f"📂 Workspace reset: {DEBUG_WORKSPACE}")

def verify_file_exists(rel_path: str, content_snippet: str = None) -> bool:
    """Verify file exists and optionally contains content."""
    full_path = DEBUG_WORKSPACE / rel_path
    if not full_path.exists():
        print(f"❌ MISSING: {rel_path} (Expected at {full_path})")
        # Check for ghost files (files starting with [NEW])
        ghost_path = DEBUG_WORKSPACE / f"[NEW] {rel_path}"
        if ghost_path.exists():
            print(f"👻 GHOST FILE DETECTED: {ghost_path.name}")
        return False

    if content_snippet:
        content = full_path.read_text()
        if content_snippet not in content:
            print(f"❌ CONTENT MISMATCH: '{content_snippet}' not found in {rel_path}")
            return False

    print(f"✅ VERIFIED: {rel_path}")
    return True

async def run_mode_a_deterministic():
    """
    Mode A: Manually invoke _process_tool_call with the problematic arguments.
    This bypasses the LLM and tests the python logic directly.
    """
    print("\n--- MODE A: FORENSIC REPRODUCTION (DETERMINISTIC) ---")

    # Mock LLM Client (not needed for this test but required for init)
    mock_llm = MagicMock(spec=LLMClient)

    agent = CoderAgent(
        specialty="be",
        llm_client=mock_llm,
        model_name="mock-gpt"
    )

    # 1. Test create_new_module with [NEW] prefix and nested folder
    tool_call_payload = {
        "name": "create_new_module",
        "arguments": {
            "file_path": "[NEW] nested/folder/test_file.py",
            "content": "print('hello_world')",
            "explanation": "Creating a test file"
        }
    }

    print(f"🔫 Firing Tool Call: {tool_call_payload}")

    # Directly invoke the logic we patched
    # Note: _process_tool_call is async
    await agent._process_tool_call(tool_call_payload, str(DEBUG_WORKSPACE))

    # Verification
    success = verify_file_exists("nested/folder/test_file.py", "print('hello_world')")

    print("\n--- MODE A RESULT ---")
    if success:
        print("✅ PASSED: [NEW] prefix stripped and directory created.")
    else:
        print("❌ FAILED: Logic bug persists.")

async def run_mode_b_live():
    """
    Mode B: Live LLM Call.
    Requires OPENAI_API_KEY in env.
    """
    print("\n--- MODE B: LIVE FIRE (LLM INTERACTION) ---")

    # Load Real ENV
    from dotenv import load_dotenv
    load_dotenv()

    if not os.getenv("OPENAI_API_KEY"):
        print("❌ SKIPPING MODE B: No OPENAI_API_KEY found.")
        return

    llm_client = LLMClient()
    agent = CoderAgent(
        specialty="be",
        llm_client=llm_client,
        model_name="gpt-4o"
    )

    prompt = "Create a python script called 'calculator.py' in a folder called 'tools' that adds two numbers."
    print(f"🧠 Prompting Agent: '{prompt}'")

    context = {
        "repo_path": str(DEBUG_WORKSPACE),
        "task_description": prompt,
        "step": {
            "description": prompt,
            "files_affected": ["tools/calculator.py"]
        }
    }

    # Execute full agent loop
    output = await agent.execute(task_id="debug-task-123", context=context)

    print(f"🤖 Agent Output: \n{output.technical_reasoning}")

    # Verification
    verify_file_exists("tools/calculator.py", "def add")


async def main():
    setup_workspace()

    mode = "A"
    if len(sys.argv) > 1:
        mode = sys.argv[1].upper()

    if mode == "A":
        await run_mode_a_deterministic()
    elif mode == "B":
        await run_mode_b_live()
    else:
        print("Usage: python scripts/test_agent_local.py [A|B]")

if __name__ == "__main__":
    asyncio.run(main())
