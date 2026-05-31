from __future__ import annotations

import itertools
import math
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

try:
    import networkx as nx
except ImportError:
    print("NetworkX is required. Install it with: pip install networkx")
    sys.exit(1)

try:
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

try:
    import folium
    FOLIUM_AVAILABLE = True
except ImportError:
    FOLIUM_AVAILABLE = False

try:
    import tkinter as tk
    from tkinter import ttk, messagebox
    TKINTER_AVAILABLE = True
except ImportError:
    TKINTER_AVAILABLE = False

# CONFIGURATION
WIDTH = 78
BASE_FARE = 80.0                # Rs fixed starting fare
RATE_PER_KM = 45.0              # Rs per km
RATE_PER_MIN = 8.0              # Rs per minute
SHARED_DISCOUNT = 0.20          # 20% discount for shared passenger fare
AVERAGE_SPEED_KMH = 35.0        # used for ETA in this project simulation
DETOUR_LIMIT = 0.40             # max 40% passenger detour for shared rides
MAX_PICKUP_DISTANCE_KM = 9.0    # shared pickup areas should be reasonably close
MAX_DROP_DISTANCE_KM = 14.0     # shared drop areas should be same/general direction
LIVE_DELAY_SECONDS = 0.35       # lower this to 0 for instant output
MAX_DRIVER_CAPACITY = 4
MAX_CONSOLE_PASSENGERS = 12
MAX_CONSOLE_DRIVERS = 3

#UI HELPERS
def line() -> None:
    print("-" * WIDTH)

def title(text: str) -> None:
    line()
    print(text.center(WIDTH))
    line()

def section(text: str) -> None:
    print("\n" + text.center(WIDTH))
    line()

def now_text() -> str:
    return datetime.now().strftime("%H:%M:%S")

class EventLog:
    def __init__(self) -> None:
        self.events: List[str] = []

    def add(self, message: str) -> None:
        entry = f"[{now_text()}] {message}"
        self.events.append(entry)
        print(f"  {entry}")

    def print_final(self) -> None:
        section("REAL-TIME EVENT LOG")
        if not self.events:
            print("  No events recorded.")
            return
        for event in self.events:
            print(f"  {event}")

EVENT_LOG = EventLog()

#REAL MAP DATA 
location_names: Dict[int, str] = {
    0: "Faizabad",
    1: "Chandni Chowk",
    2: "F-10 Markaz",
    3: "G-9 Markaz",
    4: "Centaurus",
    5: "Blue Area",
    6: "F-6 Supermarket",
    7: "F-7 Markaz",
    8: "Pir Wadhai",
    9: "Saddar Rawalpindi",
    10: "Committee Chowk",
    11: "Peshawar Morr",
    12: "Zero Point",
    13: "Bahria Town",
    14: "DHA Phase 2",
}

#Latitude, longitude
location_coords: Dict[int, Tuple[float, float]] = {
    0: (33.7215, 73.0433),
    1: (33.7294, 73.0551),
    2: (33.7060, 72.9918),
    3: (33.6982, 73.0308),
    4: (33.7077, 73.0454),
    5: (33.7175, 73.0690),
    6: (33.7253, 73.0514),
    7: (33.7202, 73.0448),
    8: (33.6361, 73.1083),
    9: (33.5979, 73.0552),
    10: (33.6133, 73.0712),
    11: (33.7320, 73.0121),
    12: (33.7238, 73.0581),
    13: (33.5477, 73.1867),
    14: (33.5590, 73.1156),
}

ROAD_EDGES: List[Tuple[int, int]] = [
    #Islamabad core realistic local links
    (7, 6),      # F-7 Markaz ↔ F-6 Supermarket
    (7, 4),      # F-7 Markaz ↔ Centaurus
    (7, 5),      # F-7 Markaz ↔ Blue Area
    (6, 5),      # F-6 Supermarket ↔ Blue Area
    (5, 4),      # Blue Area ↔ Centaurus
    (4, 3),      # Centaurus ↔ G-9 Markaz
    (3, 2),      # G-9 Markaz ↔ F-10 Markaz
    (2, 7),      # F-10 Markaz ↔ F-7 Markaz
    (3, 12),     # G-9 Markaz ↔ Zero Point
    (5, 12),     # Blue Area ↔ Zero Point
    (1, 12),     # Chandni Chowk ↔ Zero Point
    (11, 12),    # Peshawar Morr ↔ Zero Point
    (11, 2),     # Peshawar Morr ↔ F-10 Markaz
    (11, 3),     # Peshawar Morr ↔ G-9 Markaz

    #Islamabad / Rawalpindi connector links
    (12, 0),     # Zero Point ↔ Faizabad
    (0, 1),      # Faizabad ↔ Chandni Chowk
    (0, 10),     # Faizabad ↔ Committee Chowk
    (1, 10),     # Chandni Chowk ↔ Committee Chowk
    (1, 8),      # Chandni Chowk ↔ Pir Wadhai

    #Rawalpindi links
    (8, 10),     # Pir Wadhai ↔ Committee Chowk
    (8, 9),      # Pir Wadhai ↔ Saddar
    (10, 9),     # Committee Chowk ↔ Saddar
    (9, 14),     # Saddar ↔ DHA Phase 2
    (10, 14),    # Committee Chowk ↔ DHA Phase 2
    (14, 13),    # DHA Phase 2 ↔ Bahria Town
    (9, 13),     # Saddar ↔ Bahria Town
]

def haversine_km(a: int, b: int) -> float:
    lat1, lon1 = location_coords[a]
    lat2, lon2 = location_coords[b]
    radius = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    x = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * radius * math.atan2(math.sqrt(x), math.sqrt(1 - x))

def build_graph() -> nx.Graph:
    graph = nx.Graph()
    for node, name in location_names.items():
        lat, lon = location_coords[node]
        # NetworkX layout uses x,y, so store lon,lat for map-like plotting.
        graph.add_node(node, name=name, pos=(lon, lat))
    for u, v in ROAD_EDGES:
        # Road routes are rarely perfectly straight, so multiply by 1.18.
        road_km = haversine_km(u, v) * 1.18
        graph.add_edge(u, v, weight=round(road_km, 2))
    return graph

G = build_graph()
assert not G.has_edge(7, 0), "Unexpected F-7 ↔ Faizabad shortcut still exists."
positions = nx.get_node_attributes(G, "pos")

PLOT_POSITIONS: Dict[int, Tuple[float, float]] = {
    11: (0.6, 8.6),
    2:  (0.4, 5.9),
    7:  (1.9, 7.1),
    3:  (1.8, 4.5),
    4:  (4.6, 5.6),
    12: (5.0, 7.6),
    1:  (6.8, 6.2),
    6:  (8.4, 7.7),
    5:  (8.0, 4.8),
    0:  (5.7, 3.9),
    8:  (9.4, 2.4),
    10: (6.4, 1.5),
    9:  (4.3, 0.5),
    14: (7.9, 0.2),
    13: (10.2, 0.5),
}

NODE_SHORT_LABELS: Dict[int, str] = {
    0: "0\nFaizabad",
    1: "1\nChandni",
    2: "2\nF-10",
    3: "3\nG-9",
    4: "4\nCentaurus",
    5: "5\nBlue Area",
    6: "6\nF-6",
    7: "7\nF-7",
    8: "8\nPir Wadhai",
    9: "9\nSaddar",
    10: "10\nCommittee",
    11: "11\nPeshawar",
    12: "12\nZero Point",
    13: "13\nBahria",
    14: "14\nDHA",
}

