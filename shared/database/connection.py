"""
Database connection and session management.

Provides async database access using SQLAlchemy + aiosqlite.
"""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator, Optional

from loguru import logger
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from .models import Base


class Database:
    """
    Database manager for 100AC.
    
    Handles:
    - Connection management
    - Session creation
    - Schema initialization
    """
    
    def __init__(self, database_url: Optional[str] = None):
        """
        Initialize database connection.
        
        Args:
            database_url: Database connection string. 
                         Defaults to sqlite+aiosqlite:///./100ac.db
        """
        if database_url is None:
            db_path = Path(__file__).parent.parent.parent / "100ac.db"
            database_url = f"sqlite+aiosqlite:///{db_path}"
        
        self.database_url = database_url
        self.engine: Optional[AsyncEngine] = None
        self.session_factory: Optional[async_sessionmaker] = None
        
        logger.info(f"Database configured: {database_url}")
    
    async def initialize(self) -> None:
        """Initialize database engine and create tables."""
        if self.engine is not None:
            logger.warning("Database already initialized")
            return
        
        # Create engine
        self.engine = create_async_engine(
            self.database_url,
            echo=False,  # Set to True for SQL debugging
            future=True,
        )
        
        # Create session factory
        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        
        # Create all tables
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        logger.info("Database initialized successfully")
    
    async def close(self) -> None:
        """Close database connections."""
        if self.engine:
            await self.engine.dispose()
            self.engine = None
            self.session_factory = None
            logger.info("Database connections closed")
    
    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Get a database session.
        
        Usage:
            async with db.get_session() as session:
                result = await session.execute(query)
        """
        if self.session_factory is None:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        
        async with self.session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    
    async def execute_raw(self, sql: str) -> None:
        """
        Execute raw SQL statement.
        
        Args:
            sql: SQL statement to execute
        """
        if self.engine is None:
            raise RuntimeError("Database not initialized")
        
        async with self.engine.begin() as conn:
            await conn.execute(sql)


# Global database instance
_database: Optional[Database] = None


def get_database() -> Database:
    """Get the global database instance."""
    global _database
    if _database is None:
        _database = Database()
    return _database


def init_database(database_url: Optional[str] = None) -> Database:
    """Initialize the global database instance."""
    global _database
    _database = Database(database_url)
    return _database
