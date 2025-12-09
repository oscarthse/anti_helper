from typing import Optional, Dict, Any
from uuid import UUID, uuid4
import logging

# Mock database
class MockDatabase:
    def __init__(self):
        self.users = {}

    def add_user(self, user_id: UUID, user_data: Dict[str, Any]) -> None:
        self.users[user_id] = user_data

    def get_user(self, user_id: UUID) -> Optional[Dict[str, Any]]:
        return self.users.get(user_id)

    def update_user(self, user_id: UUID, user_data: Dict[str, Any]) -> bool:
        if user_id in self.users:
            self.users[user_id].update(user_data)
            return True
        return False

    def delete_user(self, user_id: UUID) -> bool:
        if user_id in self.users:
            del self.users[user_id]
            return True
        return False

# Service layer for user operations
class UserService:
    def __init__(self, database: MockDatabase):
        """
        Initialize the UserService with a given database.

        :param database: An instance of a database interface.
        """
        self._database = database

    def create_user(self, user_data: Dict[str, Any]) -> UUID:
        """
        Create a new user with the provided data.

        :param user_data: A dictionary containing user information.
        :return: The UUID of the newly created user.
        """
        user_id = uuid4()
        try:
            self._database.add_user(user_id, user_data)
            logging.info(f"User created with ID: {user_id}")
        except Exception as e:
            logging.error(f"Failed to create user: {e}")
            raise
        return user_id

    def get_user(self, user_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Retrieve a user's information by their UUID.

        :param user_id: The UUID of the user to retrieve.
        :return: A dictionary of the user's information, or None if not found.
        """
        try:
            user = self._database.get_user(user_id)
            if user is None:
                logging.warning(f"User with ID {user_id} not found.")
            return user
        except Exception as e:
            logging.error(f"Failed to retrieve user: {e}")
            raise

    def update_user(self, user_id: UUID, user_data: Dict[str, Any]) -> bool:
        """
        Update an existing user's information.

        :param user_id: The UUID of the user to update.
        :param user_data: A dictionary of the user's updated information.
        :return: True if the update was successful, False otherwise.
        """
        try:
            success = self._database.update_user(user_id, user_data)
            if success:
                logging.info(f"User with ID {user_id} updated successfully.")
            else:
                logging.warning(f"User with ID {user_id} not found for update.")
            return success
        except Exception as e:
            logging.error(f"Failed to update user: {e}")
            raise

    def delete_user(self, user_id: UUID) -> bool:
        """
        Delete a user by their UUID.

        :param user_id: The UUID of the user to delete.
        :return: True if the user was successfully deleted, False otherwise.
        """
        try:
            success = self._database.delete_user(user_id)
            if success:
                logging.info(f"User with ID {user_id} deleted successfully.")
            else:
                logging.warning(f"User with ID {user_id} not found for deletion.")
            return success
        except Exception as e:
            logging.error(f"Failed to delete user: {e}")
            raise