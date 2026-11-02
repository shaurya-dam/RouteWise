#include <iostream>
#include <string>
#include <vector>
#include <fstream>
#include <sstream>
#include <algorithm>
#include <cmath>
#include <queue>
#include <unordered_map>
#include <limits>
#include <stdexcept>

using namespace std;

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

// ==========================================
// 1. OOP BASE & DERIVED CLASSES (VEHICLE MODULE)
// ==========================================
class Car {
protected:
    string carType;
    double currentPercent;
    double capacity;
    double efficiency;
    string preferredConnector;

public:
    Car(string type, double percent, double cap, double eff, string conn)
        : carType(type), currentPercent(percent), capacity(cap), efficiency(eff), preferredConnector(conn) {}

    string getCarType() const { return carType; }
    string getConnector() const { return preferredConnector; }

    virtual double calculateUsableRange() = 0; 

    virtual void displayInfo() const {
        cout << "Vehicle: " << carType << " | Energy Level: " << currentPercent << "%\n";
    }

    virtual ~Car() {}
};

class Electric : public Car {
public:
    Electric(double percent, double cap, double eff, string conn) 
        : Car("EV", percent, cap, eff, conn) {}

    double calculateUsableRange() override {
        return (currentPercent / 100.0) * capacity * efficiency * 0.80; // 80% safe buffer
    }

    void displayInfo() const override {
        cout << "[Electric Vehicle] Battery: " << currentPercent 
             << "% | Plug: " << preferredConnector << "\n";
    }
};

class Petrol : public Car {
public:
    Petrol(double percent, double cap, double eff) 
        : Car("PETROL", percent, cap, eff, "None") {}

    double calculateUsableRange() override {
        return (currentPercent / 100.0) * capacity * efficiency * 0.85; // 85% safe buffer
    }

    void displayInfo() const override {
        cout << "[Petrol Vehicle] Fuel: " << currentPercent << "%\n";
    }
};

class Hybrid : public Car {
public:
    Hybrid(double percent, double cap, double eff) 
        : Car("HYBRID", percent, cap, eff, "Type-2") {}

    double calculateUsableRange() override {
        return (currentPercent / 100.0) * capacity * efficiency * 0.90; // 90% safe buffer
    }
    
    void displayInfo() const override {
        cout << "[Hybrid Vehicle] Fuel/Battery Combined: " << currentPercent << "%\n";
    }
};

// ==========================================
// 2. HAVERSINE HEURISTIC & STATION STRUCTURE
// ==========================================
inline double haversineDistance(double lat1, double lon1, double lat2, double lon2) {
    double R = 6371.0; // Earth radius in km
    double dLat = (lat2 - lat1) * M_PI / 180.0;
    double dLon = (lon2 - lon1) * M_PI / 180.0;
    double a = sin(dLat / 2) * sin(dLat / 2) +
               cos(lat1 * M_PI / 180.0) * cos(lat2 * M_PI / 180.0) *
               sin(dLon / 2) * sin(dLon / 2);
    return R * 2 * atan2(sqrt(a), sqrt(1.0 - a));
}

struct ChargingStation {
    int id;
    string name;
    double lat;
    double lon;
    double distance;
    string connector;
    double speed;
};

// ==========================================
// 3. A* GRAPH ROUTER MODULE (PATHFINDING)
// ==========================================
struct MapNode {
    int id;
    double lat;
    double lon;
};

struct Edge {
    int targetNodeId;
    double distance;
};

struct AStarElement {
    int nodeId;
    double fScore;

    bool operator>(const AStarElement& other) const {
        return fScore > other.fScore;
    }
};

class GraphRouter {
private:
    unordered_map<int, vector<Edge>> graph;
    unordered_map<int, MapNode> mapNodes;

public:
    void addNode(int id, double lat, double lon) {
        mapNodes[id] = {id, lat, lon};
    }

    void addEdge(int u, int v, double dist) {
        graph[u].push_back({v, dist});
        graph[v].push_back({u, dist}); // Two-way road
    }

