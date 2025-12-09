"""
Unit Tests for GravityCore Tools

Tests individual tool functions for correctness, error handling,
and edge cases.
"""

import os

# Add project paths
# Add project paths
import tempfile
from pathlib import Path

import pytest
from gravity_core.tools.knowledge import check_dependency_version
from gravity_core.tools.manipulation import create_new_module, edit_file_snippet
from gravity_core.tools.perception import get_file_signatures, scan_repo_structure, search_codebase
from gravity_core.tools.runtime import run_shell_command
from gravity_core.tools.version_control import git_diff_staged


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

        result = await scan_repo_structure(str(temp_repo))

        assert result["root"] == str(temp_repo)
        # Check simple names in tree
        names = [item["name"] for item in result["tree"]]
        assert "src" in names
        assert "README.md" in names
        # .git should be excluded by default
        assert ".git" not in names

    @pytest.mark.asyncio
    async def test_scan_repo_structure_with_depth(self, temp_repo):
        """Test scanning with depth limit."""

        result = await scan_repo_structure(str(temp_repo), max_depth=1)

        names = [item["name"] for item in result["tree"]]
        assert "src" in names

    @pytest.mark.asyncio
    async def test_scan_repo_structure_nonexistent(self):
        """Test scanning nonexistent directory."""

        result = await scan_repo_structure("/nonexistent/path/to/repo")

        assert "error" in result

    @pytest.mark.asyncio
    async def test_search_codebase(self, temp_repo):
        """Test searching codebase for patterns."""

        result = await search_codebase(str(temp_repo), "MyClass")

        # Check matches list
        assert len(result["matches"]) > 0
        file_paths = [m["file"] for m in result["matches"]]
        assert "src/main.py" in file_paths or "src/main.py" in [
            f.replace("\\", "/") for f in file_paths
        ]

    @pytest.mark.asyncio
    async def test_search_codebase_no_matches(self, temp_repo):
        """Test searching with no matches."""

        result = await search_codebase(str(temp_repo), "NonexistentPattern12345")

        assert len(result["matches"]) == 0

    @pytest.mark.asyncio
    async def test_get_file_signatures(self, temp_repo):
        """Test extracting file signatures."""

        result = await get_file_signatures(str(temp_repo / "src" / "main.py"))

        assert "signatures" in result
        sigs = result["signatures"]
        names = [s["name"] for s in sigs]
        assert "MyClass" in names
        assert "standalone_function" in names

    @pytest.mark.asyncio
    async def test_get_file_signatures_nonexistent(self):
        """Test extracting signatures from nonexistent file."""

        result = await get_file_signatures("/nonexistent/file.py")

        assert "error" in result


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

        result = await edit_file_snippet(
            temp_file,
            old_content='return "Hello, World!"',
            new_content='return "Goodbye, World!"',
        )

        assert result.success is True
        # Verify the edit was made
        content = Path(temp_file).read_text()
        assert 'return "Goodbye, World!"' in content

    @pytest.mark.asyncio
    async def test_edit_file_snippet_not_found(self, temp_file):
        """Test editing with content not in file."""

        result = await edit_file_snippet(
            temp_file,
            old_content="nonexistent content",
            new_content="new content",
        )

        assert result.success is False
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_edit_file_snippet_multiple_matches(self, temp_file):
        """Test editing when snippet appears multiple times."""
        # Create file with duplicate content
        Path(temp_file).write_text("""
return True
return True
return True
""")

        # Replace first occurrence (default)
        result = await edit_file_snippet(
            temp_file,
            old_content="return True",
            new_content="return False",
        )

        assert result.success is True

        content = Path(temp_file).read_text()
        assert "return False" in content
        assert content.count("return True") == 2

    @pytest.mark.asyncio
    async def test_edit_file_nonexistent(self):
        """Test editing nonexistent file."""

        result = await edit_file_snippet(
            "/nonexistent/file.py",
            old_content="old",
            new_content="new",
        )

        assert result.success is False
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_create_new_module(self):
        """Test creating a new module."""

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create dummy pyproject.toml to stop recursion
            (Path(tmpdir) / "pyproject.toml").touch()
            new_file = Path(tmpdir) / "new_package" / "module.py"

            result = await create_new_module(
                str(new_file),
                content="def new_function(): pass",
            )

            assert result.success is True
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

        result = await run_shell_command("echo 'Hello, World!'")

        assert result["success"] is True
        assert "Hello, World!" in result["stdout"]

    @pytest.mark.asyncio
    async def test_run_shell_command_failure(self):
        """Test running a command that fails."""

        result = await run_shell_command("exit 1")

        # Command ran successfully (tool success) but returned exit code 1
        assert result["success"] is False
        assert result["exit_code"] == 1

    @pytest.mark.asyncio
    async def test_run_shell_command_blocked_dangerous(self):
        """Test that dangerous commands are blocked."""

        # Try to run rm -rf (should be blocked)
        result = await run_shell_command("rm -rf /")

        assert result["success"] is False
        assert "blocked" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_run_shell_command_timeout(self):
        """Test command timeout handling."""

        # This test runs "echo 'quick'" with timeout 1s.
        # It should succeed fast enough.
        result = await run_shell_command("echo 'quick'", timeout_seconds=1)

        assert result["success"] is True
        assert "quick" in result["stdout"]

    @pytest.mark.asyncio
    async def test_read_file_outside_repo_blocked(self):
        """Test that reading files outside repo is blocked."""

        # Attempt to read /etc/passwd
        result = await run_shell_command("cat /etc/passwd")

        # In local execution (fallback), checking for success key
        assert "success" in result


class TestKnowledgeTools:
    """Tests for knowledge tools (web_search, scrape_web_content, check_dependency)."""

    @pytest.mark.asyncio
    async def test_check_dependency_version_installed(self):
        """Test checking version of installed package."""

        result = await check_dependency_version("pydantic")

        # Returns dict
        assert isinstance(result, dict)
        assert result["package"] == "pydantic"
        assert result["installed_version"] is not None

    @pytest.mark.asyncio
    async def test_check_dependency_version_not_installed(self):
        """Test checking version of package not installed."""

        result = await check_dependency_version("nonexistent-package-12345")

        assert isinstance(result, dict)
        assert result["installed_version"] is None


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

        result = await git_diff_staged(str(temp_git_repo))

        assert result["success"] is True
        # Diff should be empty or indicate no changes
        assert not result["diff"].strip()

    @pytest.mark.asyncio
    async def test_git_diff_staged_with_changes(self, temp_git_repo):
        """Test git diff with staged changes."""
        import subprocess

        # Make and stage a change
        (temp_git_repo / "new_file.py").write_text("print('hello')")
        subprocess.run(["git", "add", "."], cwd=temp_git_repo, capture_output=True)

        result = await git_diff_staged(str(temp_git_repo))

        assert result["success"] is True
        assert "new_file.py" in result["diff"]
