from unittest.mock import AsyncMock, patch

import pytest
from gravity_core.guardrails.quality_gates import CoderSelfCheck


@pytest.mark.asyncio
class TestCoderSelfCheck:
    async def test_syntax_error_blocking(self, tmp_path):
        """Test that syntax errors are caught and marked as failures."""
        # Create a file with bad syntax
        bad_file = tmp_path / "bad.py"
        bad_file.write_text("def foo(:", encoding="utf-8")  # Syntax Error

        check = CoderSelfCheck()
        result = await check.verify([str(bad_file)])

        assert not result.success
        assert "Syntax Error" in result.errors[0]
        assert len(result.errors) == 1

    async def test_valid_syntax_passes(self, tmp_path):
        """Test that valid python passes syntax check."""
        good_file = tmp_path / "good.py"
        good_file.write_text("def foo():\n    pass\n", encoding="utf-8")

        check = CoderSelfCheck()

        # Mock linter to pass
        with patch(
            "gravity_core.guardrails.quality_gates.run_linter_fix", new_callable=AsyncMock
        ) as mock_lint:
            mock_lint.return_value = {"success": True, "lint": {"exit_code": 0}}

            result = await check.verify([str(good_file)])

        assert result.success
        assert len(result.errors) == 0

    async def test_linter_failure_is_warning_by_default(self, tmp_path):
        """Test that linter failures are treated as warnings by default."""
        messy_file = tmp_path / "messy.py"
        messy_file.write_text("x=1\n", encoding="utf-8")  # Valid syntax

        check = CoderSelfCheck()

        # Mock linter to fail (e.g. style violation)
        with patch(
            "gravity_core.guardrails.quality_gates.run_linter_fix", new_callable=AsyncMock
        ) as mock_lint:
            # Simulate ruff exit code 1
            mock_lint.return_value = {"success": True, "lint": {"exit_code": 1}}

            result = await check.verify([str(messy_file)])

        assert result.success  # Should still succeed
        assert len(result.errors) == 0
        assert len(result.warnings) > 0
        assert "Linter issues" in result.warnings[0]

    async def test_missing_file_handled(self):
        """Test graceful handling of missing files."""
        check = CoderSelfCheck()
        result = await check.verify(["/non/existent/path.py"])

        assert not result.success
        assert "File missing" in result.errors[0]

    async def test_non_python_files_skipped(self, tmp_path):
        """Test that non-python files are skipped for syntax/lint."""
        txt_file = tmp_path / "readme.txt"
        txt_file.write_text("hello", encoding="utf-8")

        check = CoderSelfCheck()
        # Mock linter - should NOT be called
        with patch(
            "gravity_core.guardrails.quality_gates.run_linter_fix", new_callable=AsyncMock
        ) as mock_lint:
            result = await check.verify([str(txt_file)])

            mock_lint.assert_not_called()

        assert result.success
        assert len(result.files_checked) == 1
