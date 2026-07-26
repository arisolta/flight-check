# ✈️ Multi-Destination Direct Flight Route Optimizer (`flight-route-optimizer`)

A zero-cost Python CLI application that finds the most optimal multi-destination direct flight itinerary starting and ending at a home origin (e.g., `GVA -> LON -> EDI -> DUB -> LJU -> CPH -> STO -> GVA`).

It solves a modified Traveling Salesperson Problem (TSP) over $N$ destinations ($N \in [3, 6]$) subject to direct-flight graph constraints, flexible stay duration schedules, departure time preferences, and multi-objective optimization (flight time, price, and detour ratio).

---

## 🌟 Key Features

- **Zero-Cost & API-Free**: Uses OpenFlights static datasets for instant graph pruning without any paid API keys or subscriptions.
- **Direct Flights Only**: Non-direct (connecting) legs are pruned automatically.
- **Metropolitan City Abstraction**: Treats multi-airport hubs (e.g. `LON` covering `LHR`, `LGW`, `STN`) as single city nodes.
- **Flexible Stay Day Grid Search**: Define global stay day ranges (`min_stay_days_per_city`, `max_stay_days_per_city`) or custom per-city stay overrides (`city_stay_overrides`). The solver grid-searches valid stay combinations to optimize flight dates.
- **Departure Time Preferences**: Filter out late evening departures using `max_departure_hour` (e.g., 15:00 / 3 PM cutoff).
- **Line-by-Line Google Flights Links**: Direct search links for each individual leg.
- **1-Click Kayak Multi-City Booking**: Direct pre-filled multi-city booking links for the full circuit.

---

## 📁 Directory Structure

```text
flight-route-optimizer/
├── .gitignore
├── requirements.txt
├── config.json
├── README.md
├── data/
│   ├── routes.dat
│   └── airports.dat
├── cache/
│   └── flight_cache.json
├── src/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── static_graph.py
│   ├── flight_engine.py
│   ├── google_flights_scraper.py
│   ├── cost_engine.py
│   └── solver.py
└── tests/
    └── test_optimizer.py
```

---

## ⚙️ Configuration (`config.json`)

Customize your home city, destinations, start date, stay constraints, departure time cutoff, and scoring weights in `config.json`:

```json
{
  "trip_settings": {
    "home_city": "GVA",
    "destinations": ["DUB", "LON", "STO", "CPH", "LJU", "EDI"],
    "start_date": "2026-08-03",
    "min_stay_days_per_city": 2,
    "max_stay_days_per_city": 4,
    "city_stay_overrides": {
      "LON": { "min": 3, "max": 5 },
      "CPH": { "min": 2, "max": 3 }
    },
    "preferred_departure_window": "morning_afternoon",
    "max_departure_hour": 15
  },
  "cost_weights": {
    "weight_time": 0.5,
    "weight_price": 0.3,
    "weight_geo_deviation": 0.2
  },
  "cache_settings": {
    "cache_ttl_hours": 24,
    "cache_file": "cache/flight_cache.json"
  }
}
```

---

## 🚀 Quick Start & Usage

### 1. Setup Virtual Environment & Install Dependencies
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Run the Route Optimizer
```bash
python -m src.main --config config.json
```

### 3. Optional: Run with Headless Chromium Scraper
```bash
playwright install chromium
python -m src.main --scrape-google-flights
```

### 4. Run Unit Tests
```bash
python -m unittest discover -s tests
```

---

## 📐 Mathematical Cost Model

Each candidate circuit $C = [home, d_1, d_2, \dots, d_n, home]$ is evaluated using:

$$W(u, v) = w_t \cdot \hat{T}(u,v) + w_p \cdot \hat{P}(u,v) + w_g \cdot \hat{G}(u,v)$$

Where $w_t + w_p + w_g = 1.0$, and parameters are min-max normalized across all valid circuit permutations and stay schedules.
