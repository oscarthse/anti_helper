import tempfile
from pathlib import Path

import pytest
from gravity_core.tools.manipulation import create_new_module, edit_file_snippet
from gravity_core.tools.perception import read_file
from gravity_core.tools.policies import (
    FileAccessPolicy,
    clear_current_policy,
    get_current_policy,
    set_current_policy,
)


@pytest.mark.asyncio
class TestIntegrationAccessPolicy:
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        # Create temp file
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp_dir.name)

        # Create a dummy file
        self.test_file = self.tmp_path / "target.py"
        self.test_file.write_text("def foo():\n    pass\n")

        # Setup clean policy
        clear_current_policy()

        yield

        # Cleanup
        clear_current_policy()
        self.tmp_dir.cleanup()

    async def test_edit_blocked_without_read(self):
        """Verify editing is blocked if file hasn't been read."""
        policy = FileAccessPolicy()
        set_current_policy(policy)

        path_str = str(self.test_file)

        # Attempt edit directly
        result = await edit_file_snippet(
            path=path_str, old_content="pass", new_content="return True"
        )

        assert not result.success
        assert "Policy Violation" in result.error
        assert "must read file" in result.error

    async def test_edit_allowed_after_read(self):
        """Verify editing is allowed after reading."""
        policy = FileAccessPolicy()
        set_current_policy(policy)

        path_str = str(self.test_file)

        # 1. Read file
        read_result = await read_file(path=path_str)
        assert "content" in read_result
        assert "def foo" in read_result["content"]

        # Verify policy recorded it
        assert policy.can_edit(path_str)

        # 2. Edit file
        result = await edit_file_snippet(
            path=path_str, old_content="pass", new_content="return True"
        )

        assert result.success, f"Edit failed: {result.error}"
        assert "return True" in self.test_file.read_text()

    async def test_create_allowed_without_read(self):
        """Verify creating new files is always allowed."""
        policy = FileAccessPolicy()
        set_current_policy(policy)

        new_file = self.tmp_path / "new_module.py"
        path_str = str(new_file)

        result = await create_new_module(path=path_str, content="x = 1")

        assert result.success is True
        assert new_file.exists()

    async def test_no_policy_enforcement_if_unset(self):
        """Verify existing behavior is preserved if no policy is active."""
        clear_current_policy()
        assert get_current_policy() is None

        path_str = str(self.test_file)

        # Edit should succeed without read because no policy is set
        # (This is important for backward compatibility or other modes)
        result = await edit_file_snippet(
            path=path_str, old_content="pass", new_content="return False"
        )

        assert result.success
        assert "return False" in self.test_file.read_text()