num_nodes = len(location_names)

#SAFE ROUTING FUNCTIONS
def route_text(path: Sequence[int]) -> str:
    if not path:
        return "No route"
    return " -> ".join(location_names[n] for n in path)

def heuristic(a: int, b: int) -> float:
    return haversine_km(a, b)

def shortest_distance(a: int, b: int) -> float:
    if a == b:
        return 0.0
    try:
        return float(nx.dijkstra_path_length(G, a, b, weight="weight"))
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return float("inf")

def dijkstra_path(a: int, b: int) -> Tuple[List[int], float]:
    if a == b:
        return [a], 0.0
    try:
        path = nx.dijkstra_path(G, a, b, weight="weight")
        dist = nx.dijkstra_path_length(G, a, b, weight="weight")
        return path, float(dist)
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return [], float("inf")

def astar_path(a: int, b: int) -> Tuple[List[int], float]:
    if a == b:
        return [a], 0.0
    try:
        path = nx.astar_path(G, a, b, heuristic=heuristic, weight="weight")
        dist = nx.astar_path_length(G, a, b, heuristic=heuristic, weight="weight")
        return path, float(dist)
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return [], float("inf")

def eta_minutes(distance_km: float) -> float:
    if distance_km == float("inf"):
        return float("inf")
    return (distance_km / AVERAGE_SPEED_KMH) * 60.0

def money(value: float) -> str:
    return f"Rs. {value:,.0f}"

#DATA MODELS
class RideStatus(str, Enum):
    REQUESTED = "REQUESTED"
    ASSIGNED = "ASSIGNED"
    DRIVER_ARRIVING = "DRIVER_ARRIVING"
    PICKED_UP = "PICKED_UP"
    IN_RIDE = "IN_RIDE"
    DROPPED = "DROPPED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"

@dataclass(eq=False)
class Passenger:
    name: str
    pickup: int
    drop: int
    wants_share: bool = False
    id: int = field(init=False)
    driver: Optional["Driver"] = None
    shared: bool = False
    status: RideStatus = RideStatus.REQUESTED
    fare: float = 0.0
    eta: Optional[float] = None
    share_declined_reason: Optional[str] = None

    _counter = 0

    def __post_init__(self) -> None:
        Passenger._counter += 1
        self.id = Passenger._counter

    def __hash__(self) -> int:
        return self.id

@dataclass
class Driver:
    name: str
    vehicle: str
    node: int
    capacity: int
    id: int = field(init=False)
    passengers: List[Passenger] = field(default_factory=list)
    online: bool = True

    _counter = 0

    def __post_init__(self) -> None:
        Driver._counter += 1
        self.id = Driver._counter
        self.capacity = max(1, min(MAX_DRIVER_CAPACITY, int(self.capacity)))

    @property
    def seats_free(self) -> int:
        return self.capacity - len(self.passengers)

@dataclass
class StopEvent:
    kind: str         
    passenger: Passenger
    node: int

    @property
    def label(self) -> str:
        arrow = "PICKUP" if self.kind == "pickup" else "DROP"
        return f"{arrow}: {self.passenger.name} @ {location_names[self.node]}"

@dataclass
class TripPlan:
    events: List[StopEvent]
    stop_nodes: List[int]
    leg_paths: List[List[int]]
    leg_distances: List[float]
    total_distance: float
    full_route: List[int]

#INPUT HELPERS
def get_int_input(prompt: str, lo: int, hi: int) -> int:
    while True:
        raw = input(prompt).strip()
        try:
            val = int(raw)
            if lo <= val <= hi:
                return val
            print(f"  Please enter a number from {lo} to {hi}.")
        except ValueError:
            print("  Invalid input. Please enter a number.")

def show_locations() -> None:
    print(f"\n  {'NODE':<8}{'LOCATION':<24}{'CONNECTED ROAD DISTANCES'}")
    line()
    for i, name in location_names.items():
        neighbors = []
        for n in sorted(G.neighbors(i)):
            neighbors.append(f"{n}:{G[i][n]['weight']}km")
        print(f"  {i:<8}{name:<24}{', '.join(neighbors)}")
    print()

#TRIP OPTIMIZATION
def build_full_route(start_node: int, events: Sequence[StopEvent]) -> Tuple[List[int], List[List[int]], List[float], float]:
    current = start_node
    full_route = [start_node]
    leg_paths: List[List[int]] = []
    leg_distances: List[float] = []
    total = 0.0

    for event in events:
        path, dist = astar_path(current, event.node)
        if not path or dist == float("inf"):
            return [], [], [], float("inf")
        leg_paths.append(path)
        leg_distances.append(dist)
        total += dist
        if len(path) > 1:
            full_route.extend(path[1:])
        current = event.node

    return full_route, leg_paths, leg_distances, total

def valid_event_order(events: Sequence[StopEvent]) -> bool:
    picked = set()
    for event in events:
        pid = event.passenger.id
        if event.kind == "pickup":
            picked.add(pid)
        elif pid not in picked:
            return False
    return True

def best_trip_plan(start_node: int, passengers: Sequence[Passenger]) -> Optional[TripPlan]:
    if not passengers:
        return TripPlan([], [], [], [], 0.0, [start_node])

    events: List[StopEvent] = []
    for p in passengers:
        events.append(StopEvent("pickup", p, p.pickup))
        events.append(StopEvent("drop", p, p.drop))

    best_events: Optional[List[StopEvent]] = None
    best_route: List[int] = []
    best_leg_paths: List[List[int]] = []
    best_leg_distances: List[float] = []
    best_total = float("inf")

    seen_orders = set()
    for perm in itertools.permutations(events):
        key = tuple((e.kind, e.passenger.id) for e in perm)
        if key in seen_orders:
            continue
        seen_orders.add(key)
        if not valid_event_order(perm):
            continue
        full_route, leg_paths, leg_distances, total = build_full_route(start_node, perm)
        if total < best_total:
            best_total = total
            best_events = list(perm)
            best_route = full_route
            best_leg_paths = leg_paths
            best_leg_distances = leg_distances

    if best_events is None or best_total == float("inf"):
        return None

    return TripPlan(
        events=best_events,
        stop_nodes=[e.node for e in best_events],
        leg_paths=best_leg_paths,
        leg_distances=best_leg_distances,
        total_distance=best_total,
        full_route=best_route,
    )

def passenger_direct_distance(p: Passenger) -> float:
    return shortest_distance(p.pickup, p.drop)

def passenger_experience_distance(plan: TripPlan, passenger: Passenger) -> float:
    inside = False
    total = 0.0
    prev_node: Optional[int] = None

    for idx, event in enumerate(plan.events):
        # The leg ending at this event has index idx.
        if idx < len(plan.leg_distances):
            leg_dist = plan.leg_distances[idx]
        else:
            leg_dist = 0.0

        #If passenger was already inside before reaching this event, this leg counts.
        if inside:
            total += leg_dist

        if event.passenger.id == passenger.id and event.kind == "pickup":
            inside = True
        elif event.passenger.id == passenger.id and event.kind == "drop":
            inside = False
            break

        prev_node = event.node

    return total

def pairwise_max_distance(passengers: Sequence[Passenger], attr: str) -> float:
    nodes = [getattr(p, attr) for p in passengers]
    if len(nodes) <= 1:
        return 0.0
    max_dist = 0.0
    for a, b in itertools.combinations(nodes, 2):
        max_dist = max(max_dist, shortest_distance(a, b))
    return max_dist

