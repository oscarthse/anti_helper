"""
Integration Tests for Reality Engine - File Write Verification

Tests the Reality Engine's ability to:
1. Write files to disk and verify they exist
2. Reject invalid or lazy code
3. Edit existing files with verification
4. Track all written files for batch verification
"""

from pathlib import Path

import pytest

from backend.app.schemas.reality import FileAction, VerifiedFileAction
from backend.app.workers.task_executor import RealityCheckError, RealityEngine


class TestRealityEngineFileCreation:
    """Tests for file creation with verification."""

    @pytest.fixture
    def tmp_repo(self, tmp_path: Path) -> str:
        """Create a temporary repository directory."""
        repo_dir = tmp_path / "test_repo"
        repo_dir.mkdir()
        return str(repo_dir)

    @pytest.fixture
    def reality_engine(self, tmp_repo: str) -> RealityEngine:
        """Create a RealityEngine with the temp repo."""
        return RealityEngine(repo_path=tmp_repo, step_index=0)

    def test_write_file_creates_and_verifies(self, reality_engine: RealityEngine, tmp_repo: str):
        """Test that writing a file creates it on disk and returns verified action."""
        content = """
def hello_world() -> str:
    \"\"\"Return a greeting.\"\"\"
    return "Hello, World!"

if __name__ == "__main__":
    print(hello_world())
"""
        result = reality_engine.write_file("hello.py", content)

        # Verify return type
        assert isinstance(result, VerifiedFileAction)
        assert result.action == FileAction.CREATE

        # Verify file exists on disk
        file_path = Path(tmp_repo) / "hello.py"
        assert file_path.exists()
        assert file_path.read_text() == content

        # Verify tracking
        assert str(file_path) in reality_engine.written_files
        assert result in reality_engine.verified_actions

    def test_write_file_creates_parent_directories(
        self, reality_engine: RealityEngine, tmp_repo: str
    ):
        """Test that writing to nested path creates parent directories."""
        content = "# Nested module\nVALUE = 42\n"
        _result = reality_engine.write_file("src/utils/constants.py", content)  # noqa: F841

        file_path = Path(tmp_repo) / "src" / "utils" / "constants.py"
        assert file_path.exists()
        assert file_path.read_text() == content

    def test_write_file_rejects_empty_content(self, reality_engine: RealityEngine):
        """Test that empty content raises ValueError."""
        # Write empty file - the Reality Engine writes it, but Pydantic validation fails
        with pytest.raises(ValueError, match="empty"):
            reality_engine.write_file("empty.py", "")

    def test_write_python_file_rejects_pass_only_function(self, reality_engine: RealityEngine):
        """Test that Python files with only 'pass' in functions are rejected."""
        lazy_code = '''
def do_nothing():
    """A lazy placeholder function."""
    pass
'''
        with pytest.raises(ValueError, match="pass"):
            reality_engine.write_file("lazy.py", lazy_code)

    def test_write_non_python_file_succeeds(self, reality_engine: RealityEngine, tmp_repo: str):
        """Test that non-Python files skip quality checks."""
        json_content = '{"name": "test", "version": "1.0.0"}'
        result = reality_engine.write_file("package.json", json_content)

        assert result.action == FileAction.CREATE
        file_path = Path(tmp_repo) / "package.json"
        assert file_path.exists()


class TestRealityEngineFileEditing:
    """Tests for file editing with verification."""

    @pytest.fixture
    def tmp_repo(self, tmp_path: Path) -> str:
        """Create a temporary repository with a sample file."""
        repo_dir = tmp_path / "test_repo"
        repo_dir.mkdir()

        # Create initial file
        sample_file = repo_dir / "sample.py"
        sample_file.write_text('''
def greet(name: str) -> str:
    """Greet someone."""
    return f"Hello, {name}!"
''')
        return str(repo_dir)

    @pytest.fixture
    def reality_engine(self, tmp_repo: str) -> RealityEngine:
        """Create a RealityEngine with the temp repo."""
        return RealityEngine(repo_path=tmp_repo, step_index=1)

    def test_edit_file_replaces_content(self, reality_engine: RealityEngine, tmp_repo: str):
        """Test that editing a file replaces the specified content."""
        result = reality_engine.edit_file(
            relative_path="sample.py",
            original_content='return f"Hello, {name}!"',
            new_content='return f"Hi there, {name}!"',
        )

        assert result.action == FileAction.UPDATE

        # Verify content changed
        file_path = Path(tmp_repo) / "sample.py"
        content = file_path.read_text()
        assert 'return f"Hi there, {name}!"' in content
        assert 'return f"Hello, {name}!"' not in content

    def test_edit_file_nonexistent_raises(self, reality_engine: RealityEngine):
        """Test that editing a non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="non-existent"):
            reality_engine.edit_file(
                relative_path="nonexistent.py",
                original_content="old",
                new_content="new",
            )

    def test_edit_file_original_not_found_raises(self, reality_engine: RealityEngine):
        """Test that editing with wrong original content raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            reality_engine.edit_file(
                relative_path="sample.py",
                original_content="this text does not exist",
                new_content="new content",
            )


class TestRealityEngineBatchVerification:
    """Tests for batch file verification."""

    @pytest.fixture
    def tmp_repo(self, tmp_path: Path) -> str:
        """Create a temporary repository directory."""
        repo_dir = tmp_path / "test_repo"
        repo_dir.mkdir()
        return str(repo_dir)

    @pytest.fixture
    def reality_engine(self, tmp_repo: str) -> RealityEngine:
        """Create a RealityEngine with the temp repo."""
        return RealityEngine(repo_path=tmp_repo, step_index=0)

    def test_verify_all_writes_detects_missing(self, reality_engine: RealityEngine, tmp_repo: str):
        """Test that batch verification detects missing files."""
        # Write one file
        reality_engine.write_file("exists.txt", "I exist!")

        # Verify including a file that doesn't exist
        all_verified, missing = reality_engine.verify_all_writes(
            [
                "exists.txt",
                "missing.txt",
                "also_missing.py",
            ]
        )

        assert all_verified is False
        assert len(missing) == 2
        assert any("missing.txt" in path for path in missing)
        assert any("also_missing.py" in path for path in missing)

    def test_verify_all_writes_all_present(self, reality_engine: RealityEngine, tmp_repo: str):
        """Test that batch verification passes when all files exist."""
        # Write multiple files
        reality_engine.write_file("file1.txt", "Content 1")
        reality_engine.write_file("file2.txt", "Content 2")
        reality_engine.write_file("src/file3.txt", "Content 3")

        all_verified, missing = reality_engine.verify_all_writes(
            [
                "file1.txt",
                "file2.txt",
                "src/file3.txt",
            ]
        )

        assert all_verified is True
        assert missing == []

    def test_reality_check_error_contains_missing_files(self, tmp_repo: str):
        """Test that RealityCheckError contains the correct missing file list."""
        missing_files = ["/path/to/missing1.py", "/path/to/missing2.py"]
        error = RealityCheckError(missing_files)

        assert error.missing_files == missing_files
        assert "missing1.py" in str(error)
        assert "missing2.py" in str(error)
