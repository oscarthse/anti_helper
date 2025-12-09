import unittest
from unittest.mock import patch, MagicMock
from services.user_service import UserService
from models.user import User

class TestUserService(unittest.TestCase):
    """
    Unit tests for the UserService class to verify CRUD operations.
    """

    def setUp(self) -> None:
        """
        Set up the test case environment.
        """
        self.user_service = UserService()
        self.mock_user = User(id=1, name="Test User", email="testuser@example.com")

    @patch('services.user_service.UserRepository')
    def test_create_user(self, MockUserRepository: MagicMock) -> None:
        """
        Test creating a user.
        """
        mock_repo_instance = MockUserRepository.return_value
        mock_repo_instance.create_user.return_value = self.mock_user

        created_user = self.user_service.create_user(name="Test User", email="testuser@example.com")

        self.assertEqual(created_user, self.mock_user)
        mock_repo_instance.create_user.assert_called_once_with(name="Test User", email="testuser@example.com")

    @patch('services.user_service.UserRepository')
    def test_get_user(self, MockUserRepository: MagicMock) -> None:
        """
        Test retrieving a user by ID.
        """
        mock_repo_instance = MockUserRepository.return_value
        mock_repo_instance.get_user.return_value = self.mock_user

        user = self.user_service.get_user(user_id=1)

        self.assertEqual(user, self.mock_user)
        mock_repo_instance.get_user.assert_called_once_with(user_id=1)

    @patch('services.user_service.UserRepository')
    def test_update_user(self, MockUserRepository: MagicMock) -> None:
        """
        Test updating a user's information.
        """
        mock_repo_instance = MockUserRepository.return_value
        updated_user = User(id=1, name="Updated User", email="updateduser@example.com")
        mock_repo_instance.update_user.return_value = updated_user

        user = self.user_service.update_user(user_id=1, name="Updated User", email="updateduser@example.com")

        self.assertEqual(user, updated_user)
        mock_repo_instance.update_user.assert_called_once_with(user_id=1, name="Updated User", email="updateduser@example.com")

    @patch('services.user_service.UserRepository')
    def test_delete_user(self, MockUserRepository: MagicMock) -> None:
        """
        Test deleting a user by ID.
        """
        mock_repo_instance = MockUserRepository.return_value
        mock_repo_instance.delete_user.return_value = True

        result = self.user_service.delete_user(user_id=1)

        self.assertTrue(result)
        mock_repo_instance.delete_user.assert_called_once_with(user_id=1)

if __name__ == '__main__':
    unittest.main()