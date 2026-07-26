import json
import os
import time
from typing import Dict, Optional
from src.static_graph import StaticFlightGraph


class FlightEngine:
    """Zero-cost flight engine using static OpenFlights graph and disk caching."""

    def __init__(
        self,
        cache_file: str = "cache/flight_cache.json",
        cache_ttl_hours: int = 24,
        static_graph: Optional[StaticFlightGraph] = None,
    ):
        self.cache_file = cache_file
        self.cache_ttl_seconds = cache_ttl_hours * 3600
        self.static_graph = static_graph or StaticFlightGraph()
        self.cache: Dict[str, Dict] = self._load_cache()

    def _load_cache(self) -> Dict[str, Dict]:
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_cache(self) -> None:
        os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, indent=2)
        except Exception as e:
            print(f"Warning: Failed to save cache: {e}")

    def get_direct_city_offer(self, city_a: str, city_b: str, date: str) -> Optional[Dict]:
        """
        Retrieves direct route data between city_a and city_b for a given date.
        Returns None if no direct route exists in OpenFlights.
        """
        cache_key = f"{city_a}-{city_b}-{date}"
        now = time.time()

        if cache_key in self.cache:
            cached_item = self.cache[cache_key]
            timestamp = cached_item.get("timestamp", 0)
            if (now - timestamp) < self.cache_ttl_seconds:
                offer = cached_item.get("offer")
                if offer is not None:
                    offer["cached"] = True
                return offer

        if not self.static_graph.has_direct_city_flight(city_a, city_b):
            return None

        dist_km = self.static_graph.get_city_distance(city_a, city_b)
        duration_mins = int((dist_km / 700.0) * 60 + 40)
        base_price = round(40.0 + dist_km * 0.08, 2)
        
        airports_a = self.static_graph.get_airports_for_city(city_a)
        airports_b = self.static_graph.get_airports_for_city(city_b)

        offer = {
            "origin": airports_a[0],
            "destination": airports_b[0],
            "origin_city": city_a,
            "destination_city": city_b,
            "price_usd": base_price,
            "duration_minutes": duration_mins,
            "carrier": "EST",
            "cached": False,
        }

        self.cache[cache_key] = {
            "timestamp": now,
            "offer": offer,
        }
        self._save_cache()

        return offer
