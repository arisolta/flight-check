import csv
import os
import requests
from typing import Dict, List, Set, Tuple
from geopy.distance import great_circle

ROUTES_URL = "https://raw.githubusercontent.com/jpatokal/openflights/master/data/routes.dat"
AIRPORTS_URL = "https://raw.githubusercontent.com/jpatokal/openflights/master/data/airports.dat"

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
ROUTES_FILE = os.path.join(DATA_DIR, "routes.dat")
AIRPORTS_FILE = os.path.join(DATA_DIR, "airports.dat")

METRO_CITY_MAP: Dict[str, List[str]] = {
    "LON": ["LHR", "LGW", "STN", "LCY", "LTN", "SEN"],
    "NYC": ["JFK", "LGA", "EWR"],
    "PAR": ["CDG", "ORY", "BVA"],
    "STO": ["ARN", "BMA", "NYO", "VST"],
    "ROM": ["FCO", "CIA"],
    "TYO": ["HND", "NRT"],
    "MOW": ["SVO", "DME", "VKO", "ZIA"],
    "MIL": ["MXP", "LIN", "BGY"],
    "BER": ["BER", "TXL", "SXF"],
    "CHI": ["ORD", "MDW", "RFD"],
}


class StaticFlightGraph:
    """Static graph parser for OpenFlights airport and route datasets."""

    def __init__(self, data_dir: str = DATA_DIR):
        self.data_dir = data_dir
        self.routes_path = os.path.join(data_dir, "routes.dat")
        self.airports_path = os.path.join(data_dir, "airports.dat")
        
        self.airport_coords: Dict[str, Tuple[float, float]] = {}
        self.direct_routes: Set[Tuple[str, str]] = set()
        
        self._ensure_datasets()
        self._load_airports()
        self._load_routes()

    def _ensure_datasets(self) -> None:
        """Download datasets if not already present locally."""
        os.makedirs(self.data_dir, exist_ok=True)
        if not os.path.exists(self.airports_path):
            res = requests.get(AIRPORTS_URL, timeout=30)
            res.raise_for_status()
            with open(self.airports_path, "w", encoding="utf-8") as f:
                f.write(res.text)

        if not os.path.exists(self.routes_path):
            res = requests.get(ROUTES_URL, timeout=30)
            res.raise_for_status()
            with open(self.routes_path, "w", encoding="utf-8") as f:
                f.write(res.text)

    def _load_airports(self) -> None:
        """Parse OpenFlights airports.dat into IATA -> (lat, lon) mapping."""
        if not os.path.exists(self.airports_path):
            return

        with open(self.airports_path, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 8:
                    iata = row[4].replace('"', '').strip()
                    lat_str = row[6].strip()
                    lon_str = row[7].strip()
                    if iata and iata != "\\N" and len(iata) == 3:
                        try:
                            lat = float(lat_str)
                            lon = float(lon_str)
                            self.airport_coords[iata] = (lat, lon)
                        except ValueError:
                            continue

    def _load_routes(self) -> None:
        """Parse OpenFlights routes.dat into set of direct airport pairs."""
        if not os.path.exists(self.routes_path):
            return

        with open(self.routes_path, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 8:
                    src_apt = row[2].replace('"', '').strip()
                    dst_apt = row[4].replace('"', '').strip()
                    stops_str = row[7].strip()
                    
                    if src_apt and dst_apt and stops_str == "0":
                        self.direct_routes.add((src_apt, dst_apt))

    def get_airports_for_city(self, city_code: str) -> List[str]:
        """Returns airport IATA codes representing a metropolitan city."""
        code = city_code.strip().upper()
        return METRO_CITY_MAP.get(code, [code])

    def has_direct_city_flight(self, city_a: str, city_b: str) -> bool:
        """
        Returns True if ANY airport in city_a has a direct flight
        to ANY airport in city_b in the static dataset.
        """
        airports_a = self.get_airports_for_city(city_a)
        airports_b = self.get_airports_for_city(city_b)

        for src in airports_a:
            for dst in airports_b:
                if (src, dst) in self.direct_routes:
                    return True
        return False

    def get_city_coords(self, city_code: str) -> Tuple[float, float]:
        """Calculates central lat/lon coordinates for a city based on its airports."""
        airports = self.get_airports_for_city(city_code)
        coords = [self.airport_coords[apt] for apt in airports if apt in self.airport_coords]
        if not coords:
            # Fallback coordinates if city airport not found
            return (0.0, 0.0)
        avg_lat = sum(c[0] for c in coords) / len(coords)
        avg_lon = sum(c[1] for c in coords) / len(coords)
        return (avg_lat, avg_lon)

    def get_city_distance(self, city_a: str, city_b: str) -> float:
        """Calculates Great-Circle distance in km between two cities."""
        coords_a = self.get_city_coords(city_a)
        coords_b = self.get_city_coords(city_b)
        if coords_a == (0.0, 0.0) or coords_b == (0.0, 0.0):
            return 1000.0  # Fallback distance in km
        return great_circle(coords_a, coords_b).kilometers
