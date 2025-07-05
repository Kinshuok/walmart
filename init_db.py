import asyncio
from db import engine
from models import Base  # your SQLAlchemy Base where all models are defined

async def init():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Database initialized.")

if __name__ == "__main__":
    asyncio.run(init())