    vector<MapNode> findShortestPathAStar(int startId, int goalId) {
        priority_queue<AStarElement, vector<AStarElement>, greater<AStarElement>> openSet;
        unordered_map<int, double> gScore;
        unordered_map<int, double> fScore;
        unordered_map<int, int> cameFrom;

        for (const auto& pair : mapNodes) {
            gScore[pair.first] = numeric_limits<double>::infinity();
            fScore[pair.first] = numeric_limits<double>::infinity();
        }

        if (mapNodes.find(startId) == mapNodes.end() || mapNodes.find(goalId) == mapNodes.end()) {
            return {};
        }

        gScore[startId] = 0.0;
        double hStart = haversineDistance(mapNodes[startId].lat, mapNodes[startId].lon,
                                          mapNodes[goalId].lat, mapNodes[goalId].lon);
        fScore[startId] = hStart;
        openSet.push({startId, hStart});

        while (!openSet.empty()) {
            int current = openSet.top().nodeId;
            openSet.pop();

            if (current == goalId) {
                vector<MapNode> path;
                int temp = goalId;
                while (temp != startId) {
                    path.push_back(mapNodes[temp]);
                    temp = cameFrom[temp];
                }
                path.push_back(mapNodes[startId]);
                reverse(path.begin(), path.end());
                return path;
            }

            for (const auto& edge : graph[current]) {
                int neighbor = edge.targetNodeId;
                double tentative_gScore = gScore[current] + edge.distance;

                if (tentative_gScore < gScore[neighbor]) {
                    cameFrom[neighbor] = current;
                    gScore[neighbor] = tentative_gScore;
                    double h = haversineDistance(mapNodes[neighbor].lat, mapNodes[neighbor].lon,
                                                mapNodes[goalId].lat, mapNodes[goalId].lon);
                    fScore[neighbor] = gScore[neighbor] + h;
                    openSet.push({neighbor, fScore[neighbor]});
                }
            }
        }
        return {};
    }
};

// ==========================================
// 4. ROUTE MANAGER (PIPELINE EXECUTOR)
// ==========================================
class RouteManager {
private:
    vector<ChargingStation> stations;

public:
    void loadStationsFromFile(const string& filename, double userLat, double userLon) {
        ifstream file(filename);
        string line;

        if (!file.is_open()) {
            // Default demo stations in Dehradun area
            stations.push_back({101, "Station Alpha", 30.3250, 78.0400, haversineDistance(userLat, userLon, 30.3250, 78.0400), "Type-2", 50.0});
            stations.push_back({102, "Station Beta",  30.3400, 78.0600, haversineDistance(userLat, userLon, 30.3400, 78.0600), "CCS2", 150.0});
            stations.push_back({103, "Station Gamma", 30.3100, 78.0500, haversineDistance(userLat, userLon, 30.3100, 78.0500), "Type-2", 22.0});
            return;
        }

        while (getline(file, line)) {
            if (line.empty()) continue;
            stringstream ss(line);
            string idStr, name, distStr, conn, speedStr, latStr, lonStr;

            getline(ss, idStr, ',');
            getline(ss, name, ',');
            getline(ss, distStr, ',');
            getline(ss, conn, ',');
            getline(ss, speedStr, ',');
            getline(ss, latStr, ',');
            getline(ss, lonStr, ',');

            try {
                int id = idStr.empty() ? 101 : stoi(idStr);
                double lat = latStr.empty() ? 30.3250 : stod(latStr);
                double lon = lonStr.empty() ? 78.0400 : stod(lonStr);
                double dist = haversineDistance(userLat, userLon, lat, lon);
                double speed = speedStr.empty() ? 50.0 : stod(speedStr);

                stations.push_back({id, name, lat, lon, dist, conn, speed});
            } catch (...) {
                continue;
            }
        }
        file.close();
    }

