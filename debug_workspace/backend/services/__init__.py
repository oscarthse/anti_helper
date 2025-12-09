"""
This module contains service layer logic for the application.

Services handle business logic and interact with data models.
"""

from backend.models import ExampleModel

class ExampleService:
    """
    ExampleService provides business logic for example operations.
    """

    def get_example(self, item_id: int) -> ExampleModel:
        """
        Retrieve an example item by its ID.

        Args:
            item_id (int): The ID of the item to retrieve.

        Returns:
            ExampleModel: The retrieved item.

        Raises:
            ValueError: If the item is not found.
        """
        # Simulate business logic
        if item_id == 1:
            return ExampleModel(id=item_id, name="Sample Item")
        else:
            raise ValueError("Item not found")