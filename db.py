import os
import ssl
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# 👇 Required for NeonDB (enables SSL manually for asyncpg)
ssl_context = ssl.create_default_context()

engine = create_async_engine(
    DATABASE_URL,
    connect_args={"ssl": ssl_context},  # 🛡️ Enable SSL for NeonDB
    echo=False,
    future=True
)

AsyncSessionLocal = sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession
)

async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
