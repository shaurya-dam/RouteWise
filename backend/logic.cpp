#include<iostream>
#include<string>
using namespace std;
class Car{
protected:
    string carType;
    double range;
    double fuelOrBatteryAmount;
    double averageOfCar;
    public:
    Car(string type, double r, double amount, double avg){
        carType=type;
        range=r;
        fuelOrBatteryAmount=amount;
        averageOfCar=avg;
    }
};
class Electric : public Car{
    public:
    Electric(double r, double batteryAmount, double avg) 
        : Car("Electric", r, batteryAmount, avg) {}

    void displayDetails() {
        cout << "[EV Module] Type: " << carType 
             << " | Total Range: " << range << " km"
             << " | Battery Amount: " << fuelOrBatteryAmount << " kWh"
             << " | Efficiency: " << averageOfCar << " km/kWh\n";
    }
};
class Petrol : public Car{
    Petrol(double r, double batteryAmount, double avg) : Car("Petrol",r,batteryAmount,avg){}
    void displayDetails(){
        cout << "[Petrol Module] Type" << carType
             <<" | Total Range: " << range << " km"
             << " | Fuel Amount: " << fuelOrBatteryAmount << " L"
             << " | Mileage: " << averageOfCar << " km/L"<<endl;
    }
};
class Hybrid : public Car{
    private:
    double electricPortionRange;
    double fuelPortionRange;

public:
    Hybrid(double r, double totalEnergy, double avg, double eRange, double fRange) 
        : Car("Hybrid", r, totalEnergy, avg), electricPortionRange(eRange), fuelPortionRange(fRange) {}

    void displayDetails() {
        cout << "[Hybrid Module] Type: " << carType 
             << " | Total Range: " << range << " km"
             << " | EV Range: " << electricPortionRange << " km"
             << " | Fuel Range: " << fuelPortionRange << " km\n";
    }
};
class Diesel : public Car{
    public:
    Diesel(double r, double batteryAmount, double avg) : Car("Diesel",r,batteryAmount,avg){}
    void displayDetails(){
        cout << "[Diesel Module] Type" << carType
             <<" | Total Range: " << range << " km"
             << " | Fuel Amount: " << fuelOrBatteryAmount << " L"
             << " | Mileage: " << averageOfCar << " km/L"<<endl;
    }
};