def group_compatibility(driver_node: int, passengers: Sequence[Passenger]) -> Tuple[bool, str, Optional[TripPlan]]:
    if not passengers:
        return False, "No passengers selected.", None

    if len(passengers) == 1:
        plan = best_trip_plan(driver_node, passengers)
        if plan is None:
            return False, "No route found for this passenger.", None
        return True, "Solo ride is valid.", plan

    if len(passengers) > MAX_DRIVER_CAPACITY:
        return False, "Group is larger than maximum vehicle capacity.", None

    if any(not p.wants_share for p in passengers):
        return False, "One or more passengers did not opt in to sharing.", None

    pickup_spread = pairwise_max_distance(passengers, "pickup")
    if pickup_spread > MAX_PICKUP_DISTANCE_KM:
        return False, f"Pickup locations are too far apart ({pickup_spread:.1f} km).", None

    drop_spread = pairwise_max_distance(passengers, "drop")
    if drop_spread > MAX_DROP_DISTANCE_KM:
        return False, f"Drop locations are too far apart ({drop_spread:.1f} km).", None

    plan = best_trip_plan(driver_node, passengers)
    if plan is None:
        return False, "No valid shared route found.", None

    for p in passengers:
        direct = passenger_direct_distance(p)
        experienced = passenger_experience_distance(plan, p)
        if direct == float("inf") or direct <= 0:
            return False, f"No direct route found for {p.name}.", None
        detour_ratio = (experienced - direct) / direct
        if detour_ratio > DETOUR_LIMIT:
            return (
                False,
                f"{p.name}'s detour is too high ({detour_ratio * 100:.1f}% > {DETOUR_LIMIT * 100:.0f}%).",
                None,
            )

    return True, "Shared group is compatible using pickup/drop proximity and detour check.", plan

#DRIVER ASSIGNMENT
def nearest_waiting_passenger(driver: Driver, waiting_pool: Sequence[Passenger]) -> Optional[Passenger]:
    if not waiting_pool:
        return None
    return min(waiting_pool, key=lambda p: shortest_distance(driver.node, p.pickup))

def choose_best_group_for_driver(driver: Driver, waiting_pool: Sequence[Passenger]) -> Tuple[List[Passenger], str, Optional[TripPlan]]:
    base = nearest_waiting_passenger(driver, waiting_pool)
    if base is None:
        return [], "No waiting passengers.", None

    solo_ok, solo_reason, solo_plan = group_compatibility(driver.node, [base])
    if not solo_ok:
        return [], solo_reason, None

    if driver.capacity <= 1 or not base.wants_share:
        if not base.wants_share:
            base.share_declined_reason = "Passenger selected solo-only ride."
        return [base], "Nearest passenger assigned as solo.", solo_plan

    share_candidates = [p for p in waiting_pool if p is not base and p.wants_share]
    best_group = [base]
    best_plan = solo_plan
    best_reason = "No compatible share partner found; assigned nearest passenger as solo."
    best_score = (1, -solo_plan.total_distance if solo_plan else -float("inf"))

    max_group_size = min(driver.capacity, len(waiting_pool), MAX_DRIVER_CAPACITY)

    for size in range(2, max_group_size + 1):
        for partners in itertools.combinations(share_candidates, size - 1):
            group = [base, *partners]
            ok, reason, plan = group_compatibility(driver.node, group)
            if not ok or plan is None:
                # Keep a useful explanation for base passenger.
                base.share_declined_reason = reason
                continue
            #Prefer larger shared groups first, then shorter optimized route.
            score = (len(group), -plan.total_distance)
            if score > best_score:
                best_score = score
                best_group = list(group)
                best_plan = plan
                best_reason = reason

    return best_group, best_reason, best_plan

def auto_assign_passengers(driver: Driver, waiting_pool: List[Passenger]) -> Tuple[List[Passenger], str, Optional[TripPlan]]:
    group, reason, plan = choose_best_group_for_driver(driver, waiting_pool)
    if not group:
        return [], reason, plan

    is_shared = len(group) > 1
    for p in group:
        p.driver = driver
        p.shared = is_shared
        p.status = RideStatus.ASSIGNED
        if p in waiting_pool:
            waiting_pool.remove(p)
        driver.passengers.append(p)

    EVENT_LOG.add(
        f"Driver {driver.name} assigned {len(group)} passenger(s): "
        + ", ".join(p.name for p in group)
        + (" [SHARED]" if is_shared else " [SOLO]")
    )
    return group, reason, plan

#REAL-TIME SIMULATION
def print_assignment(driver: Driver, group: Sequence[Passenger], reason: str, plan: Optional[TripPlan]) -> None:
    section(f"AUTO ASSIGNMENT — DRIVER {driver.id}: {driver.name}")
    print(f"  Location : {location_names[driver.node]}")
    print(f"  Vehicle  : {driver.vehicle}")
    print(f"  Capacity : {driver.capacity} seat(s)")
    print(f"  Decision : {reason}")

    if not group:
        print("  No passenger assigned.")
        return

    ride_type = "SHARED RIDE" if len(group) > 1 else "SOLO RIDE"
    print(f"  Ride Type: {ride_type}")
    for p in group:
        print(
            f"    • {p.name:<16} {location_names[p.pickup]:<20} → "
            f"{location_names[p.drop]:<20} | Status: {p.status.value}"
        )
        if p.wants_share and not p.shared and p.share_declined_reason:
            print(f"      Share note: {p.share_declined_reason}")

    if plan:
        print(f"\n  Optimized total route distance: {plan.total_distance:.2f} km")
        print(f"  Estimated completion time     : {eta_minutes(plan.total_distance):.1f} minutes")
        print("\n  Planned stop order:")
        for idx, event in enumerate(plan.events, 1):
            print(f"    {idx}. {event.label}")

def simulate_live_trip(driver: Driver, plan: TripPlan) -> None:
    if not driver.passengers or not plan.events:
        return

    section(f"LIVE RIDE SIMULATION — DRIVER {driver.id}: {driver.name}")
    current = driver.node
    remaining_distance = plan.total_distance
    onboard: List[Passenger] = []

    for idx, event in enumerate(plan.events):
        leg_path = plan.leg_paths[idx]
        leg_dist = plan.leg_distances[idx]
        if not leg_path:
            continue

        target = event.node
        for p in driver.passengers:
            if p.status == RideStatus.ASSIGNED:
                p.status = RideStatus.DRIVER_ARRIVING

        EVENT_LOG.add(
            f"{driver.name} navigating from {location_names[current]} to {location_names[target]} "
            f"via {route_text(leg_path)} "
            f"({leg_dist:.2f} km, ETA {eta_minutes(leg_dist):.1f} min)"
        )

        # Step-by-step movement through graph nodes.
        for step_node in leg_path[1:]:
            driver.node = step_node
            print(
                f"    LIVE GPS: {driver.name} reached {location_names[step_node]:<22} | "
                f"Remaining trip ETA: {eta_minutes(max(remaining_distance, 0)):.1f} min"
            )
            if LIVE_DELAY_SECONDS > 0:
                time.sleep(LIVE_DELAY_SECONDS)

        remaining_distance -= leg_dist
        current = target

        if event.kind == "pickup":
            event.passenger.status = RideStatus.PICKED_UP
            onboard.append(event.passenger)
            EVENT_LOG.add(f"{event.passenger.name} picked up from {location_names[event.node]}.")
            for p in onboard:
                p.status = RideStatus.IN_RIDE
        else:
            event.passenger.status = RideStatus.DROPPED
            if event.passenger in onboard:
                onboard.remove(event.passenger)
            EVENT_LOG.add(f"{event.passenger.name} dropped at {location_names[event.node]}.")

    for p in driver.passengers:
        p.status = RideStatus.COMPLETED
    EVENT_LOG.add(f"Ride completed for Driver {driver.name}.")

