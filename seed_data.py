from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from db import engine, AsyncSessionLocal
from models import Depot, Truck

import asyncio

async def seed():
    async with AsyncSessionLocal() as session:
        # Clear old data safely using raw SQL wrapped in `text()`
        await session.execute(text('DELETE FROM route_stops'))
        await session.execute(text('DELETE FROM routes'))
        await session.execute(text('DELETE FROM store_requests'))
        await session.execute(text('DELETE FROM trucks'))
        await session.execute(text('DELETE FROM depots'))
        await session.commit()

        # Create depot
        depot = Depot(lat=28.7041, lon=77.1025)
        session.add(depot)

        # Create trucks
        trucks = [
            Truck(id=1, capacity=100, available_capacity=100, current_lat=28.7041, current_lon=77.1025),
            Truck(id=2, capacity=120, available_capacity=120, current_lat=28.7041, current_lon=77.1025),
        ]
        session.add_all(trucks)

        await session.commit()
        print("Depot and trucks seeded successfully.")

if __name__ == "__main__":
    asyncio.run(seed())
