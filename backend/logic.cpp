#include <iostream>
#include <string>
#include <vector>
#include <fstream>
#include <sstream>

using namespace std;

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
        return (currentPercent / 100.0) * capacity * efficiency * 0.80;
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
        return (currentPercent / 100.0) * capacity * efficiency * 0.85;
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
        return (currentPercent / 100.0) * capacity * efficiency * 0.90;
    }
    
    void displayInfo() const override {
        cout << "[Hybrid Vehicle] Fuel/Battery Combined: " << currentPercent << "%\n";
    }
};


struct ChargingStation {
    string name;
    double distance;
    string connector;
    double speed;
};

class RouteManager {
private:
    vector<ChargingStation> stations;

public:
    void loadStationsFromFile(string filename) {
        ifstream file(filename);
        string line;

        if (!file.is_open()) {
            cout << "Warning: stations.txt file not found! Using demo data...\n";
            stations.push_back({"Station Alpha", 45.0, "Type-2", 50.0});
            stations.push_back({"Station Beta", 120.0, "CCS2", 150.0});
            stations.push_back({"Station Gamma", 15.0, "Type-2", 22.0});
            stations.push_back({"Station Delta", 200.0, "Type-2", 100.0});
            return;
        }

        while (getline(file, line)) {
            stringstream ss(line);
            string id, name, dist_str, conn, speed_str;
            
            getline(ss, id, ','); 
            getline(ss, name, ','); 
            getline(ss, dist_str, ',');
            getline(ss, conn, ','); 
            getline(ss, speed_str, ',');

            stations.push_back({name, stod(dist_str), conn, stod(speed_str)});
        }
        file.close();
    }

    void planRoute(Car* userCar) {
        double currentRange = userCar->calculateUsableRange();
        
        cout << "\n------------------------------------------\n";
        userCar->displayInfo();
        cout << "Calculated Safe Range: " << currentRange << " km\n";
        cout << "------------------------------------------\n\n";

        bool foundCompatible = false;
        double nearestDist = 99999.0;
        string bestStation = "";

        cout << "--- Station Analysis ---\n";
        for (const auto& station : stations) {
            
            bool withinRange = (station.distance <= currentRange);
            
            bool isCompatible = true;
            if (userCar->getCarType() == "EV") {
                isCompatible = (station.connector == userCar->getConnector());
            }

            if (withinRange && isCompatible) {
                cout << "[REACHABLE] " << station.name << " (" << station.distance << " km)\n";
                foundCompatible = true;
                
                if (station.distance < nearestDist) {
                    nearestDist = station.distance;
                    bestStation = station.name;
                }
            }
        }

        cout << "\n==========================================\n";
        if (foundCompatible) {
            cout << ">> RECOMMENDED NEAREST STATION: " << bestStation << " (" << nearestDist << " km) <<\n";
        } else {
            cout << ">> ALERT: No reachable & compatible stations found! <<\n";
        }
        cout << "==========================================\n";
    }
};


int main(int argc, char* argv[]) {
    // 1. Argument Count Validation
    if (argc < 5) {
        cout << "Error: Missing parameters!\n";
        cout << "Usage: ./RouteWiseEngine <Type> <Percent> <Capacity> <Efficiency> [Connector] [FilePath]\n";
        cout << "Example: ./RouteWiseEngine EV 80 40 6 Type-2\n";
        return 1;
    }

    try {
        // 2. Command Line Arguments Read Karna
        string v_type = argv[1];
        double percent = stod(argv[2]);
        double capacity = stod(argv[3]);
        double efficiency = stod(argv[4]);
        
        string connector = (argc >= 6) ? argv[5] : "None";
        string filePath = (argc >= 7) ? argv[6] : "stations.txt"; // Dynamic path fallback

        Car* myCar = nullptr;

        // 3. Case-Insensitive Matching (Upper & Mixed Case Safety)
        if (v_type == "EV" || v_type == "Electric" || v_type == "ev") {
            myCar = new Electric(percent, capacity, efficiency, connector);
        } 
        else if (v_type == "PETROL" || v_type == "DIESEL" || v_type == "Petrol" || v_type == "Diesel") {
            myCar = new Petrol(percent, capacity, efficiency);
        } 
        else if (v_type == "HYBRID" || v_type == "Hybrid" || v_type == "hybrid") {
            myCar = new Hybrid(percent, capacity, efficiency);
        } 
        else {
            cout << "Error: Unknown Vehicle Type passed by Backend (" << v_type << ")!\n";
            return 1;
        }

        // 4. Engine Run & Execution
        RouteManager engine;
        engine.loadStationsFromFile(filePath);
        engine.planRoute(myCar);

        // Memory Freeing
        delete myCar;
        return 0;

    } catch (const exception& e) {
        // Safe Exception Handling for numeric conversion failures
        cout << "Error: Invalid numeric input from backend args (" << e.what() << ")\n";
        return 1;
    }
}