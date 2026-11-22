#define _USE_MATH_DEFINES
#include <iostream>
#include <iomanip>
#include <string>
#include <vector>
#include <queue>
#include <cmath>
#include <functional>
#include <unordered_map>
#include <unordered_set>
#include <fstream>
#include <algorithm>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

using namespace std;

// ============================================================
// PART 1: OOP RANGE ENGINE (Fuel & EV Safe Range)
// ============================================================

class Vehicle {
protected:
    double currentPercent;
    double maxCapacity;
    double efficiency;

public:
    Vehicle(double p, double c, double e) : currentPercent(p), maxCapacity(c), efficiency(e) {}
    virtual double calculateSafeRange() = 0;
    virtual ~Vehicle() {}
};

class FuelVehicle : public Vehicle {
public:
    FuelVehicle(double p, double c, double e) : Vehicle(p, c, e) {}
    double calculateSafeRange() override {
        double currentFuel = (currentPercent / 100.0) * maxCapacity;
        return (currentFuel * efficiency) * 0.90; // 10% buffer
    }
};

class ElectricVehicle : public Vehicle {
private:
    string connectorType;
public:
    ElectricVehicle(double p, double c, double e, string conn) : Vehicle(p, c, e), connectorType(conn) {}
    double calculateSafeRange() override {
        double currentBattery = (currentPercent / 100.0) * maxCapacity;
        return (currentBattery * efficiency) * 0.80; // 20% buffer
    }
};

class HybridVehicle : public Vehicle {
public:
    HybridVehicle(double p, double c, double e) : Vehicle(p, c, e) {}
    double calculateSafeRange() override {
        double currentEnergy = (currentPercent / 100.0) * maxCapacity;
        return (currentEnergy * efficiency) * 0.85; // 15% buffer
    }
};

// ============================================================
// PART 2: TRAFFIC-AWARE A* PATHFINDING ALGORITHM
// (Python ye graph file banata hai, A* yahan C++ me chalta hai)
// ============================================================

const double MAX_SPEED = 80.0;   // sabse tez road (km/h) - heuristic ke liye

struct Node {
    int id;
    double lat, lon;
};

struct Edge {
    int target_id;
    double distance;   // road ki length (km)
    double speed;      // road ki average speed (km/h)
    bool isBig;        // badi road (primary/secondary...) ya nahi
};

struct AStarNode {
    int id;
    double g_cost;     // start se yahan tak ka asli time (ghante)
    double f_cost;     // g_cost + h_cost

    bool operator>(const AStarNode& other) const {
        return f_cost > other.f_cost;
    }
};

struct ParentInfo {    // rasta wapas banane ke liye: kahan se aaye
    int prev;
    double distance;
    double speed;
};

struct RouteResult {
    bool found = false;
    vector<int> path;
    double km = 0.0;
    double freeHours = 0.0;      // bina traffic ke time
    double trafficHours = 0.0;   // traffic ke saath time
};

double calculateHaversine(double lat1, double lon1, double lat2, double lon2) {
    double R = 6371.0;
    double dLat = (lat2 - lat1) * M_PI / 180.0;
    double dLon = (lon2 - lon1) * M_PI / 180.0;
    lat1 = lat1 * M_PI / 180.0;
    lat2 = lat2 * M_PI / 180.0;

    double a = sin(dLat / 2) * sin(dLat / 2) + sin(dLon / 2) * sin(dLon / 2) * cos(lat1) * cos(lat2);
    double c = 2 * atan2(sqrt(a), sqrt(1 - a));
    return R * c;
}

// Traffic multiplier: 1.0 = clear, 1.6 = heavy (rush hour me badi roads par)
double trafficMultiplier(bool isBig, int hour) {
    bool rush = (hour >= 8 && hour <= 10) || (hour >= 17 && hour <= 20);
    if (rush) return isBig ? 1.6 : 1.25;
    return isBig ? 1.1 : 1.0;
}

RouteResult aStarSearch(int start, int goal, unordered_map<int, Node>& nodes,
                        unordered_map<int, vector<Edge>>& graph, int hour) {
    RouteResult result;
    priority_queue<AStarNode, vector<AStarNode>, greater<AStarNode>> minHeap;
    unordered_map<int, double> g_costs;
    unordered_map<int, ParentInfo> parent;
    unordered_set<int> closed;

    g_costs[start] = 0.0;
    double h0 = calculateHaversine(nodes[start].lat, nodes[start].lon, nodes[goal].lat, nodes[goal].lon) / MAX_SPEED;
    minHeap.push({start, 0.0, h0});

    while (!minHeap.empty()) {
        AStarNode current = minHeap.top();
        minHeap.pop();

        if (closed.count(current.id)) continue;   // ye node pehle ho chuka
        closed.insert(current.id);

        if (current.id == goal) {
            // goal se start tak peeche chalke rasta banao
            int curr = goal;
            result.path.push_back(goal);
            while (curr != start) {
                ParentInfo p = parent[curr];
                result.km += p.distance;
                result.freeHours += p.distance / p.speed;
                curr = p.prev;
                result.path.push_back(curr);
            }
            reverse(result.path.begin(), result.path.end());
            result.trafficHours = g_costs[goal];
            result.found = true;
            return result;
        }

        auto it = graph.find(current.id);
        if (it == graph.end()) continue;

        for (const Edge& edge : it->second) {
            // TRAFFIC LOGIC: time = distance / speed * traffic multiplier
            double hours = edge.distance / edge.speed * trafficMultiplier(edge.isBig, hour);
            double new_g_cost = g_costs[current.id] + hours;

            if (g_costs.find(edge.target_id) == g_costs.end() || new_g_cost < g_costs[edge.target_id]) {
                g_costs[edge.target_id] = new_g_cost;
                double h_cost = calculateHaversine(nodes[edge.target_id].lat, nodes[edge.target_id].lon,
                                                   nodes[goal].lat, nodes[goal].lon) / MAX_SPEED;
                parent[edge.target_id] = {current.id, edge.distance, edge.speed};
                minHeap.push({edge.target_id, new_g_cost, new_g_cost + h_cost});
            }
        }
    }
    return result;   // found = false (rasta nahi mila)
}

