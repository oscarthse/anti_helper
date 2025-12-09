import unittest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from models import Base, User

class TestUserModel(unittest.TestCase):
    """
    Unit tests for the User model to ensure correct ORM mapping and constraints.
    """

    @classmethod
    def setUpClass(cls):
        """
        Set up a temporary in-memory database for testing.
        """
        cls.engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(cls.engine)
        cls.Session = sessionmaker(bind=cls.engine)

    def setUp(self):
        """
        Create a new session for each test.
        """
        self.session = self.Session()

    def tearDown(self):
        """
        Rollback any changes made during the test.
        """
        self.session.rollback()
        self.session.close()

    def test_user_creation(self):
        """
        Test that a User can be created and persisted.
        """
        user = User(username='testuser', email='test@example.com', password='securepassword')
        self.session.add(user)
        self.session.commit()

        retrieved_user = self.session.query(User).filter_by(username='testuser').one()
        self.assertEqual(retrieved_user.email, 'test@example.com')

    def test_username_uniqueness(self):
        """
        Test that the username field is unique.
        """
        user1 = User(username='uniqueuser', email='unique1@example.com', password='password1')
        user2 = User(username='uniqueuser', email='unique2@example.com', password='password2')
        self.session.add(user1)
        self.session.commit()

        with self.assertRaises(IntegrityError):
            self.session.add(user2)
            self.session.commit()

    def test_email_uniqueness(self):
        """
        Test that the email field is unique.
        """
        user1 = User(username='user1', email='unique@example.com', password='password1')
        user2 = User(username='user2', email='unique@example.com', password='password2')
        self.session.add(user1)
        self.session.commit()

        with self.assertRaises(IntegrityError):
            self.session.add(user2)
            self.session.commit()

    def test_password_not_null(self):
        """
        Test that the password field cannot be null.
        """
        user = User(username='user3', email='user3@example.com', password=None)
        self.session.add(user)

        with self.assertRaises(IntegrityError):
            self.session.commit()

if __name__ == '__main__':
    unittest.main()
