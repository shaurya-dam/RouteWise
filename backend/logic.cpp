#include <iostream>
#include <string>
#include <vector>
#include <sstream>
#include <queue>
#include <unordered_map>
#include <algorithm>
#include <limits>

using namespace std;

// ==========================================
// 1. OOP: VEHICLE CLASSES
// ==========================================
class Car {
protected:
    string carType;
    double currentPercent;
    double capacity;
    double efficiency;
    string preferredConnector;

public:
    Car(string type, double percent, double cap, double eff, string conn) {
        carType = type;
        currentPercent = percent;
        capacity = cap;
        efficiency = eff;
        preferredConnector = conn;
    }

    string getCarType() const { return carType; }
    string getConnector() const { return preferredConnector; }

    virtual double calculateUsableRange() = 0; 
    virtual ~Car() {}
};

class Electric : public Car {
public:
    Electric(double percent, double cap, double eff, string conn) 
        : Car("EV", percent, cap, eff, conn) {}

    double calculateUsableRange() override {
        return (currentPercent / 100.0) * capacity * efficiency * 0.80;
    }
};

class Petrol : public Car {
public:
    Petrol(double percent, double cap, double eff) 
        : Car("PETROL", percent, cap, eff, "None") {}

    double calculateUsableRange() override {
        return (currentPercent / 100.0) * capacity * efficiency * 0.85;
    }
};

class Hybrid : public Car {
public:
    Hybrid(double percent, double cap, double eff) 
        : Car("HYBRID", percent, cap, eff, "Type-2") {}

    double calculateUsableRange() override {
        return (currentPercent / 100.0) * capacity * efficiency * 0.90;
    }
};

// ==========================================
// 2. DSA: GRAPH ROUTING (DIJKSTRA'S ALGO)
// ==========================================
struct Edge {
    string targetNode;
    double roadDistance;
};

class MapGraph {
private:
    unordered_map<string, vector<Edge>> adjList;

public:
    void addRoad(const string& from, const string& to, double distance) {
        adjList[from].push_back({to, distance});
        adjList[to].push_back({from, distance}); // 2-way road
    }

    string getShortestRoute(const string& start, const string& destination) {
        unordered_map<string, double> minDistance;
        unordered_map<string, string> previousNode;
        priority_queue<pair<double, string>, vector<pair<double, string>>, greater<pair<double, string>>> pq;

        for (const auto& pair : adjList) {
            minDistance[pair.first] = numeric_limits<double>::infinity();
        }

        minDistance[start] = 0.0;
        pq.push({0.0, start});

        while (!pq.empty()) {
            double currentDist = pq.top().first;
            string currentNode = pq.top().second;
            pq.pop();

            if (currentNode == destination) break;
            if (currentDist > minDistance[currentNode]) continue;

            for (const auto& neighbor : adjList[currentNode]) {
                double newDist = currentDist + neighbor.roadDistance;
                if (newDist < minDistance[neighbor.targetNode]) {
                    minDistance[neighbor.targetNode] = newDist;
                    previousNode[neighbor.targetNode] = currentNode;
                    pq.push({newDist, neighbor.targetNode});
                }
            }
        }

        if (minDistance.find(destination) == minDistance.end() || minDistance[destination] == numeric_limits<double>::infinity()) {
            return "NO_ROUTE_FOUND";
        }

        vector<string> path;
        string curr = destination;
        while (curr != start) {
            path.push_back(curr);
            curr = previousNode[curr];
        }
        path.push_back(start);
        reverse(path.begin(), path.end());

        string fullPath = "";
        for (size_t i = 0; i < path.size(); i++) {
            fullPath += path[i] + (i == path.size() - 1 ? "" : " -> ");
        }
        return fullPath + " (" + to_string(minDistance[destination]) + " km)";
    }
};

// ==========================================
// 3. DSA: PRIORITY QUEUE LOGIC
// ==========================================
struct ChargingStation {
    string name;
    double distance;
    string connector;
    double speed;
};

struct CompareDistance {
    bool operator()(ChargingStation const& s1, ChargingStation const& s2) {
        return s1.distance > s2.distance; 
    }
};

class RouteManager {
private:
    vector<ChargingStation> stations;
    MapGraph cityMap; // Graph object add kiya

public:
    // Demo ke liye kuch roads add kar rahe hain (Python se bhi aa sakti hain baad me)
    RouteManager() {
        cityMap.addRoad("CurrentLocation", "Highway 1", 10.0);
        cityMap.addRoad("Highway 1", "Station Alpha", 35.0);
        cityMap.addRoad("CurrentLocation", "City Center", 15.0);
        cityMap.addRoad("City Center", "Station Beta", 100.0);
    }

    void loadStationsFromBackend() {
        string line;
        while (getline(cin, line)) {
            if (line.empty()) continue;
            
            stringstream ss(line);
            string name, dist_str, conn, speed_str;
            
            getline(ss, name, ','); 
            getline(ss, dist_str, ',');
            getline(ss, conn, ','); 
            getline(ss, speed_str, ',');

            stations.push_back({name, stod(dist_str), conn, stod(speed_str)});
        }
    }

    void planRoute(Car* userCar) {
        double currentRange = userCar->calculateUsableRange();
        priority_queue<ChargingStation, vector<ChargingStation>, CompareDistance> minHeap;

        for (const auto& station : stations) {
            bool withinRange = (station.distance <= currentRange);
            bool isCompatible = (userCar->getCarType() != "EV" || station.connector == userCar->getConnector());

            if (withinRange && isCompatible) {
                minHeap.push(station);
            }
        }

        if (!minHeap.empty()) {
            ChargingStation nearest = minHeap.top();
            
            // Graph se route nikalna
            string routePath = cityMap.getShortestRoute("CurrentLocation", nearest.name);

            // Python ko sab kuch ek sath bhejna
            cout << "SUCCESS|" << nearest.name << "|" << nearest.distance << "|" 
                 << nearest.connector << "|" << routePath << "\n";
        } else {
            cout << "FAILED|No reachable stations found.\n";
        }
    }
};

// ==========================================
// 4. MAIN ENTRY POINT
// ==========================================
int main(int argc, char* argv[]) {
    if (argc < 5) {
        cout << "FAILED|Invalid arguments passed from backend.\n";
        return 1;
    }

    string v_type = argv[1];
    double percent = stod(argv[2]);
    double capacity = stod(argv[3]);
    double efficiency = stod(argv[4]);
    string connector = (argc >= 6) ? argv[5] : "None";

    Car* myCar = nullptr;
    if (v_type == "EV") myCar = new Electric(percent, capacity, efficiency, connector);
    else if (v_type == "PETROL" || v_type == "DIESEL") myCar = new Petrol(percent, capacity, efficiency);
    else if (v_type == "HYBRID") myCar = new Hybrid(percent, capacity, efficiency);
    else {
        cout << "FAILED|Unknown Vehicle Type.\n";
        return 1;
    }

    RouteManager engine;
    engine.loadStationsFromBackend(); 
    engine.planRoute(myCar); 

    delete myCar;
    return 0;
}