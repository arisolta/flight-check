import unittest
import os
import json
from src.config import load_config, AppConfig, TripSettings, CostWeights, CacheSettings
from src.static_graph import StaticFlightGraph
from src.flight_engine import FlightEngine
from src.cost_engine import CostEngine
from src.solver import find_optimal_routes


class TestFlightOptimizer(unittest.TestCase):

    def test_config_validation(self):
        config = load_config("config.json")
        self.assertEqual(config.trip_settings.home_city, "GVA")
        self.assertEqual(len(config.trip_settings.destinations), 6)
        self.assertAlmostEqual(
            config.cost_weights.weight_time + config.cost_weights.weight_price + config.cost_weights.weight_geo_deviation,
            1.0,
        )
        self.assertEqual(config.trip_settings.min_stay_days_per_city, 2)
        self.assertEqual(config.trip_settings.max_stay_days_per_city, 4)

    def test_city_stay_overrides(self):
        config = load_config("config.json")
        stay_lon = config.trip_settings.get_stay_days_for_city("LON")
        stay_dub = config.trip_settings.get_stay_days_for_city("DUB")
        self.assertEqual(stay_lon, 4)  # (3 + 5) // 2
        self.assertEqual(stay_dub, 3)  # (2 + 4) // 2

    def test_invalid_weights(self):
        with self.assertRaises(ValueError):
            CostWeights(weight_time=0.5, weight_price=0.5, weight_geo_deviation=0.5)

    def test_static_graph(self):
        graph = StaticFlightGraph()
        self.assertTrue(graph.has_direct_city_flight("LON", "PAR"))
        dist = graph.get_city_distance("GVA", "LON")
        self.assertGreater(dist, 500.0)

    def test_solver_execution(self):
        config = load_config("config.json")
        results = find_optimal_routes(config)
        self.assertEqual(results["total_permutations"], 720)
        self.assertGreater(results["valid_itineraries_count"], 0)
        top_route = results["itineraries"][0]
        self.assertTrue(top_route["route_string"].startswith("GVA"))
        self.assertTrue(top_route["route_string"].endswith("GVA"))


if __name__ == "__main__":
    unittest.main()
