#include<iostream>
#include<string>
#include<vector>
#include<queue>
#include<fstream>
#include<sstream>
using namespace std;
class Vehicle {
protected:
    double max_range;
    double current_percent;
public:
    Vehicle(double m_range, double c_percent) {
        max_range = m_range;
        current_percent = c_percent;
    }
    virtual double calculateUsableRange() = 0; 
    virtual ~Vehicle() {}
};

class ElectricVehicle : public Vehicle {
public:
    ElectricVehicle(double m_range, double c_percent) : Vehicle(m_range, c_percent) {}
    double calculateUsableRange() override {
        return (max_range * (current_percent / 100.0)) * 0.85; 
    }
};

class FuelVehicle : public Vehicle {
public:
    FuelVehicle(double m_range, double c_percent) : Vehicle(m_range, c_percent) {}
    double calculateUsableRange() override {
        return (max_range * (current_percent / 100.0));
    }
};

class HybridVehicle : public Vehicle {
public:
    HybridVehicle(double m_range, double c_percent) : Vehicle(m_range, c_percent) {}
    double calculateUsableRange() override {
        return (max_range * (current_percent / 100.0)) * 0.95; 
    }
};
struct Station {
    string name;
    double dis;
    string type;
    int charging_speed;
    double score;
};

struct CompareStation {
    bool operator()(const Station& a, const Station& b) {
        return a.score > b.score; 
    }
};

class RouteWiseEngine {
public:
    void findBestStations(string filename, double current_range, string v_type, int top_n) {
        priority_queue<Station, vector<Station>, CompareStation> minHeap;
        ifstream fi(filename);
        string line;

        if (!fi.is_open()) {
            cout << "Error: Backend stations file missing!\n";
            return;
        }

        while (getline(fi, line)) {
            stringstream ss(line);
            string id, name, dist_str, type, speed_str;
            
            getline(ss, id, ','); 
            getline(ss, name, ','); 
            getline(ss, dist_str, ',');
            getline(ss, type, ','); 
            getline(ss, speed_str, ',');

            double dist = stod(dist_str);
            int speed = stoi(speed_str);

            bool isCompat = false;
            if (v_type == "Hybrid" && (type == "EV" || type == "Petrol")) {
                isCompat = true;
            } 
            else if (type == v_type) {
                isCompat = true; 
            }
            if (isCompat && dist <= current_range) {
                double score = (type == "EV") ? (dist - speed * 0.15) : dist;
                minHeap.push({name, dist, type, speed, score});
            }
        }
        fi.close();

        cout << "\n--- TOP " << top_n << " RECOMMENDED STATIONS ---\n";
        if (minHeap.empty()) {
            cout << "ALERT: No stations reachable within " << current_range << " km!\n";
            return;
        }
    }
};
