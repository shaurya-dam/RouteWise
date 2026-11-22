"""
RouteWise - apna routing (A* algorithm). Koi routing API nahi.

Steps:
  1. get_graph()  -> OpenStreetMap se sadkon ka data lekar graph banao
                     aur graph ko text file me save karo
  2. find_route() -> C++ engine (logic.cpp) A* chalata hai
                     (C++ exe na mile to neeche wala Python a_star() chalta hai)
"""
import heapq
import math
import os
import subprocess
import tempfile
from datetime import datetime

import requests

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Road type -> average speed (km/h). Jo type yahan nahi hai wo road ignore hogi.
SPEEDS = {
    "motorway": 80, "trunk": 60, "primary": 45, "secondary": 40,
    "tertiary": 35, "unclassified": 30, "residential": 25,
    "motorway_link": 50, "trunk_link": 40, "primary_link": 35,
    "secondary_link": 30, "tertiary_link": 30,
}
MAX_SPEED = 80                      # sabse tez road (heuristic ke liye)
BIG_ROADS = ("motorway", "trunk", "primary", "secondary",
             "motorway_link", "trunk_link", "primary_link", "secondary_link")
RUSH_HOURS = (8, 9, 10, 17, 18, 19, 20)

_saved_graph = None                 # last graph yaad rakho (baar-baar download na ho)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENGINE_PATH = os.path.join(BASE_DIR, "backend", "RouteWiseEngine.exe" if os.name == "nt" else "RouteWiseEngine")
GRAPH_FILE = os.path.join(tempfile.gettempdir(), "routewise_graph.txt")   # C++ ko ye file milti hai


# ---------------------------------------------------------------
# Chhote helper functions
# ---------------------------------------------------------------
def distance_km(lat1, lon1, lat2, lon2):
    """Haversine: do GPS points ke beech ki doori (km)."""
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def traffic(road_type, hour):
    """Traffic multiplier (simulated): 1.0 = clear, 1.6 = heavy."""
    big = road_type in BIG_ROADS
    if hour in RUSH_HOURS:
        return 1.6 if big else 1.25
    return 1.1 if big else 1.0


# ---------------------------------------------------------------
# Car ke liye road rules
# ---------------------------------------------------------------
def car_can_use(tags):
    """Kya ye road car ke liye khuli hai? (private / band roads skip)"""
    if tags.get("area") == "yes":
        return False
    motor = tags.get("motor_vehicle")
    if motor in ("yes", "designated", "permissive"):
        return True                                   # motor_vehicle=yes baaki rules ko override karta hai
    for key in ("motor_vehicle", "motorcar", "vehicle", "access"):
        if tags.get(key) in ("no", "private", "customers", "delivery", "agricultural", "forestry"):
            return False
    return True


def road_direction(tags, road_type):
    """'both' = dono taraf, 'forward' = sirf aage, 'reverse' = sirf ulta."""
    oneway = tags.get("oneway", "")
    if oneway in ("-1", "reverse"):
        return "reverse"
    if oneway in ("yes", "true", "1"):
        return "forward"
    if oneway == "no":
        return "both"
    if tags.get("junction") in ("roundabout", "circular"):
        return "forward"                              # roundabout me ulta nahi ghoom sakte
    if road_type in ("motorway", "motorway_link"):
        return "forward"                              # motorway by default oneway hoti hai
    return "both"


