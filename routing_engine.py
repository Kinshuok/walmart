from datetime import datetime
from typing import List, Dict, Any
from geopy.distance import geodesic
from ortools.constraint_solver import routing_enums_pb2, pywrapcp

from models import Depot, Truck, StoreRequest, StopType


def _distance_matrix(locations: List[tuple]) -> List[List[float]]:
    matrix = []
    for from_node in locations:
        row = []
        for to_node in locations:
            row.append(geodesic(from_node, to_node).km)
        matrix.append(row)
    return matrix

async def solve_initial_routes(depot: Depot, trucks: List[Truck], requests: List[StoreRequest]) -> List[Dict[str, Any]]:
    locations = [(depot.lat, depot.lon)] + [(r.lat, r.lon) for r in requests]
    distance_matrix = _distance_matrix(locations)
    demands = [0] + [r.demand for r in requests]
    time_windows = [(0, int(1e7))] + [
        (int(r.start_time.timestamp() / 60), int(r.end_time.timestamp() / 60)) for r in requests
    ]

    manager = pywrapcp.RoutingIndexManager(len(distance_matrix), len(trucks), 0)
    routing = pywrapcp.RoutingModel(manager)

    def distance_callback(from_index, to_index):
        f = manager.IndexToNode(from_index)
        t = manager.IndexToNode(to_index)
        return int(distance_matrix[f][t] * 1000)

    transit_cb_idx = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_cb_idx)

    def demand_callback(from_index):
        node = manager.IndexToNode(from_index)
        return demands[node]

    demand_cb_idx = routing.RegisterUnaryTransitCallback(demand_callback)
    routing.AddDimensionWithVehicleCapacity(
        demand_cb_idx,
        0,
        [t.capacity for t in trucks],
        True,
        'Capacity'
    )

    speed = 50  # km/h
    def time_callback(from_index, to_index):
        f = manager.IndexToNode(from_index)
        t = manager.IndexToNode(to_index)
        dist = distance_matrix[f][t]
        return int(dist / speed * 60)

    time_cb_idx = routing.RegisterTransitCallback(time_callback)
    routing.AddDimension(time_cb_idx, 30, 100000, False, 'Time')
    time_dim = routing.GetDimensionOrDie('Time')

    for idx, window in enumerate(time_windows):
        index = routing.NodeToIndex(idx)
        time_dim.CumulVar(index).SetRange(window[0], window[1])

    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    params.time_limit.FromSeconds(5)

    solution = routing.SolveWithParameters(params)
    routes: List[Dict[str, Any]] = []
    if solution:
        for vehicle_id in range(len(trucks)):
            index = routing.Start(vehicle_id)
            stops = []
            while not routing.IsEnd(index):
                node = manager.IndexToNode(index)
                eta_minutes = solution.Min(time_dim.CumulVar(index))
                eta = datetime.utcnow().replace(microsecond=0)  # placeholder
                stop_type = StopType.depot if node == 0 else StopType.store
                lat, lon = locations[node]
                stops.append({
                    'lat': lat,
                    'lon': lon,
                    'eta': eta,
                    'stop_type': stop_type.value
                })
                index = solution.Value(routing.NextVar(index))
            stops.append({
                'lat': depot.lat,
                'lon': depot.lon,
                'eta': datetime.utcnow().replace(microsecond=0),
                'stop_type': StopType.depot.value
            })
            routes.append({'truck_id': trucks[vehicle_id].id, 'stops': stops})
    return routes

async def insert_urgent_request(depot: Depot, trucks: List[Truck], request: StoreRequest) -> Dict[str, Any] | None:
    best_truck = None
    best_dist = float('inf')
    for truck in trucks:
        if truck.available_capacity < request.demand:
            continue
        dist = geodesic((truck.current_lat, truck.current_lon), (request.lat, request.lon)).km
        if dist < best_dist:
            best_dist = dist
            best_truck = truck
    if not best_truck:
        return None
    route = {
        'truck_id': best_truck.id,
        'stops': [
            {'lat': request.lat, 'lon': request.lon, 'eta': datetime.utcnow().replace(microsecond=0), 'stop_type': StopType.store.value},
            {'lat': depot.lat, 'lon': depot.lon, 'eta': datetime.utcnow().replace(microsecond=0), 'stop_type': StopType.depot.value}
        ]
    }
    return route