#FARE CALCULATION
def calculate_fares(driver: Driver, plan: TripPlan) -> None:
    section(f"FARE CALCULATION — DRIVER {driver.id}: {driver.name}")
    if not driver.passengers:
        print("  No passengers for fare calculation.")
        return

    print(f"  Base Fare      : {money(BASE_FARE)}")
    print(f"  Distance Rate  : {money(RATE_PER_KM)} / km")
    print(f"  Time Rate      : {money(RATE_PER_MIN)} / min")
    print(f"  Shared Discount: {int(SHARED_DISCOUNT * 100)}%")
    line()

    total_driver_fare = 0.0
    for p in driver.passengers:
        if p.shared:
            passenger_km = passenger_experience_distance(plan, p)
        else:
            passenger_km = passenger_direct_distance(p)
        passenger_min = eta_minutes(passenger_km)
        raw_fare = BASE_FARE + passenger_km * RATE_PER_KM + passenger_min * RATE_PER_MIN
        final_fare = raw_fare * (1 - SHARED_DISCOUNT) if p.shared else raw_fare
        p.fare = final_fare
        total_driver_fare += final_fare

        tag = "SHARED" if p.shared else "SOLO"
        print(
            f"  {p.name:<16} | {tag:<6} | distance {passenger_km:>5.2f} km | "
            f"time {passenger_min:>5.1f} min | fare {money(final_fare)}"
        )

    line()
    print(f"  Total collected estimate: {money(total_driver_fare)}")

#TKINTER GUI INPUT
DARK = "#0d0d1a"
PANEL = "#161628"
CARD = "#1e1e35"
ACCENT = "#e94560"
ACCENT2 = "#4fc3f7"
TEXT = "#eaeaea"
SUBTLE = "#9a9ab8"
SUCCESS = "#69f0ae"
WARNING = "#ffd740"
LOC_OPTIONS = [f"{k:>2} — {v}" for k, v in location_names.items()]

def parse_node(combo_val: str) -> int:
    try:
        return int(combo_val.strip().split("—")[0].strip())
    except Exception:
        return 0

def apply_theme(root: tk.Misc) -> None:
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    style.configure(
        "TCombobox",
        fieldbackground=CARD,
        background=CARD,
        foreground=TEXT,
        selectbackground=ACCENT,
        selectforeground="white",
        arrowcolor=ACCENT,
    )
    style.map("TCombobox", fieldbackground=[("readonly", CARD)])

def open_role_window(root: tk.Tk, waiting_count: int, driver_count: int) -> str:
    result = {"role": "finish"}
    win = tk.Toplevel(root)
    win.title("Ride Sharing — Select Role")
    win.configure(bg=DARK)
    win.geometry("620x420")
    win.resizable(False, False)
    apply_theme(win)

    tk.Label(
        win,
        text="REAL-TIME RIDE SHARING SYSTEM",
        bg=ACCENT,
        fg="white",
        font=("Courier", 15, "bold"),
        pady=14,
    ).pack(fill="x")

    tk.Label(
        win,
        text="Who are you? Choose your role to open the correct window.",
        bg=DARK,
        fg=TEXT,
        font=("Courier", 11, "bold"),
        pady=18,
    ).pack()

    status = tk.Frame(win, bg=PANEL, padx=16, pady=12)
    status.pack(fill="x", padx=26, pady=(0, 18))
    tk.Label(status, text=f"Waiting passenger requests : {waiting_count}", bg=PANEL, fg=WARNING, font=("Courier", 10)).pack(anchor="w")
    tk.Label(status, text=f"Drivers already registered : {driver_count}", bg=PANEL, fg=SUCCESS, font=("Courier", 10)).pack(anchor="w")

    btns = tk.Frame(win, bg=DARK)
    btns.pack(pady=8)

    def choose(role: str) -> None:
        result["role"] = role
        win.destroy()

    tk.Button(
        btns,
        text="I AM A PASSENGER",
        command=lambda: choose("passenger"),
        bg=ACCENT2,
        fg=DARK,
        relief="flat",
        font=("Courier", 12, "bold"),
        width=22,
        padx=12,
        pady=10,
    ).grid(row=0, column=0, padx=10, pady=8)

    tk.Button(
        btns,
        text="I AM A DRIVER",
        command=lambda: choose("driver"),
        bg=ACCENT,
        fg="white",
        relief="flat",
        font=("Courier", 12, "bold"),
        width=22,
        padx=12,
        pady=10,
    ).grid(row=0, column=1, padx=10, pady=8)

    tk.Button(
        win,
        text="Finish / Generate Output",
        command=lambda: choose("finish"),
        bg=PANEL,
        fg=SUBTLE,
        relief="flat",
        font=("Courier", 10),
        padx=16,
        pady=8,
    ).pack(pady=(18, 0))

    win.grab_set()
    root.wait_window(win)
    return result["role"]

