from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create a base class for declarative class definitions
Base = declarative_base()

class DatabaseSessionManager:
    """
    Manages the database session lifecycle, including creation and disposal of sessions.
    This class ensures that database connections are properly handled and closed.
    """

    def __init__(self, database_url: str):
        """
        Initialize the DatabaseSessionManager with a database URL.

        :param database_url: The database URL for SQLAlchemy to connect to.
        """
        self._database_url = database_url
        self._engine = None
        self._session_factory = None

    def _create_engine(self) -> None:
        """
        Create a SQLAlchemy engine using the provided database URL.
        """
        try:
            self._engine = create_engine(self._database_url, echo=True)
            logger.info("SQLAlchemy engine created successfully.")
        except Exception as e:
            logger.error(f"Failed to create SQLAlchemy engine: {e}")
            raise

    def _create_session_factory(self) -> None:
        """
        Create a session factory using the SQLAlchemy engine.
        """
        if not self._engine:
            self._create_engine()
        try:
            self._session_factory = scoped_session(sessionmaker(bind=self._engine))
            logger.info("Session factory created successfully.")
        except Exception as e:
            logger.error(f"Failed to create session factory: {e}")
            raise

    def get_session(self):
        """
        Get a new session from the session factory.

        :return: A new SQLAlchemy session.
        """
        if not self._session_factory:
            self._create_session_factory()
        try:
            session = self._session_factory()
            logger.info("New session created successfully.")
            return session
        except Exception as e:
            logger.error(f"Failed to create a new session: {e}")
            raise

    def dispose_engine(self) -> None:
        """
        Dispose of the SQLAlchemy engine, closing all connections.
        """
        if self._engine:
            try:
                self._engine.dispose()
                logger.info("SQLAlchemy engine disposed successfully.")
            except Exception as e:
                logger.error(f"Failed to dispose SQLAlchemy engine: {e}")
                raise

# Example usage:
# db_manager = DatabaseSessionManager("sqlite:///example.db")
# session = db_manager.get_session()
# # Use the session to interact with the database
# session.close()
# db_manager.dispose_engine()