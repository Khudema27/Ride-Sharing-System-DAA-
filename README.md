# 🚗 Real-Time Dynamic Ride Sharing System

A Python simulation of a ride-sharing service (like Uber/Careem) built on the real **Islamabad–Rawalpindi** road network. Matches passengers to drivers, optimizes routes, simulates live GPS, and calculates fares.


## ✨ Features
- Real map data — 15 actual locations with GPS coordinates
- Graph-based routing with **Dijkstra** and **A\*** algorithms
- Smart passenger matching with shared ride validation
- Live GPS step-by-step simulation with ETA
- Dynamic fare calculation with shared discount
- Tkinter GUI + Console input modes
- Static PNG and interactive HTML map outputs


## ⚙️ Installation
pip install networkx matplotlib folium
python Ride_Sharing_System.py


## 🚀 How to Use
1. Choose **GUI** or **Console** mode
2. Select role — **Passenger** or **Driver** each round
3. Enter your details (name, location, preferences)
4. System auto-matches, simulates the trip, and calculates fares
5. Select **Finish** to generate the final summary and map visuals

## 💰 Fare Formula
Fare = Rs. 80 + (km × Rs. 45) + (minutes × Rs. 8)
Shared ride = 20% discount applied

## 📦 Dependencies

| Package | Required |
|---------|----------|
| `networkx` | ✅ Yes |
| `matplotlib` | ⚠️ Optional |
| `folium` | ⚠️ Optional |
| `tkinter` | ⚠️ Optional |

## 🎓 Context
Developed as a **Design and Analysis of Algorithms (DAA)** course project to demonstrate graph theory and pathfinding in a real-world scenario.

## 📄 License
This project was developed as part of an academic submission. All rights reserved.
