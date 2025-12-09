"""
Referee - The Contract Enforcer.

This module validates that a task has actually met its 'Definition of Done'.
It prevents 'Hallucinated Success' (claiming a file exists when it doesn't).

It is a deterministic, logic-only component.
"""

from pathlib import Path
from typing import Any


class Referee:
    """
    Validates post-conditions (Contracts) for tasks.
    """

    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)

    def validate_contract(self, contract: dict[str, Any] | None) -> tuple[bool, str | None]:
        """
        Check if the contract is satisfied.

        Args:
            contract: Dictionary like {"required_files": ["app/main.py"]}

        Returns:
            (success, error_message)
        """
        if not contract:
            return True, None

        # 1. Check Required Files
        required_files = contract.get("required_files", [])
        for file_rel_path in required_files:
            file_path = self.repo_path / file_rel_path
            if not file_path.exists():
                return (
                    False,
                    f"Contract Violation: Required file '{file_rel_path}' was not created.",
                )

        # 2. Future: Check required_tests_passed (parse JUnit/Pytest XML?)
        # 3. Future: Check required_symbols (AST check)

        return True, None