def open_passenger_window(root: tk.Tk) -> List[dict]:
    results: List[dict] = []
    win = tk.Toplevel(root)
    win.title("Ride Sharing — Passenger Registration")
    win.configure(bg=DARK)
    win.geometry("920x620")
    win.minsize(860, 540)
    apply_theme(win)

    tk.Label(
        win,
        text="PASSENGER REQUEST WINDOW",
        bg=ACCENT,
        fg="white",
        font=("Courier", 14, "bold"),
        pady=12,
    ).pack(fill="x")

    info = tk.Label(
        win,
        text="Enter passenger details. After saving, you can add another passenger before matching starts.",
        bg=PANEL,
        fg=SUBTLE,
        font=("Courier", 9),
        pady=8,
    )
    info.pack(fill="x", padx=16, pady=(12, 0))

    canvas_holder = tk.Frame(win, bg=DARK)
    canvas_holder.pack(fill="both", expand=True, padx=16, pady=10)

    canvas = tk.Canvas(canvas_holder, bg=DARK, highlightthickness=0)
    scrollbar = ttk.Scrollbar(canvas_holder, orient="vertical", command=canvas.yview)
    scroll_frame = tk.Frame(canvas, bg=DARK)
    scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    rows: List[Tuple[tk.StringVar, tk.StringVar, tk.StringVar, tk.BooleanVar]] = []

    def add_row() -> None:
        idx = len(rows) + 1
        name_v = tk.StringVar()
        pickup_v = tk.StringVar()
        drop_v = tk.StringVar()
        share_v = tk.BooleanVar(value=False)
        rows.append((name_v, pickup_v, drop_v, share_v))

        card = tk.Frame(scroll_frame, bg=CARD, highlightbackground=ACCENT, highlightthickness=1, padx=10, pady=10)
        card.pack(fill="x", pady=7)
        tk.Label(card, text=f"PASSENGER {idx}", bg=ACCENT, fg="white", font=("Courier", 10, "bold"), padx=10).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 10))

        tk.Label(card, text="Name:", bg=CARD, fg=SUBTLE, font=("Courier", 9)).grid(row=1, column=0, sticky="w", padx=(0, 6))
        tk.Entry(card, textvariable=name_v, bg=DARK, fg=TEXT, insertbackground=ACCENT, relief="flat", width=28, font=("Courier", 10)).grid(row=1, column=1, sticky="w", padx=6, pady=4)

        tk.Label(card, text="Pickup:", bg=CARD, fg=SUBTLE, font=("Courier", 9)).grid(row=2, column=0, sticky="w", padx=(0, 6))
        ttk.Combobox(card, textvariable=pickup_v, values=LOC_OPTIONS, state="readonly", width=34, font=("Courier", 9)).grid(row=2, column=1, sticky="w", padx=6, pady=4)

        tk.Label(card, text="Drop:", bg=CARD, fg=SUBTLE, font=("Courier", 9)).grid(row=2, column=2, sticky="w", padx=(24, 6))
        ttk.Combobox(card, textvariable=drop_v, values=LOC_OPTIONS, state="readonly", width=34, font=("Courier", 9)).grid(row=2, column=3, sticky="w", padx=6, pady=4)

        tk.Checkbutton(
            card,
            text="I want shared ride if route is compatible",
            variable=share_v,
            bg=CARD,
            fg=ACCENT2,
            activebackground=CARD,
            activeforeground=SUCCESS,
            selectcolor=CARD,
            font=("Courier", 9, "bold"),
        ).grid(row=3, column=0, columnspan=4, sticky="w", pady=(8, 0))

    add_row()

    btn_frame = tk.Frame(win, bg=DARK)
    btn_frame.pack(fill="x", padx=16, pady=(0, 14))

    def submit() -> None:
        results.clear()
        for idx, (nv, pv, dv, sv) in enumerate(rows, 1):
            name = nv.get().strip()
            pickup_raw = pv.get().strip()
            drop_raw = dv.get().strip()
            if not name:
                messagebox.showerror("Missing", f"Passenger {idx}: name is required.", parent=win)
                return
            if not pickup_raw or not drop_raw:
                messagebox.showerror("Missing", f"Passenger {idx}: pickup and drop are required.", parent=win)
                return
            pickup = parse_node(pickup_raw)
            drop = parse_node(drop_raw)
            if pickup == drop:
                messagebox.showerror("Invalid", f"Passenger {idx}: pickup and drop must be different.", parent=win)
                return
            results.append({"name": name, "pickup": pickup, "drop": drop, "wants_share": sv.get()})

        add_more = messagebox.askyesno(
            "Add another passenger?",
            "Passenger request saved.\n\nDo you want to add another passenger before starting the ride/matching?",
            parent=win,
        )

        if add_more:
            add_row()
            win.update_idletasks()
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.yview_moveto(1.0)
            return

        win.destroy()

    tk.Button(btn_frame, text="+ Add Passenger", command=add_row, bg=PANEL, fg=ACCENT2, relief="flat", font=("Courier", 10, "bold"), padx=12, pady=6).pack(side="left")
    tk.Button(btn_frame, text="DONE / START MATCHING", command=submit, bg=ACCENT, fg="white", relief="flat", font=("Courier", 11, "bold"), padx=18, pady=7).pack(side="right")

    win.grab_set()
    root.wait_window(win)
    return results

def open_driver_window(root: tk.Tk, driver_num: int, waiting_summary: List[Passenger]) -> Optional[dict]:
    result: dict = {}
    win = tk.Toplevel(root)
    win.title(f"Ride Sharing — Driver {driver_num}")
    win.configure(bg=DARK)
    win.geometry("900x650")
    win.minsize(850, 560)
    apply_theme(win)

    tk.Label(
        win,
        text=f"DRIVER {driver_num} — GO ONLINE",
        bg=ACCENT,
        fg="white",
        font=("Courier", 14, "bold"),
        pady=12,
    ).pack(fill="x")

    pool = tk.Frame(win, bg=PANEL, padx=10, pady=8)
    pool.pack(fill="x", padx=16, pady=12)
    tk.Label(pool, text=f"WAITING PASSENGERS ({len(waiting_summary)})", bg=PANEL, fg=WARNING, font=("Courier", 10, "bold")).pack(anchor="w")
    for p in waiting_summary[:8]:
        share = "Share" if p.wants_share else "Solo"
        tk.Label(pool, text=f"• {p.name:<16} {location_names[p.pickup]} → {location_names[p.drop]} [{share}]", bg=PANEL, fg=TEXT, font=("Courier", 8)).pack(anchor="w")
    if len(waiting_summary) > 8:
        tk.Label(pool, text=f"... and {len(waiting_summary) - 8} more", bg=PANEL, fg=SUBTLE, font=("Courier", 8)).pack(anchor="w")

    form = tk.Frame(win, bg=DARK)
    form.pack(fill="x", padx=28, pady=12)

    name_v = tk.StringVar()
    vehicle_v = tk.StringVar()
    loc_v = tk.StringVar()
    cap_v = tk.StringVar(value="4")

    def row(label: str, widget: tk.Widget, r: int) -> None:
        tk.Label(form, text=label, bg=DARK, fg=SUBTLE, font=("Courier", 10)).grid(row=r, column=0, sticky="w", pady=8)
        widget.grid(row=r, column=1, sticky="w", padx=12, pady=8)

    row("Driver Name:", tk.Entry(form, textvariable=name_v, bg=CARD, fg=TEXT, insertbackground=ACCENT, relief="flat", font=("Courier", 11), width=26), 0)
    row("Vehicle No.:", tk.Entry(form, textvariable=vehicle_v, bg=CARD, fg=TEXT, insertbackground=ACCENT, relief="flat", font=("Courier", 11), width=26), 1)
    row("Location:", ttk.Combobox(form, textvariable=loc_v, values=LOC_OPTIONS, state="readonly", font=("Courier", 10), width=34), 2)

    cap_frame = tk.Frame(form, bg=DARK)
    for cap in range(1, MAX_DRIVER_CAPACITY + 1):
        tk.Radiobutton(cap_frame, text=str(cap), value=str(cap), variable=cap_v, bg=DARK, fg=TEXT, selectcolor=CARD, activebackground=DARK, font=("Courier", 11, "bold")).pack(side="left", padx=4)
    row("Seat Capacity:", cap_frame, 3)

    note = tk.Label(
        win,
        text="The system will assign the nearest valid passenger/group using capacity, sharing consent, ETA and detour checks.",
        bg=PANEL,
        fg=SUCCESS,
        font=("Courier", 9),
        pady=10,
    )
    note.pack(fill="x", padx=16, pady=10)

    def submit() -> None:
        name = name_v.get().strip()
        loc_raw = loc_v.get().strip()
        if not name:
            messagebox.showerror("Missing", "Driver name is required.")
            return
        if not loc_raw:
            messagebox.showerror("Missing", "Driver location is required.")
            return
        result.update({"name": name, "vehicle": vehicle_v.get().strip() or "N/A", "node": parse_node(loc_raw), "capacity": int(cap_v.get())})
        win.destroy()

    def skip() -> None:
        win.destroy()

    buttons = tk.Frame(win, bg=DARK)
    buttons.pack(fill="x", padx=16, pady=18)
    tk.Button(buttons, text="Skip", command=skip, bg=PANEL, fg=SUBTLE, relief="flat", font=("Courier", 10), padx=18, pady=7).pack(side="left")
    tk.Button(buttons, text="GO ONLINE", command=submit, bg=ACCENT, fg="white", relief="flat", font=("Courier", 11, "bold"), padx=20, pady=8).pack(side="right")

    win.grab_set()
    root.wait_window(win)
    return result if result else None

