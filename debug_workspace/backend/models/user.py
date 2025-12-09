from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define the base class for declarative class definitions
Base = declarative_base()

class User(Base):
    """
    User model for storing user information.
    Attributes:
        id (int): The unique identifier for the user.
        name (str): The name of the user.
        email (str): The email address of the user.
    """

    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)
    email = Column(String(100), nullable=False, unique=True)

    def __init__(self, name: str, email: str):
        """
        Initialize a User instance.
        Args:
            name (str): The name of the user.
            email (str): The email address of the user.
        """
        self.name = name
        self.email = email

    def __repr__(self) -> str:
        """
        Return a string representation of the User instance.
        Returns:
            str: The string representation of the User instance.
        """
        return f"<User(id={self.id}, name={self.name}, email={self.email})>"

# Example setup for database engine and session
# This would typically be in a separate configuration or main application file
# engine = create_engine('sqlite:///example.db', echo=True)
# Base.metadata.create_all(engine)
# Session = sessionmaker(bind=engine)
# session = Session()