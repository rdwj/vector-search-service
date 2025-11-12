import asyncio
from typing import AsyncGenerator, Optional
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy import text
from src.config.settings import Settings
from src.db.models import Base
import logging

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.engine = None
        self.session_factory = None
        
    async def initialize(self):
        """Initialize database connection and create tables with retry/backoff"""
        # Create async engine with reduced pool size to prevent OOM
        self.engine = create_async_engine(
            self.settings.database_url,
            echo=self.settings.debug,
            poolclass=StaticPool if "sqlite" in self.settings.database_url else None,
            pool_size=self.settings.db_pool_size,
            max_overflow=self.settings.db_max_overflow,
            pool_pre_ping=True,
            pool_recycle=self.settings.db_pool_recycle,
            pool_timeout=self.settings.db_pool_timeout
        )

        # Create session factory
        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

        # Retry loop waiting for Postgres readiness
        import asyncio
        max_attempts = int(getattr(self.settings, "db_connect_retries", 30))
        delay_seconds = int(getattr(self.settings, "db_connect_retry_delay", 5))

        last_error: Optional[Exception] = None
        for attempt in range(1, max_attempts + 1):
            try:
                async with self.engine.begin() as conn:
                    await conn.run_sync(Base.metadata.create_all)
                await self._verify_pgvector()
                logger.info("Database initialized successfully")
                return
            except Exception as e:
                last_error = e
                logger.warning(
                    f"DB not ready (attempt {attempt}/{max_attempts}): {e}. "
                    f"Retrying in {delay_seconds}s..."
                )
                await asyncio.sleep(delay_seconds)

        logger.error(f"Database initialization failed after retries: {last_error}")
        raise last_error if last_error else RuntimeError("DB init failed")
    
    async def _verify_pgvector(self):
        """Verify pgvector extension is available"""
        try:
            async with self.get_session_context() as session:
                result = await session.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'"))
                if not result.fetchone():
                    raise RuntimeError("pgvector extension not found")
                logger.info("pgvector extension verified")
        except Exception as e:
            logger.error(f"pgvector verification failed: {e}")
            raise
    
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get async database session"""
        if not self.session_factory:
            raise RuntimeError("Database not initialized")
            
        async with self.session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    
    @asynccontextmanager
    async def get_session_context(self) -> AsyncSession:
        """Get async database session as context manager"""
        if not self.session_factory:
            raise RuntimeError("Database not initialized")
            
        async with self.session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
    
    async def health_check(self) -> bool:
        """Check database health"""
        try:
            async with self.get_session_context() as session:
                await session.execute(text("SELECT 1"))
                return True
        except Exception:
            return False
    
    async def close(self):
        """Close database connections"""
        if self.engine:
            await self.engine.dispose()
            logger.info("Database connections closed")