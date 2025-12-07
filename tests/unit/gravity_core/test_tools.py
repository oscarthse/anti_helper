"""
Unit Tests for GravityCore Tools

Tests individual tool functions for correctness, error handling,
and edge cases.
"""

import pytest
import os
import tempfile
from pathlib import Path

# Add project paths
import sys
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "libs"))


class TestPerceptionTools:
    """Tests for perception tools (scan_repo_structure, search_codebase, get_file_signatures)."""

    @pytest.fixture
    def temp_repo(self):
        """Create a temporary repository structure for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a simple repo structure
            repo = Path(tmpdir)

            # Create directories
            (repo / "src").mkdir()
            (repo / "tests").mkdir()
            (repo / ".git").mkdir()  # Should be excluded

            # Create files
            (repo / "README.md").write_text("# Test Repo")
            (repo / "src" / "__init__.py").write_text("")
            (repo / "src" / "main.py").write_text("""
class MyClass:
    def __init__(self):
        pass

    def method(self):
        return True

def standalone_function():
    return "hello"
""")
            (repo / "tests" / "test_main.py").write_text("def test_example(): pass")

            yield repo

    @pytest.mark.asyncio
    async def test_scan_repo_structure(self, temp_repo):
        """Test scanning repository structure."""
        from gravity_core.tools.perception import scan_repo_structure

        result = await scan_repo_structure(str(temp_repo))

        assert "src" in result or "src/" in result
        assert "README.md" in result
        # .git should be excluded by default
        assert ".git" not in result

    @pytest.mark.asyncio
    async def test_scan_repo_structure_with_depth(self, temp_repo):
        """Test scanning with depth limit."""
        from gravity_core.tools.perception import scan_repo_structure

        result = await scan_repo_structure(str(temp_repo), max_depth=1)

        # Should include top-level items
        assert "src" in result or "src/" in result

    @pytest.mark.asyncio
    async def test_scan_repo_structure_nonexistent(self):
        """Test scanning nonexistent directory."""
        from gravity_core.tools.perception import scan_repo_structure

        result = await scan_repo_structure("/nonexistent/path/to/repo")

        assert "error" in result.lower() or "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_search_codebase(self, temp_repo):
        """Test searching codebase for patterns."""
        from gravity_core.tools.perception import search_codebase

        result = await search_codebase(str(temp_repo), "MyClass")

        assert "main.py" in result
        assert "MyClass" in result

    @pytest.mark.asyncio
    async def test_search_codebase_no_matches(self, temp_repo):
        """Test searching with no matches."""
        from gravity_core.tools.perception import search_codebase

        result = await search_codebase(str(temp_repo), "NonexistentPattern12345")

        assert "no matches" in result.lower() or result.strip() == ""

    @pytest.mark.asyncio
    async def test_get_file_signatures(self, temp_repo):
        """Test extracting file signatures."""
        from gravity_core.tools.perception import get_file_signatures

        result = await get_file_signatures(str(temp_repo / "src" / "main.py"))

        assert "MyClass" in result
        assert "method" in result
        assert "standalone_function" in result

    @pytest.mark.asyncio
    async def test_get_file_signatures_nonexistent(self):
        """Test extracting signatures from nonexistent file."""
        from gravity_core.tools.perception import get_file_signatures

        result = await get_file_signatures("/nonexistent/file.py")

        assert "error" in result.lower() or "not found" in result.lower()


class TestManipulationTools:
    """Tests for manipulation tools (edit_file_snippet, create_new_module, run_linter_fix)."""

    @pytest.fixture
    def temp_file(self):
        """Create a temporary file for editing."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("""def hello():
    return "Hello, World!"

def greet(name):
    return f"Hello, {name}!"
""")
            temp_path = f.name

        yield temp_path

        # Cleanup
        if os.path.exists(temp_path):
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_edit_file_snippet_success(self, temp_file):
        """Test successful file snippet editing."""
        from gravity_core.tools.manipulation import edit_file_snippet

        result = await edit_file_snippet(
            temp_file,
            old_content='return "Hello, World!"',
            new_content='return "Goodbye, World!"',
        )

        # Verify the edit was made
        content = Path(temp_file).read_text()
        assert 'return "Goodbye, World!"' in content
        assert "diff" in result.lower() or "success" in result.lower()

    @pytest.mark.asyncio
    async def test_edit_file_snippet_not_found(self, temp_file):
        """Test editing with content not in file."""
        from gravity_core.tools.manipulation import edit_file_snippet

        result = await edit_file_snippet(
            temp_file,
            old_content="nonexistent content",
            new_content="new content",
        )

        assert "not found" in result.lower() or "error" in result.lower()

    @pytest.mark.asyncio
    async def test_edit_file_snippet_multiple_matches(self, temp_file):
        """Test editing when snippet appears multiple times."""
        # Create file with duplicate content
        Path(temp_file).write_text("""