# ---------------------------------------------------------------
# Step 1: Graph banana
# graph["nodes"] = {node_id: (lat, lon)}
# graph["roads"] = {node_id: [(agla_node, km, road_type), ...]}
# ---------------------------------------------------------------
def get_graph(points):
    """points = [(lat, lon), ...]. In sab ko cover karne wala graph do."""
    global _saved_graph

    # Pehle se bana graph kaam aa sakta hai?
    if _saved_graph:
        s, w, n, e = _saved_graph["bbox"]
        if all(s < lat < n and w < lon < e for lat, lon in points):
            return _saved_graph

    # Sab points ke around ka box (thoda extra jagah ke saath)
    lats = [p[0] for p in points]
    lons = [p[1] for p in points]
    pad = 0.02
    bbox = (min(lats) - pad, min(lons) - pad, max(lats) + pad, max(lons) + pad)

    # Overpass se is box ki saari roads maango
    road_types = "|".join(SPEEDS)
    query = (f'[out:json][timeout:40];'
             f'way["highway"~"^({road_types})$"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});'
             f'(._;>;);out body;')
    response = requests.post(OVERPASS_URL, data={"data": query}, timeout=60,
                             headers={"User-Agent": "RouteWiseApp/1.0"})
    response.raise_for_status()
    data = response.json()

    nodes = {}
    roads = {}

    # Pehle saare nodes (GPS points) yaad karo
    for item in data["elements"]:
        if item["type"] == "node":
            nodes[item["id"]] = (item["lat"], item["lon"])

    # Phir har road ke do-do paas ke nodes ko jodo (sirf car wali roads, sahi direction me)
    for item in data["elements"]:
        if item["type"] != "way":
            continue
        tags = item.get("tags", {})
        road_type = tags.get("highway")
        if road_type not in SPEEDS or not car_can_use(tags):
            continue
        direction = road_direction(tags, road_type)

        ids = item["nodes"]
        for a, b in zip(ids, ids[1:]):
            if a not in nodes or b not in nodes or a == b:
                continue
            km = distance_km(*nodes[a], *nodes[b])
            if direction in ("both", "forward"):
                roads.setdefault(a, []).append((b, km, road_type))
            if direction in ("both", "reverse"):
                roads.setdefault(b, []).append((a, km, road_type))

    roads = keep_main_network(roads)

    _saved_graph = {"bbox": bbox, "nodes": nodes, "roads": roads}
    save_graph_file(_saved_graph)
    return _saved_graph


def keep_main_network(roads):
    """Sirf sabse bada jura hua road network rakho.
    Chhote alag-thalag tukde (jaise gated lane / parking) hat jate hain,
    taaki start/goal kisi aisi road par na chipke jahan se car bahar na nikle."""
    neighbors = {}                                   # bina direction ke, sirf 'jura hua hai ya nahi'
    for a, edges in roads.items():
        for b, _, _ in edges:
            neighbors.setdefault(a, set()).add(b)
            neighbors.setdefault(b, set()).add(a)

    seen, biggest = set(), set()
    for node in neighbors:
        if node in seen:
            continue
        group, stack = set(), [node]
        seen.add(node)
        while stack:
            current = stack.pop()
            group.add(current)
            for nxt in neighbors[current]:
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        if len(group) > len(biggest):
            biggest = group

    return {a: [e for e in edges if e[0] in biggest]
            for a, edges in roads.items() if a in biggest}


def save_graph_file(graph):
    """Graph ko text file me likho taaki C++ padh sake.
    Format: N, phir N lines "id lat lon", phir M, phir M lines "from to km speed isBig"
    """
    used = set()
    edge_lines = []
    for a, edges in graph["roads"].items():
        for b, km, road_type in edges:
            used.add(a)
            used.add(b)
            big = 1 if road_type in BIG_ROADS else 0
            edge_lines.append(f"{a} {b} {km:.6f} {SPEEDS[road_type]} {big}")

    with open(GRAPH_FILE, "w") as f:
        f.write(f"{len(used)}\n")
        for node_id in used:
            lat, lon = graph["nodes"][node_id]
            f.write(f"{node_id} {lat} {lon}\n")
        f.write(f"{len(edge_lines)}\n")
        f.write("\n".join(edge_lines) + "\n")


def nearest_node(graph, lat, lon):
    """GPS point ke sabse paas ka road node."""
    best_node, best_dist = None, float("inf")
    for node_id in graph["roads"]:
        n_lat, n_lon = graph["nodes"][node_id]
        d = distance_km(lat, lon, n_lat, n_lon)
        if d < best_dist:
            best_node, best_dist = node_id, d
    return best_node