#CONSOLE INPUT
def console_passenger_input() -> List[Passenger]:
    passengers: List[Passenger] = []

    while True:
        section(f"PASSENGER {len(passengers) + 1} INFORMATION")
        name = input("  Passenger Name : ").strip()
        while not name:
            name = input("  Name required  : ").strip()

        show_locations()
        pickup = get_int_input("  Pickup Node    : ", 0, num_nodes - 1)
        drop = get_int_input("  Drop Node      : ", 0, num_nodes - 1)
        while drop == pickup:
            print("  Drop must be different from pickup.")
            drop = get_int_input("  Drop Node      : ", 0, num_nodes - 1)

        share_answer = input("  Wants shared ride if compatible? (y/n): ").strip().lower()
        while share_answer not in {"y", "n"}:
            share_answer = input("  Please enter y or n: ").strip().lower()
        wants_share = share_answer == "y"

        p = Passenger(name, pickup, drop, wants_share)
        passengers.append(p)
        EVENT_LOG.add(
            f"Passenger request created: {p.name}, "
            f"{location_names[p.pickup]} → {location_names[p.drop]}."
        )

        print("\n  ✓ Passenger request saved.")

        if len(passengers) >= MAX_CONSOLE_PASSENGERS:
            print(f"  Maximum limit of {MAX_CONSOLE_PASSENGERS} passenger requests reached.")
            break

        more = input("\n  Do you want to add another passenger? (y/n): ").strip().lower()
        while more not in {"y", "n"}:
            more = input("  Please enter y or n: ").strip().lower()
        if more == "n":
            break

    print("\n  Passenger registration completed. The system will now try to match/start the ride.")
    return passengers

def console_driver_input(driver_num: int) -> Driver:
    section(f"DRIVER {driver_num} REGISTRATION")
    name = input("  Driver Name    : ").strip()
    while not name:
        name = input("  Name required  : ").strip()
    vehicle = input("  Vehicle Number : ").strip() or "N/A"
    show_locations()
    node = get_int_input("  Current Location Node : ", 0, num_nodes - 1)
    capacity = get_int_input("  Seat Capacity (1–4)   : ", 1, MAX_DRIVER_CAPACITY)
    return Driver(name, vehicle, node, capacity)

#VISUALIZATION
DRIVER_COLORS = ["#ffd740", "#ff9800", "#ce93d8", "#80d8ff"]
PICKUP_COLOR = "#69f0ae"
DROP_COLOR = "#ff5252"
ROUTE_COLOR = "#4fc3f7"
UNMATCHED_COLOR = "#9e9e9e"

def draw_matplotlib_graph(drivers: Sequence[Driver], plans: Dict[int, TripPlan], unmatched: Sequence[Passenger]) -> None:
    if not MATPLOTLIB_AVAILABLE:
        print("  [!] Matplotlib not installed — run: pip install matplotlib")
        return

    fig = plt.figure(figsize=(20, 12))
    fig.patch.set_facecolor(DARK)
    ax = fig.add_axes([0.035, 0.06, 0.64, 0.86])
    ax_info = fig.add_axes([0.70, 0.06, 0.27, 0.86])
    ax.set_facecolor(DARK)
    ax_info.set_facecolor(PANEL)
    ax_info.set_axis_off()

    fig.suptitle(
        "Real-Time Dynamic Ride Sharing — Readable Route Graph",
        color="white",
        fontsize=16,
        fontweight="bold",
    )

    plot_pos = PLOT_POSITIONS

    nx.draw_networkx_edges(G, plot_pos, ax=ax, edge_color="#34345a", width=1.4, alpha=0.55)
    nx.draw_networkx_nodes(
        G,
        plot_pos,
        ax=ax,
        node_color="#1e1e35",
        edgecolors="#666690",
        node_size=1050,
        linewidths=1.6,
    )
    nx.draw_networkx_labels(
        G,
        plot_pos,
        labels=NODE_SHORT_LABELS,
        ax=ax,
        font_color="white",
        font_size=8.6,
        font_family="monospace",
        font_weight="bold",
    )

    used_edges = set()
    for plan in plans.values():
        if not plan:
            continue
        for u, v in zip(plan.full_route, plan.full_route[1:]):
            used_edges.add(tuple(sorted((u, v))))

    route_edge_labels = {}
    for u, v, data in G.edges(data=True):
        if tuple(sorted((u, v))) in used_edges:
            route_edge_labels[(u, v)] = f"{data['weight']:.1f} km"

    nx.draw_networkx_edge_labels(
        G,
        plot_pos,
        edge_labels=route_edge_labels,
        ax=ax,
        font_color="#111111",
        font_weight="bold",
        font_size=8.2,
        rotate=False,
        bbox=dict(
            boxstyle="round,pad=0.24",
            facecolor="#ffd740",
            edgecolor="#6b5300",
            linewidth=1.0,
            alpha=0.97,
        ),
    )

    def draw_route(path: Sequence[int], color: str, width: float = 4.5, style: str = "solid") -> None:
        if len(path) < 2:
            return
        edges = list(zip(path, path[1:]))
        nx.draw_networkx_edges(
            G,
            plot_pos,
            edgelist=edges,
            ax=ax,
            edge_color=color,
            width=width,
            alpha=0.96,
            style=style,
        )

    def callout_offset(drop_node: int, nth: int) -> Tuple[int, int, str]:
        """Return readable offset points so labels do not sit on top of nodes."""
        patterns = [
            ((70, 34), "left"),
            ((-70, 34), "right"),
            ((70, -34), "left"),
            ((-70, -34), "right"),
            ((0, 62), "center"),
            ((0, -62), "center"),
        ]
        dx, dy = patterns[nth % len(patterns)][0]
        align = patterns[nth % len(patterns)][1]
        x, _ = plot_pos[drop_node]
        # Push labels inward if node is close to left/right edge.
        if x < 2.2 and dx < 0:
            dx = abs(dx)
            align = "left"
        elif x > 8.3 and dx > 0:
            dx = -abs(dx)
            align = "right"
        return dx, dy, align

    drop_callout_count: Dict[int, int] = {}
    for idx, driver in enumerate(drivers):
        color = DRIVER_COLORS[idx % len(DRIVER_COLORS)]
        plan = plans.get(driver.id)
        if plan:
            draw_route(plan.full_route, color, width=5.0)

        nx.draw_networkx_nodes(
            G,
            plot_pos,
            nodelist=[driver.node],
            ax=ax,
            node_color=color,
            edgecolors="white",
            node_size=1350,
            linewidths=2.5,
        )

        if driver.passengers:
            pickup_nodes = list({p.pickup for p in driver.passengers})
            drop_nodes = list({p.drop for p in driver.passengers})
            nx.draw_networkx_nodes(G, plot_pos, nodelist=pickup_nodes, ax=ax, node_color=PICKUP_COLOR, edgecolors="white", node_size=1150, linewidths=2.0)
            nx.draw_networkx_nodes(G, plot_pos, nodelist=drop_nodes, ax=ax, node_color=DROP_COLOR, edgecolors="white", node_size=1150, linewidths=2.0)

        for p in driver.passengers:
            x, y = plot_pos[p.drop]
            nth = drop_callout_count.get(p.drop, 0)
            drop_callout_count[p.drop] = nth + 1
            xoff = 0.38 + (nth % 2) * 0.55
            yoff = 0.55 + nth * 0.36
            tag = "Shared" if p.shared else "Solo"
            ax.annotate(
                f"{p.name}\n{money(p.fare)} ({tag})",
                xy=(x, y),
                xytext=(x + xoff, y + yoff),
                color="white",
                fontsize=8.2,
                fontfamily="monospace",
                fontweight="bold",
                arrowprops=dict(arrowstyle="->", color=WARNING, lw=1.2),
                bbox=dict(boxstyle="round,pad=0.28", facecolor="#161628", edgecolor=WARNING, alpha=0.95),
            )

    if unmatched:
        nodes = list({p.pickup for p in unmatched})
        nx.draw_networkx_nodes(G, plot_pos, nodelist=nodes, ax=ax, node_color=UNMATCHED_COLOR, edgecolors="white", node_size=950, linewidths=1.8)

    ax.text(
        0.01,
        0.01,
        "Note: nodes are intentionally spread out for readability; distances still come from real coordinates.",
        transform=ax.transAxes,
        color=SUBTLE,
        fontsize=8,
        fontfamily="monospace",
    )

    ax.set_xlim(-1.2, 11.4)
    ax.set_ylim(-1.2, 9.8)
    ax.tick_params(left=False, bottom=False, labelleft=False, labelbottom=False)
    for spine in ax.spines.values():
        spine.set_visible(False)

    y = 0.965
    ax_info.text(0.5, y, "LIVE SYSTEM SUMMARY", color=ACCENT, fontsize=12, fontweight="bold", ha="center", va="top", transform=ax_info.transAxes, fontfamily="monospace")
    y -= 0.046
    ax_info.text(0.05, y, "Passenger fares are shown below and also as callouts on drop nodes.", color=SUBTLE, fontsize=7, transform=ax_info.transAxes, fontfamily="monospace")
    y -= 0.044

    for idx, driver in enumerate(drivers):
        color = DRIVER_COLORS[idx % len(DRIVER_COLORS)]
        plan = plans.get(driver.id)
        ax_info.text(0.05, y, f"Driver {driver.id}: {driver.name}", color=color, fontsize=9.2, fontweight="bold", transform=ax_info.transAxes, fontfamily="monospace")
        y -= 0.032
        ax_info.text(0.07, y, f"Vehicle: {driver.vehicle} | Capacity: {driver.capacity}", color=SUBTLE, fontsize=7, transform=ax_info.transAxes, fontfamily="monospace")
        y -= 0.028
        ax_info.text(0.07, y, f"Current: {location_names[driver.node]}", color=SUBTLE, fontsize=7, transform=ax_info.transAxes, fontfamily="monospace")
        y -= 0.032
        if plan:
            ax_info.text(0.07, y, f"Distance: {plan.total_distance:.2f} km | ETA: {eta_minutes(plan.total_distance):.1f} min", color=TEXT, fontsize=7, transform=ax_info.transAxes, fontfamily="monospace")
            y -= 0.034
        for p in driver.passengers:
            tag = "SHARED" if p.shared else "SOLO"
            ax_info.text(0.09, y, f"• {p.name} [{tag}]", color=ROUTE_COLOR if p.shared else TEXT, fontsize=7.2, transform=ax_info.transAxes, fontfamily="monospace")
            y -= 0.024
            ax_info.text(0.12, y, f"{location_names[p.pickup]} → {location_names[p.drop]}", color=SUBTLE, fontsize=6.4, transform=ax_info.transAxes, fontfamily="monospace")
            y -= 0.023
            ax_info.text(0.12, y, f"Fare to pay: {money(p.fare)}", color=WARNING, fontsize=7.0, fontweight="bold", transform=ax_info.transAxes, fontfamily="monospace")
            y -= 0.031
        y -= 0.018
        if y < 0.14:
            break

    if unmatched and y > 0.10:
        ax_info.text(0.05, y, "UNMATCHED", color=WARNING, fontsize=9, fontweight="bold", transform=ax_info.transAxes, fontfamily="monospace")
        y -= 0.035
        for p in unmatched[:5]:
            ax_info.text(0.08, y, f"• {p.name}: {location_names[p.pickup]} → {location_names[p.drop]}", color=SUBTLE, fontsize=6.5, transform=ax_info.transAxes, fontfamily="monospace")
            y -= 0.027

    if y > 0.08:
        ax_info.text(0.05, 0.055, "Legend: yellow/orange/purple/blue = drivers | green = pickup | red = drop | grey = unmatched", color=SUBTLE, fontsize=6.5, transform=ax_info.transAxes, fontfamily="monospace")

    plt.savefig("ride_sharing_route.png", dpi=170, bbox_inches="tight", facecolor=fig.get_facecolor())
    print("  [✓] Matplotlib graph saved → ride_sharing_route.png")
    plt.show()


