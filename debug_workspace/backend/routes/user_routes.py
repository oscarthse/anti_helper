import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Define a Pydantic model for the User
class User(BaseModel):
    id: int
    name: str
    email: str


# Simulated database
fake_user_db = {
    1: {"name": "John Doe", "email": "john.doe@example.com"},
    2: {"name": "Jane Smith", "email": "jane.smith@example.com"},
}

# Create a FastAPI router
router = APIRouter()


@router.get("/users/", response_model=list[User])
def get_users() -> list[User]:
    """
    Retrieve a list of all users.
    """
    logger.info("Fetching all users")
    try:
        users = [User(id=user_id, **user_data) for user_id, user_data in fake_user_db.items()]
        return users
    except Exception as e:
        logger.error(f"Error fetching users: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.get("/users/{user_id}", response_model=User)
def get_user(user_id: int) -> User:
    """
    Retrieve a user by their ID.
    """
    logger.info(f"Fetching user with ID: {user_id}")
    try:
        if user_id in fake_user_db:
            user_data = fake_user_db[user_id]
            return User(id=user_id, **user_data)
        else:
            raise HTTPException(status_code=404, detail="User not found")
    except HTTPException as e:
        logger.warning(f"User not found: {user_id}")
        raise e
    except Exception as e:
        logger.error(f"Error fetching user: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.post("/users/", response_model=User, status_code=201)
def create_user(user: User) -> User:
    """
    Create a new user.
    """
    logger.info(f"Creating user: {user}")
    try:
        if user.id in fake_user_db:
            raise HTTPException(status_code=400, detail="User already exists")
        fake_user_db[user.id] = {"name": user.name, "email": user.email}
        return user
    except HTTPException as e:
        logger.warning(f"User already exists: {user.id}")
        raise e
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.put("/users/{user_id}", response_model=User)
def update_user(user_id: int, user: User) -> User:
    """
    Update an existing user.
    """
    logger.info(f"Updating user with ID: {user_id}")
    try:
        if user_id in fake_user_db:
            fake_user_db[user_id] = {"name": user.name, "email": user.email}
            return User(id=user_id, **fake_user_db[user_id])
        else:
            raise HTTPException(status_code=404, detail="User not found")
    except HTTPException as e:
        logger.warning(f"User not found for update: {user_id}")
        raise e
    except Exception as e:
        logger.error(f"Error updating user: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: int) -> None:
    """
    Delete a user by their ID.
    """
    logger.info(f"Deleting user with ID: {user_id}")
    try:
        if user_id in fake_user_db:
            del fake_user_db[user_id]
        else:
            raise HTTPException(status_code=404, detail="User not found")
    except HTTPException as e:
        logger.warning(f"User not found for deletion: {user_id}")
        raise e
    except Exception as e:
        logger.error(f"Error deleting user: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
