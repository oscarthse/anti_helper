import asyncio

from gravity_core.tools.policies import (
    FileAccessPolicy,
    clear_current_policy,
    get_current_policy,
    set_current_policy,
)


class TestFileAccessPolicy:
    def test_normalize_path(self):
        policy = FileAccessPolicy()
        # Test basic normalization
        assert policy._normalize_path("foo.py").endswith("/foo.py")
        assert policy._normalize_path("/abs/path/foo.py") == "/abs/path/foo.py"

    def test_record_read_allows_edit(self):
        policy = FileAccessPolicy()
        path = "/tmp/test_file.py"

        # Initially not editable
        assert not policy.can_edit(path)

        # Record read
        policy.record_read(path)

        # Now editable
        assert policy.can_edit(path)

    def test_create_always_allowed(self):
        policy = FileAccessPolicy()
        path = "/tmp/new_file.py"
        assert policy.can_create(path)

    def test_reset_clears_state(self):
        policy = FileAccessPolicy()
        policy.record_read("/tmp/file.py")
        assert policy.can_edit("/tmp/file.py")

        policy.reset()
        assert not policy.can_edit("/tmp/file.py")


class TestPolicyContextVars:
    async def test_policy_context_isolation(self):
        """Verify that policies are isolated between async tasks."""

        async def task_a():
            policy_a = FileAccessPolicy()
            set_current_policy(policy_a)
            policy_a.record_read("/a.py")

            # Yield to let other tasks run
            await asyncio.sleep(0.01)

            # Verify context is still policy_a
            current = get_current_policy()
            assert current is policy_a
            assert current.can_edit("/a.py")
            assert not current.can_edit("/b.py")

        async def task_b():
            policy_b = FileAccessPolicy()
            set_current_policy(policy_b)
            policy_b.record_read("/b.py")

            # Yield to let other tasks run
            await asyncio.sleep(0.01)

            # Verify context is still policy_b
            current = get_current_policy()
            assert current is policy_b
            assert current.can_edit("/b.py")
            assert not current.can_edit("/a.py")

        # Run both concurrently
        await asyncio.gather(task_a(), task_b())

        # Ensure context is cleared/reset in parent scope if not set
        # (This depends on how pytest-asyncio handles top-level context,
        # but locally created vars shouldn't leak upwards easily)

    def test_get_current_return_none_by_default(self):
        # We must ensure we start clean.
        # Since other tests might have run, explicitly clear first if needed,
        # but the default contextvar should be empty in a fresh context.
        # However, pytest runs in one process.

        # Explicit clear for test hygiene
        clear_current_policy()
        assert get_current_policy() is None
