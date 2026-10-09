#include<iostream>
#include<string>

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