    void executePipeline(Car* userCar, double userLat, double userLon) {
        double usableRange = userCar->calculateUsableRange();

        cout << "\n------------------------------------------\n";
        userCar->displayInfo();
        // Exact string required for app.py regex match
        cout << "Calculated Safe Usable Range: " << usableRange << " km\n";
        cout << "------------------------------------------\n\n";

        bool foundValid = false;
        double minDistance = 999999.0;
        ChargingStation recommendedStation;

        cout << "--- Station Analysis ---\n";
        for (const auto& st : stations) {
            bool withinRange = (st.distance <= usableRange);
            bool isCompatible = true;
            if (userCar->getCarType() == "EV") {
                isCompatible = (st.connector == userCar->getConnector() || st.connector == "Type-2" || st.connector == "CCS2");
            }

            if (withinRange && isCompatible) {
                cout << "[REACHABLE] " << st.name << " (" << st.distance << " km) | Plug: " << st.connector << "\n";
                foundValid = true;
                if (st.distance < minDistance) {
                    minDistance = st.distance;
                    recommendedStation = st;
                }
            } else if (withinRange && !isCompatible) {
                cout << "[CONNECTOR MISMATCH] " << st.name << " (" << st.distance << " km)\n";
            } else {
                cout << "[OUT OF RANGE] " << st.name << " (" << st.distance << " km)\n";
            }
        }

        if (!foundValid) {
            cout << "\n>> ALERT: No reachable & compatible stations found within safe range! <<\n";
            return;
        }

        cout << "\n>> RECOMMENDED TARGET STATION: " << recommendedStation.name << " (" << recommendedStation.distance << " km) <<\n";

        // ============================================================
        // A* ROAD GRAPH ROUTING EXECUTION
        // ============================================================
        GraphRouter router;

        int startNodeId = 1;
        int targetNodeId = recommendedStation.id;

        // Construct Map Nodes (User Location -> Junctions -> Station)
        router.addNode(startNodeId, userLat, userLon);
        router.addNode(2, userLat + 0.005, userLon + 0.003);
        router.addNode(3, userLat + 0.008, userLon + 0.006);
        router.addNode(targetNodeId, recommendedStation.lat, recommendedStation.lon);

        // Construct Weighted Edges
        router.addEdge(startNodeId, 2, haversineDistance(userLat, userLon, userLat + 0.005, userLon + 0.003));
        router.addEdge(2, 3, haversineDistance(userLat + 0.005, userLon + 0.003, userLat + 0.008, userLon + 0.006));
        router.addEdge(3, targetNodeId, haversineDistance(userLat + 0.008, userLon + 0.006, recommendedStation.lat, recommendedStation.lon));

        // Execute A* Pathfinding
        vector<MapNode> routePath = router.findShortestPathAStar(startNodeId, targetNodeId);

        // JSON Output format for Flask & Leaflet.js
        cout << "\n--- A* ROUTE COORDINATES JSON ---\n";
        cout << "{\n";
        cout << "  \"target_station\": \"" << recommendedStation.name << "\",\n";
        cout << "  \"target_station_id\": " << recommendedStation.id << ",\n";
        cout << "  \"route_coordinates\": [\n";
        for (size_t i = 0; i < routePath.size(); ++i) {
            cout << "    [" << routePath[i].lat << ", " << routePath[i].lon << "]"
                 << (i + 1 < routePath.size() ? ",\n" : "\n");
        }
        cout << "  ]\n";
        cout << "}\n";
    }
};

// ==========================================
// 5. MAIN CLI FUNCTION
// ==========================================
int main(int argc, char* argv[]) {
    if (argc < 5) {
        cout << "Error: Missing parameters!\n";
        cout << "Usage: ./RouteWiseEngine <Type> <Percent> <Capacity> <Efficiency> [Connector] [FilePath]\n";
        return 1;
    }

    try {
        string v_type = argv[1];
        double percent = stod(argv[2]);
        double capacity = stod(argv[3]);
        double efficiency = stod(argv[4]);
        string connector = (argc >= 6) ? argv[5] : "Type-2";
        string filePath = (argc >= 7) ? argv[6] : "stations.txt";

        double defaultUserLat = 30.3165; // Default center (Dehradun)
        double defaultUserLon = 78.0322;

        Car* myCar = nullptr;

        string typeUpper = v_type;
        transform(typeUpper.begin(), typeUpper.end(), typeUpper.begin(), ::toupper);

        if (typeUpper == "EV" || typeUpper == "ELECTRIC") {
            myCar = new Electric(percent, capacity, efficiency, connector);
        } else if (typeUpper == "PETROL" || typeUpper == "DIESEL") {
            myCar = new Petrol(percent, capacity, efficiency);
        } else if (typeUpper == "HYBRID") {
            myCar = new Hybrid(percent, capacity, efficiency);
        } else {
            cout << "Error: Unknown Vehicle Type (" << v_type << ")!\n";
            return 1;
        }

        RouteManager engine;
        engine.loadStationsFromFile(filePath, defaultUserLat, defaultUserLon);
        engine.executePipeline(myCar, defaultUserLat, defaultUserLon);

        delete myCar;
        return 0;

    } catch (const exception& e) {
        cout << "Error: Invalid numeric arguments (" << e.what() << ")\n";
        return 1;
    }
}