// GPS point ke sabse paas ka node (jisse koi road nikalti ho)
int nearestNode(double lat, double lon, unordered_map<int, Node>& nodes,
                unordered_map<int, vector<Edge>>& graph) {
    int best = -1;
    double bestDist = 1e18;
    for (auto& entry : graph) {
        const Node& n = nodes[entry.first];
        double d = calculateHaversine(lat, lon, n.lat, n.lon);
        if (d < bestDist) { bestDist = d; best = entry.first; }
    }
    return best;
}

// Usage: RouteWiseEngine ROUTE graph.txt origin_lat origin_lon dest_lat dest_lon hour
// graph.txt format:  N, phir N lines "id lat lon", phir M, phir M lines "from to km speed isBig"
int runRouteMode(int argc, char* argv[]) {
    if (argc < 8) {
        cerr << "Error: ROUTE needs graph_file o_lat o_lon d_lat d_lon hour" << endl;
        return 1;
    }

    ifstream file(argv[2]);
    if (!file) {
        cerr << "Error: graph file not found." << endl;
        return 1;
    }

    double oLat, oLon, dLat, dLon;
    int hour;
    try {
        oLat = stod(argv[3]); oLon = stod(argv[4]);
        dLat = stod(argv[5]); dLon = stod(argv[6]);
        hour = stoi(argv[7]);
    } catch (const exception&) {
        cerr << "Error: Invalid numeric arguments." << endl;
        return 1;
    }

    unordered_map<int, Node> nodes;
    unordered_map<int, vector<Edge>> graph;

    int n;
    file >> n;
    for (int i = 0; i < n; i++) {
        Node node;
        file >> node.id >> node.lat >> node.lon;
        nodes[node.id] = node;
    }

    int m;
    file >> m;
    for (int i = 0; i < m; i++) {
        int from, to, big;
        Edge edge;
        file >> from >> to >> edge.distance >> edge.speed >> big;
        edge.target_id = to;
        edge.isBig = (big == 1);
        graph[from].push_back(edge);
    }

    int start = nearestNode(oLat, oLon, nodes, graph);
    int goal = nearestNode(dLat, dLon, nodes, graph);
    if (start == -1 || goal == -1) {
        cout << "NO_ROUTE" << endl;
        return 0;
    }

    RouteResult r = aStarSearch(start, goal, nodes, graph, hour);
    if (!r.found) {
        cout << "NO_ROUTE" << endl;
        return 0;
    }

    cout << fixed;
    cout << setprecision(4) << "DISTANCE_KM " << r.km << endl;
    cout << setprecision(0) << "TIME_MIN " << max(1.0, round(r.trafficHours * 60)) << endl;
    cout << "DELAY_MIN " << max(0.0, round((r.trafficHours - r.freeHours) * 60)) << endl;
    cout << setprecision(7);
    for (int id : r.path) {
        cout << "POINT " << nodes[id].lat << " " << nodes[id].lon << endl;
    }
    return 0;
}

// ============================================================
// PART 3: MAIN EXECUTION (Flask Entry Point: range + route)
// ============================================================

int main(int argc, char* argv[]) {
    // Route mode: Python se A* chalane ke liye
    if (argc >= 2 && string(argv[1]) == "ROUTE") {
        return runRouteMode(argc, argv);
    }

    if (argc < 6) {
        cerr << "Error: Missing arguments." << endl;
        return 1;
    }

    string type = argv[1];
    double percent, capacity, efficiency;
    try {
        percent = stod(argv[2]);
        capacity = stod(argv[3]);
        efficiency = stod(argv[4]);
    } catch (const exception&) {
        cerr << "Error: Invalid numeric arguments." << endl;
        return 1;
    }
    string connector = argv[5];

    Vehicle* myVehicle = nullptr;

    if (type == "PETROL" || type == "DIESEL") {
        myVehicle = new FuelVehicle(percent, capacity, efficiency);
    } else if (type == "EV") {
        myVehicle = new ElectricVehicle(percent, capacity, efficiency, connector);
    } else if (type == "HYBRID") {
        myVehicle = new HybridVehicle(percent, capacity, efficiency);
    } else {
        cerr << "Error: Unknown vehicle type." << endl;
        return 1;
    }

    double safeRange = myVehicle->calculateSafeRange();
    cout << fixed << setprecision(2);
    cout << "Calculated Safe Usable Range: " << safeRange << " km" << endl;

    delete myVehicle;
    return 0;
}