def draw_folium_map(drivers: Sequence[Driver], plans: Dict[int, TripPlan], unmatched: Sequence[Passenger]) -> None:
    if not FOLIUM_AVAILABLE:
        print("  [!] Folium not installed — run: pip install folium")
        return

    fmap = folium.Map(location=[33.6844, 73.0479], zoom_start=12, tiles="CartoDB dark_matter")

    for u, v, data in G.edges(data=True):
        folium.PolyLine(
            [location_coords[u], location_coords[v]],
            color="#3a3a6a",
            weight=2,
            opacity=0.45,
            tooltip=f"{location_names[u]} ↔ {location_names[v]}: {data['weight']:.1f} km",
        ).add_to(fmap)

    folium_icon_colors = ["orange", "purple", "blue", "darkred"]

    for idx, driver in enumerate(drivers):
        plan = plans.get(driver.id)
        color = DRIVER_COLORS[idx % len(DRIVER_COLORS)]
        icon_color = folium_icon_colors[idx % len(folium_icon_colors)]

        folium.Marker(
            location=location_coords[driver.node],
            popup=folium.Popup(f"<b>Driver {driver.id}: {driver.name}</b><br>Vehicle: {driver.vehicle}<br>Capacity: {driver.capacity}", max_width=240),
            tooltip=f"Driver: {driver.name}",
            icon=folium.Icon(color=icon_color, icon="car", prefix="fa"),
        ).add_to(fmap)

        if plan and len(plan.full_route) > 1:
            coords = [location_coords[n] for n in plan.full_route]
            folium.PolyLine(coords, color=color, weight=5, opacity=0.9, tooltip=f"Driver {driver.id} optimized route").add_to(fmap)

        for p in driver.passengers:
            tag = "Shared" if p.shared else "Solo"
            folium.Marker(
                location=location_coords[p.pickup],
                popup=folium.Popup(f"<b>Pickup</b><br>{p.name}<br>{tag}<br>{location_names[p.pickup]}<br>Fare: {money(p.fare)}", max_width=220),
                tooltip=f"Pickup: {p.name}",
                icon=folium.Icon(color="green", icon="map-marker", prefix="fa"),
            ).add_to(fmap)
            folium.Marker(
                location=location_coords[p.drop],
                popup=folium.Popup(f"<b>Drop</b><br>{p.name}<br>{tag}<br>{location_names[p.drop]}<br>Fare: {money(p.fare)}", max_width=220),
                tooltip=f"Drop: {p.name}",
                icon=folium.Icon(color="red", icon="flag", prefix="fa"),
            ).add_to(fmap)

    for p in unmatched:
        folium.Marker(
            location=location_coords[p.pickup],
            popup=folium.Popup(f"<b>UNMATCHED</b><br>{p.name}<br>{location_names[p.pickup]} → {location_names[p.drop]}", max_width=220),
            tooltip=f"Unmatched: {p.name}",
            icon=folium.Icon(color="gray", icon="clock-o", prefix="fa"),
        ).add_to(fmap)

    legend_html = """
    <div style="position:fixed;bottom:30px;left:30px;z-index:9999;background:#0d0d1a;
                border:1px solid #3a3a6a;border-radius:8px;padding:12px 16px;color:white;
                font-family:monospace;font-size:12px;line-height:1.8;">
      <b>REAL-TIME RIDE SYSTEM</b><br>
      <span style="color:#69f0ae">●</span> Pickup &nbsp;
      <span style="color:#ff5252">●</span> Drop &nbsp;
      <span style="color:#9e9e9e">●</span> Unmatched<br>
      Colored lines = optimized driver routes<br>
      Grey lines = available road network
    </div>
    """
    fmap.get_root().html.add_child(folium.Element(legend_html))
    fmap.save("ride_sharing_map.html")
    print("  [✓] Folium map saved      → ride_sharing_map.html")