# ---------------------------------------------------------------
# Step 2: A* algorithm      f = g + h
#   g = start se yahan tak ka asli time
#   h = goal tak seedhi doori / MAX_SPEED  (andaza)
# ---------------------------------------------------------------
def a_star(graph, start, goal, hour):
    nodes, roads = graph["nodes"], graph["roads"]
    goal_lat, goal_lon = nodes[goal]

    def guess(node):
        lat, lon = nodes[node]
        return distance_km(lat, lon, goal_lat, goal_lon) / MAX_SPEED

    heap = [(guess(start), start)]      # (f, node): sabse chhota f pehle nikalta hai
    cost = {start: 0.0}                 # g: har node tak ka sabse kam time (ghante)
    came_from = {}                      # node -> (pichla node, km, road_type)
    done = set()

    while heap:
        _, current = heapq.heappop(heap)
        if current in done:
            continue
        done.add(current)
        if current == goal:
            break

        for next_node, km, road_type in roads.get(current, []):
            hours = km / SPEEDS[road_type] * traffic(road_type, hour)
            new_cost = cost[current] + hours
            if next_node not in cost or new_cost < cost[next_node]:
                cost[next_node] = new_cost
                came_from[next_node] = (current, km, road_type)
                heapq.heappush(heap, (new_cost + guess(next_node), next_node))

    if goal not in cost:
        return None                     # rasta nahi mila

    # Goal se start tak peeche chalke rasta banao
    path, total_km, free_hours = [goal], 0.0, 0.0
    node = goal
    while node != start:
        node, km, road_type = came_from[node]
        path.append(node)
        total_km += km
        free_hours += km / SPEEDS[road_type]
    path.reverse()

    return path, total_km, free_hours, cost[goal]


# ---------------------------------------------------------------
# Step 3: Final route (app.py isi ko call karta hai)
# ---------------------------------------------------------------
def find_route(graph, o_lat, o_lon, d_lat, d_lon):
    if os.path.isfile(ENGINE_PATH):
        try:
            return route_with_cpp(o_lat, o_lon, d_lat, d_lon)     # A* C++ me
        except (OSError, subprocess.SubprocessError, ValueError):
            pass                                                   # C++ fail -> Python fallback
    return route_with_python(graph, o_lat, o_lon, d_lat, d_lon)


def route_with_cpp(o_lat, o_lon, d_lat, d_lon):
    """C++ engine ko chalao: RouteWiseEngine ROUTE graph.txt o_lat o_lon d_lat d_lon hour"""
    if os.name != "nt" and not os.access(ENGINE_PATH, os.X_OK):
        os.chmod(ENGINE_PATH, 0o755)

    result = subprocess.run(
        [ENGINE_PATH, "ROUTE", GRAPH_FILE, str(o_lat), str(o_lon), str(d_lat), str(d_lon),
         str(datetime.now().hour)],
        capture_output=True, text=True, timeout=30, check=False)

    lines = result.stdout.strip().splitlines()
    if result.returncode != 0 or not lines:
        raise ValueError("C++ engine error: " + result.stderr.strip())
    if lines[0].startswith("NO_ROUTE"):
        return None

    values = {}
    points = [{"lat": o_lat, "lon": o_lon}]
    for line in lines:
        parts = line.split()
        if parts[0] == "POINT":
            points.append({"lat": float(parts[1]), "lon": float(parts[2])})
        else:
            values[parts[0]] = float(parts[1])
    points.append({"lat": d_lat, "lon": d_lon})

    return {
        "distance_km": round(values["DISTANCE_KM"], 2),
        "travel_time_minutes": int(values["TIME_MIN"]),
        "traffic_delay_minutes": int(values["DELAY_MIN"]),
        "points": points,
    }


def route_with_python(graph, o_lat, o_lon, d_lat, d_lon):
    """Backup: C++ exe compile na hua ho to yahi A* chalta hai."""
    start = nearest_node(graph, o_lat, o_lon)
    goal = nearest_node(graph, d_lat, d_lon)
    if start is None or goal is None:
        return None

    result = a_star(graph, start, goal, datetime.now().hour)
    if result is None:
        return None
    path, km, free_hours, traffic_hours = result

    points = [{"lat": o_lat, "lon": o_lon}]
    points += [{"lat": graph["nodes"][n][0], "lon": graph["nodes"][n][1]} for n in path]
    points.append({"lat": d_lat, "lon": d_lon})

    return {
        "distance_km": round(km, 2),
        "travel_time_minutes": max(1, round(traffic_hours * 60)),
        "traffic_delay_minutes": max(0, round((traffic_hours - free_hours) * 60)),
        "points": points,
    }