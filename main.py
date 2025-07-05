import asyncio
from datetime import datetime
from typing import List

from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from pydantic import BaseModel

from db import get_session
from models import Depot, Truck, StoreRequest, Route, RouteStop, RequestStatus, StopType
from routing_engine import solve_initial_routes, insert_urgent_request

app = FastAPI()

websockets: List[WebSocket] = []

async def broadcast_routes(session: AsyncSession):
    result = await session.execute(
        select(Route).options(selectinload(Route.stops))
    )
    routes = result.scalars().all()
    data = []
    for route in routes:
        data.append({
            'id': route.id,
            'truck_id': route.truck_id,
            'stops': [
                {
                    'lat': stop.lat,
                    'lon': stop.lon,
                    'eta': stop.eta,
                    'stop_type': stop.stop_type.value,
                    'completed': stop.completed
                } for stop in route.stops
            ]
        })
    for ws in list(websockets):
        try:
            await ws.send_json(data)
        except Exception:
            websockets.remove(ws)

class StoreRequestIn(BaseModel):
    lat: float
    lon: float
    demand: int
    start_time: datetime
    end_time: datetime

class GPSPing(BaseModel):
    truck_id: int
    lat: float
    lon: float

@app.websocket("/ws/routes")
async def ws_route_updates(websocket: WebSocket):
    await websocket.accept()
    websockets.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        websockets.remove(websocket)

@app.post("/initialize-day")
async def initialize_day(requests: List[StoreRequestIn], session: AsyncSession = Depends(get_session)):
    depot = (await session.execute(select(Depot))).scalars().first()
    trucks = (await session.execute(select(Truck))).scalars().all()
    if not depot or not trucks:
        raise HTTPException(status_code=400, detail="Depot or trucks not configured")

    req_objs = []
    for r in requests:
        obj = StoreRequest(
            lat=r.lat,
            lon=r.lon,
            demand=r.demand,
            start_time=r.start_time,
            end_time=r.end_time,
            status=RequestStatus.pending
        )
        session.add(obj)
        req_objs.append(obj)
    await session.commit()
    await session.refresh(req_objs[0]) if req_objs else None

    routes_data = await solve_initial_routes(depot, trucks, req_objs)
    created_routes = []
    for rdata in routes_data:
        route = Route(truck_id=rdata['truck_id'])
        session.add(route)
        await session.flush()
        for stop in rdata['stops']:
            rs = RouteStop(
                route_id=route.id,
                lat=stop['lat'],
                lon=stop['lon'],
                eta=stop['eta'],
                stop_type=StopType(stop['stop_type'])
            )
            session.add(rs)
        created_routes.append(route)
    for ro in req_objs:
        ro.status = RequestStatus.accepted
    await session.commit()

    await broadcast_routes(session)
    return routes_data

@app.post("/request-pickup")
async def request_pickup(r: StoreRequestIn, session: AsyncSession = Depends(get_session)):
    depot = (await session.execute(select(Depot))).scalars().first()
    trucks = (await session.execute(select(Truck))).scalars().all()
    req_obj = StoreRequest(
        lat=r.lat,
        lon=r.lon,
        demand=r.demand,
        start_time=r.start_time,
        end_time=r.end_time,
        status=RequestStatus.pending
    )
    session.add(req_obj)
    await session.commit()

    route_data = await insert_urgent_request(depot, trucks, req_obj)
    if not route_data:
        raise HTTPException(status_code=409, detail="Infeasible request")
    route = Route(truck_id=route_data['truck_id'])
    session.add(route)
    await session.flush()
    for stop in route_data['stops']:
        rs = RouteStop(
            route_id=route.id,
            lat=stop['lat'],
            lon=stop['lon'],
            eta=stop['eta'],
            stop_type=StopType(stop['stop_type'])
        )
        session.add(rs)
    req_obj.status = RequestStatus.accepted
    await session.commit()
    await broadcast_routes(session)
    return route_data

@app.get("/routes")
async def get_routes(session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(Route).options(selectinload(Route.stops))
    )
    routes = result.scalars().all()
    data = []
    for route in routes:
        data.append({
            'id': route.id,
            'truck_id': route.truck_id,
            'stops': [
                {
                    'lat': s.lat,
                    'lon': s.lon,
                    'eta': s.eta,
                    'stop_type': s.stop_type.value,
                    'completed': s.completed
                } for s in route.stops
            ]
        })
    return data

@app.get("/routes/{truck_id}")
async def get_latest_route(truck_id: int, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(Route).where(Route.truck_id == truck_id).order_by(Route.id.desc())
    )
    route = result.scalars().first()
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    await session.refresh(route)
    return {
        'id': route.id,
        'truck_id': route.truck_id,
        'stops': [
            {
                'lat': s.lat,
                'lon': s.lon,
                'eta': s.eta,
                'stop_type': s.stop_type.value,
                'completed': s.completed
            } for s in route.stops
        ]
    }

@app.post("/complete-stop/{stop_id}")
async def complete_stop(stop_id: int, session: AsyncSession = Depends(get_session)):
    stop = await session.get(RouteStop, stop_id)
    if not stop:
        raise HTTPException(status_code=404, detail="Stop not found")
    if stop.completed:
        return {"status": "already completed"}
    stop.completed = True
    await session.commit()
    await broadcast_routes(session)
    return {"status": "completed"}

@app.post("/gps-ping")
async def gps_ping(ping: GPSPing, session: AsyncSession = Depends(get_session)):
    truck = await session.get(Truck, ping.truck_id)
    if not truck:
        raise HTTPException(status_code=404, detail="Truck not found")
    truck.current_lat = ping.lat
    truck.current_lon = ping.lon
    await session.commit()
    return {"status": "updated"}
