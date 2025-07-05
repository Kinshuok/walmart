import asyncio
import httpx

API_URL = "http://localhost:8000"

async def simulate():
    async with httpx.AsyncClient() as client:
        while True:
            resp = await client.get(f"{API_URL}/routes")
            routes = resp.json()
            for route in routes:
                truck_id = route['truck_id']
                for stop in route['stops']:
                    await client.post(f"{API_URL}/gps-ping", json={
                        'truck_id': truck_id,
                        'lat': stop['lat'],
                        'lon': stop['lon']
                    })
                    await asyncio.sleep(30)
            await asyncio.sleep(30)

if __name__ == "__main__":
    asyncio.run(simulate())
