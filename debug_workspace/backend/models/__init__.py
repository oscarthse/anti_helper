"""
This module contains data models for the application.

Each model represents a table in the database and is responsible for data validation and serialization.
"""

from pydantic import BaseModel

class ExampleModel(BaseModel):
    """
    ExampleModel is a sample data model for demonstration purposes.

    Attributes:
        id (int): The unique identifier for the model.
        name (str): The name associated with the model.
    """
    id: int
    name: str

    def to_dict(self) -> dict:
        """
        Convert the model instance to a dictionary.

        Returns:
            dict: A dictionary representation of the model instance.
        """
        return self.dict()