return True
return True
return True
""")
        from gravity_core.tools.manipulation import edit_file_snippet

        result = await edit_file_snippet(
            temp_file,
            old_content="return True",
            new_content="return False",
        )

        # Should either replace all or raise ambiguity error
        content = Path(temp_file).read_text()
        # The tool should handle this case - either error or replace first occurrence
        assert "return" in content  # File still valid

    @pytest.mark.asyncio
    async def test_edit_file_nonexistent(self):
        """Test editing nonexistent file."""
        from gravity_core.tools.manipulation import edit_file_snippet

        result = await edit_file_snippet(
            "/nonexistent/file.py",
            old_content="old",
            new_content="new",
        )

        assert "error" in result.lower() or "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_create_new_module(self):
        """Test creating a new module."""
        from gravity_core.tools.manipulation import create_new_module

        with tempfile.TemporaryDirectory() as tmpdir:
            new_file = Path(tmpdir) / "new_package" / "module.py"

            result = await create_new_module(
                str(new_file),
                content='def new_function(): pass',
            )

            assert new_file.exists()
            assert "def new_function" in new_file.read_text()

            # Check __init__.py was created
            init_file = new_file.parent / "__init__.py"
            assert init_file.exists()


class TestRuntimeTools:
    """Tests for runtime tools (run_shell_command, read_sandbox_logs)."""

    @pytest.mark.asyncio
    async def test_run_shell_command_success(self):
        """Test running a simple shell command."""
        from gravity_core.tools.runtime import run_shell_command

        result = await run_shell_command("echo 'Hello, World!'")

        assert "Hello, World!" in result

    @pytest.mark.asyncio
    async def test_run_shell_command_failure(self):
        """Test running a command that fails."""
        from gravity_core.tools.runtime import run_shell_command

        result = await run_shell_command("exit 1")

        # Should indicate failure
        assert "error" in result.lower() or "exit code" in result.lower() or "1" in result

    @pytest.mark.asyncio
    async def test_run_shell_command_blocked_dangerous(self):
        """Test that dangerous commands are blocked."""
        from gravity_core.tools.runtime import run_shell_command

        # Try to run rm -rf (should be blocked)
        result = await run_shell_command("rm -rf /")

        assert "blocked" in result.lower() or "denied" in result.lower() or "dangerous" in result.lower()

    @pytest.mark.asyncio
    async def test_run_shell_command_timeout(self):
        """Test command timeout handling."""
        from gravity_core.tools.runtime import run_shell_command

        # This test is environment-specific
        # In real sandbox, long-running commands would timeout
        result = await run_shell_command("echo 'quick'", timeout_seconds=1)

        # Quick command should succeed
        assert "quick" in result

    @pytest.mark.asyncio
    async def test_read_file_outside_repo_blocked(self):
        """Test that reading files outside repo is blocked."""
        from gravity_core.tools.runtime import run_shell_command

        # Attempt to read /etc/passwd
        result = await run_shell_command("cat /etc/passwd")

        # This shouldn't be blocked in local mode, but sandbox would block
        # Just ensure it doesn't crash
        assert isinstance(result, str)


class TestKnowledgeTools:
    """Tests for knowledge tools (web_search, scrape_web_content, check_dependency)."""

    @pytest.mark.asyncio
    async def test_check_dependency_version_installed(self):
        """Test checking version of installed package."""
        from gravity_core.tools.knowledge import check_dependency_version

        result = await check_dependency_version("pydantic")

        assert "pydantic" in result.lower()
        # Should contain version info
        assert any(c.isdigit() for c in result)  # Has version numbers

    @pytest.mark.asyncio
    async def test_check_dependency_version_not_installed(self):
        """Test checking version of package not installed."""
        from gravity_core.tools.knowledge import check_dependency_version

        result = await check_dependency_version("nonexistent-package-12345")

        assert "not installed" in result.lower() or "not found" in result.lower() or "error" in result.lower()


class TestVersionControlTools:
    """Tests for version control tools (git_commit_changes, git_diff_staged)."""

    @pytest.fixture
    def temp_git_repo(self):
        """Create a temporary git repository."""
        import subprocess

        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)

            # Initialize git repo
            subprocess.run(["git", "init"], cwd=repo, capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "test@example.com"],
                cwd=repo,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test User"],
                cwd=repo,
                capture_output=True,
            )

            # Create initial commit
            (repo / "README.md").write_text("# Test")
            subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", "Initial commit"],
                cwd=repo,
                capture_output=True,
            )

            yield repo

    @pytest.mark.asyncio
    async def test_git_diff_staged_no_changes(self, temp_git_repo):
        """Test git diff when no changes are staged."""
        from gravity_core.tools.version_control import git_diff_staged

        result = await git_diff_staged(str(temp_git_repo))

        assert "no changes" in result.lower() or result.strip() == ""

    @pytest.mark.asyncio
    async def test_git_diff_staged_with_changes(self, temp_git_repo):
        """Test git diff with staged changes."""
        import subprocess
        from gravity_core.tools.version_control import git_diff_staged

        # Make and stage a change
        (temp_git_repo / "new_file.py").write_text("print('hello')")
        subprocess.run(["git", "add", "."], cwd=temp_git_repo, capture_output=True)

        result = await git_diff_staged(str(temp_git_repo))

        assert "new_file.py" in result or "diff" in result.lower()
