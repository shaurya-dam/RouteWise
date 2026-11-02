#include <iostream>
#include <string>
#include <vector>
#include <queue>
#include <cmath>
#include <unordered_map>

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
// ============================================================

struct Node {
    int id;
    double lat, lon;
};

struct Edge {
    int target_id;
    double distance;
    double traffic_multiplier; // 1.0 = Clear, 1.5 = Heavy, 2.0 = Jam
};

struct AStarNode {
    int id;
    double g_cost; 
    double f_cost; 

    bool operator>(const AStarNode& other) const {
        return f_cost > other.f_cost;
    }
};

double calculateHaversine(double lat1, double lon1, double lat2, double lon2) {
    double R = 6371.0; 
    double dLat = (lat2 - lat1) * M_PI / 180.0;
    double dLon = (lon2 - lon1) * M_PI / 180.0;
    lat1 = lat1 * M_PI / 180.0;
    lat2 = lat2 * M_PI / 180.0;

    double a = sin(dLat/2) * sin(dLat/2) + sin(dLon/2) * sin(dLon/2) * cos(lat1) * cos(lat2);
    double c = 2 * atan2(sqrt(a), sqrt(1-a));
    return R * c;
}

vector<int> aStarSearch(int start, int goal, unordered_map<int, Node>& nodes, unordered_map<int, vector<Edge>>& graph) {
    priority_queue<AStarNode, vector<AStarNode>, greater<AStarNode>> minHeap;
    unordered_map<int, double> g_costs;
    unordered_map<int, int> parent;
    
    g_costs[start] = 0.0;
    double initial_h = calculateHaversine(nodes[start].lat, nodes[start].lon, nodes[goal].lat, nodes[goal].lon);
    minHeap.push({start, 0.0, initial_h});
    
    while (!minHeap.empty()) {
        AStarNode current = minHeap.top();
        minHeap.pop();
        
        if (current.id == goal) {
            vector<int> path;
            int curr = goal;
            while (curr != start) {
                path.push_back(curr);
                curr = parent[curr];
            }
            path.push_back(start);
            return path; 
        }
        
        for (const Edge& edge : graph[current.id]) {
            // TRAFFIC LOGIC: Distance * Traffic Multiplier = Effective Time Cost
            double effective_cost = edge.distance * edge.traffic_multiplier;
            double new_g_cost = g_costs[current.id] + effective_cost;
            
            if (g_costs.find(edge.target_id) == g_costs.end() || new_g_cost < g_costs[edge.target_id]) {
                g_costs[edge.target_id] = new_g_cost;
                double h_cost = calculateHaversine(nodes[edge.target_id].lat, nodes[edge.target_id].lon, nodes[goal].lat, nodes[goal].lon);
                double f_cost = new_g_cost + h_cost;
                
                parent[edge.target_id] = current.id;
                minHeap.push({edge.target_id, new_g_cost, f_cost});
            }
        }
    }
    return {}; 
}

// ============================================================
// PART 3: MAIN EXECUTION (Flask Entry Point)
// ============================================================

int main(int argc, char* argv[]) {
    if (argc < 6) {
        cerr << "Error: Missing arguments." << endl;
        return 1;
    }

    string type = argv[1];
    double percent = stod(argv[2]);
    double capacity = stod(argv[3]);
    double efficiency = stod(argv[4]);
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
    cout << "Calculated Safe Usable Range: " << safeRange << " km" << endl;

    delete myVehicle;
    return 0;
}