#REPORTING
def print_waiting_pool(waiting_pool: Sequence[Passenger]) -> None:
    section("PASSENGER POOL — WAITING REQUESTS")
    if not waiting_pool:
        print("  No waiting passengers.")
        return
    print(f"  {'ID':<5}{'NAME':<18}{'PICKUP':<22}{'DROP':<22}{'PREF':<10}{'STATUS'}")
    line()
    for p in waiting_pool:
        pref = "Share" if p.wants_share else "Solo"
        print(f"  {p.id:<5}{p.name:<18}{location_names[p.pickup]:<22}{location_names[p.drop]:<22}{pref:<10}{p.status.value}")
    print(f"\n  Total waiting: {len(waiting_pool)} passenger(s)")


def final_summary(drivers: Sequence[Driver], plans: Dict[int, TripPlan], unmatched: Sequence[Passenger]) -> None:
    title("SYSTEM FINAL SUMMARY")
    if not drivers:
        print("  No drivers came online.")
    for driver in drivers:
        print(f"\n  Driver {driver.id}: {driver.name} ({driver.vehicle})")
        print(f"  Final Location: {location_names[driver.node]}")
        plan = plans.get(driver.id)
        if plan:
            print(f"  Route Distance: {plan.total_distance:.2f} km")
            print(f"  Route         : {route_text(plan.full_route)}")
        if not driver.passengers:
            print("    ↳ No passengers assigned")
        for p in driver.passengers:
            tag = "SHARED" if p.shared else "SOLO"
            print(
                f"    ↳ {p.name:<16} {location_names[p.pickup]} → {location_names[p.drop]} "
                f"[{tag}] | {p.status.value} | {money(p.fare)}"
            )

    if unmatched:
        section("UNMATCHED PASSENGERS")
        for p in unmatched:
            print(f"  • {p.name}: {location_names[p.pickup]} → {location_names[p.drop]}")
        print("\n  Reason: no available driver seats or route/group compatibility failed.")
    else:
        section("ALL PASSENGERS MATCHED")
        print("  Every passenger was assigned and processed.")

#MAIN PROGRAM
def main() -> None:
    title("REAL-TIME DYNAMIC RIDE SHARING SYSTEM")
    print("  This version uses role-first input, passenger/driver windows, readable graph")
    print("  layout, fare labels on the graph, ETA, statuses, and live GPS movement.\n")

    print("  Input Mode:")
    print("  1. Tkinter GUI  (recommended if available)")
    print("  2. Console      (text only)")
    choice = input("\n  Choose input mode (1 or 2): ").strip()

    use_gui = choice == "1" and TKINTER_AVAILABLE
    if choice == "1" and not TKINTER_AVAILABLE:
        print("\n  [!] Tkinter is not available. Falling back to console mode.")

    waiting_pool: List[Passenger] = []
    drivers: List[Driver] = []
    plans: Dict[int, TripPlan] = {}

    root: Optional[tk.Tk] = None
    if use_gui:
        root = tk.Tk()
        root.withdraw()

    def process_driver(driver: Driver) -> None:
        drivers.append(driver)
        EVENT_LOG.add(f"Driver came online: {driver.name} at {location_names[driver.node]} with {driver.capacity} seat(s).")

        assigned_group, reason, plan = auto_assign_passengers(driver, waiting_pool)
        print_assignment(driver, assigned_group, reason, plan)

        if plan and assigned_group:
            plans[driver.id] = plan
            simulate_live_trip(driver, plan)
            calculate_fares(driver, plan)
        elif not waiting_pool:
            print("\n  No passenger requests are waiting right now. Driver remains registered in the system.")
            print("  You can now choose Passenger from the role menu; this idle driver can be matched later.")
        else:
            print("\n  Driver registered, but no compatible passenger/group was found.")

    def process_idle_drivers() -> None:
        if not waiting_pool:
            return

        idle_drivers = [driver for driver in drivers if not driver.passengers]
        for driver in idle_drivers:
            if not waiting_pool:
                break
            section(f"REAL-TIME MATCHING — WAITING DRIVER: {driver.name}")
            assigned_group, reason, plan = auto_assign_passengers(driver, waiting_pool)
            print_assignment(driver, assigned_group, reason, plan)

            if plan and assigned_group:
                plans[driver.id] = plan
                simulate_live_trip(driver, plan)
                calculate_fares(driver, plan)
            else:
                print(f"\n  {driver.name} is still online, but no compatible request was found yet.")

    while True:
        if use_gui and root:
            role = open_role_window(root, len(waiting_pool), len(drivers))
        else:
            section("SELECT ROLE")
            print("  1. I am a Passenger  → open passenger registration")
            print("  2. I am a Driver     → open driver registration")
            print("  3. Finish / Generate final output")
            raw = input("\n  Choose your role (1, 2, or 3): ").strip()
            role = {"1": "passenger", "2": "driver", "3": "finish"}.get(raw, "")
            if not role:
                print("  Invalid choice. Please choose 1, 2, or 3.")
                continue

        if role == "passenger":
            section("PASSENGER ROLE SELECTED")
            if use_gui and root:
                pax_data = open_passenger_window(root)
                for pd in pax_data:
                    p = Passenger(pd["name"], pd["pickup"], pd["drop"], pd["wants_share"])
                    waiting_pool.append(p)
                    EVENT_LOG.add(f"Passenger request created: {p.name}, {location_names[p.pickup]} → {location_names[p.drop]}.")
            else:
                waiting_pool.extend(console_passenger_input())

            #If drivers are already online and idle, match the new passenger requests immediately.
            process_idle_drivers()
            print_waiting_pool(waiting_pool)

        elif role == "driver":
            section("DRIVER ROLE SELECTED")
            driver_num = len(drivers) + 1
            if use_gui and root:
                drv_data = open_driver_window(root, driver_num, waiting_pool)
                if drv_data is None:
                    print(f"  Driver {driver_num} skipped.")
                    continue
                driver = Driver(drv_data["name"], drv_data["vehicle"], drv_data["node"], drv_data["capacity"])
            else:
                driver = console_driver_input(driver_num)
            process_driver(driver)
            if waiting_pool:
                print_waiting_pool(waiting_pool)

        elif role == "finish":
            break

        #Keep returning to the role menu. The program finishes only when the user selects option 3.

    unmatched = list(waiting_pool)
    final_summary(drivers, plans, unmatched)
    EVENT_LOG.print_final()

    active_drivers = [d for d in drivers if d.passengers]
    if active_drivers:
        section("GENERATING VISUAL OUTPUTS")
        print("  1. Static graph      → ride_sharing_route.png")
        print("  2. Interactive map   → ride_sharing_map.html")
        draw_matplotlib_graph(active_drivers, plans, unmatched)
        draw_folium_map(active_drivers, plans, unmatched)
    else:
        print("\n  No completed rides, so route visuals were not generated.")

    if root:
        root.destroy()

    line()
    print("  SYSTEM FINISHED SUCCESSFULLY".center(WIDTH))
    line()


if __name__ == "__main__":
    main()
