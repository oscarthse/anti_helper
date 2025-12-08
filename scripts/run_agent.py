
import asyncio
import os
import shutil
import sys
import logging
import argparse
from pathlib import Path
from dotenv import load_dotenv

# Ensure project root is in path
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))
sys.path.append(str(project_root / "libs"))

from libs.gravity_core.agents.coder import CoderAgent
from libs.gravity_core.llm.client import LLMClient

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("HeadlessDebugger")

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
    files = [f for f in files if f.is_file()]

    print("\n--- WORKSPACE REPORT ---")
    if not files:
        print("❌ FAILURE: No files created.")
        return False

    success = True
    for f in files:
        rel_path = f.relative_to(DEBUG_WORKSPACE)
        print(f"📄 Found: {rel_path} ({f.stat().st_size} bytes)")
        if str(rel_path).startswith("[NEW]"):
            print(f"   ⚠️  GHOST FILE DETECTED: {rel_path}")
            success = False

    if success:
        print("\n✅ SUCCESS: Files created cleanly.")
    else:
        print("\n❌ FAILURE: Ghost files or issues detected.")
    return success

async def run_agent(prompt: str):
    """Run the agent with the given prompt."""
    setup_workspace()

    # Load Real ENV
    load_dotenv()
    if not os.getenv("OPENAI_API_KEY"):
        logger.error("❌ SKIPPING: No OPENAI_API_KEY found.")
        return

    logger.info("🤖 Initializing CoderAgent...")
    llm_client = LLMClient()
    agent = CoderAgent(
        specialty="be",
        llm_client=llm_client,
        model_name="gpt-4o"
    )

    logger.info(f"🧠 Prompting Agent: '{prompt}'")

    # Context mocking
    context = {
        "repo_path": str(DEBUG_WORKSPACE),
        "task_description": prompt,
        "step": {
            "description": prompt,
            "files_affected": [] # Empty initially, let agent decide
        }
    }

    try:
        # Execute agent
        output = await agent.execute(task_id="headless-debug-1", context=context)
        print(f"\n--- AGENT THOUGHTS ---\n{output.technical_reasoning}\n----------------------")
    except Exception as e:
        logger.error(f"❌ AGENT CRASHED: {e}", exc_info=True)

    scan_workspace()

def main():
    parser = argparse.ArgumentParser(description="Run Headless Agent Debugger")
    parser.add_argument("prompt", nargs="?", default="Create a python script called 'calculator.py' that adds two numbers.", help="Task prompt for the agent")
    args = parser.parse_args()

    asyncio.run(run_agent(args.prompt))

if __name__ == "__main__":
    main()
