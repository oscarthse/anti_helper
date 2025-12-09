"""
This module contains route definitions for the application.

Each route corresponds to a specific endpoint in the API.
"""

from fastapi import APIRouter, HTTPException
from backend.models import ExampleModel

router = APIRouter()

@router.get("/example/{item_id}", response_model=ExampleModel)
def read_example(item_id: int) -> ExampleModel:
    """
    Retrieve an example item by its ID.

    Args:
        item_id (int): The ID of the item to retrieve.

    Returns:
        ExampleModel: The retrieved item.

    Raises:
        HTTPException: If the item is not found.
    """
    try:
        # Simulate database retrieval
        if item_id == 1:
            return ExampleModel(id=item_id, name="Sample Item")
        else:
            raise HTTPException(status_code=404, detail="Item not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))