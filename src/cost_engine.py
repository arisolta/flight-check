from typing import Dict, List
from src.config import CostWeights
from src.static_graph import StaticFlightGraph


class CostEngine:
    """Calculates multi-objective scores for flight routes and itineraries."""

    def __init__(self, weights: CostWeights, static_graph: StaticFlightGraph):
        self.w_t = weights.weight_time
        self.w_p = weights.weight_price
        self.w_g = weights.weight_geo_deviation
        self.static_graph = static_graph

    def score_circuit(self, circuit_offers: List[Dict]) -> Dict:
        """
        Takes a list of leg offers representing a full circuit C = [home, d1, ..., dn, home]
        and computes total duration, total price, leg scores, and composite total score.
        """
        total_price = sum(offer["price_usd"] for offer in circuit_offers)
        total_duration_mins = sum(offer["duration_minutes"] for offer in circuit_offers)

        # Compute raw parameters for each leg
        durations = [offer["duration_minutes"] for offer in circuit_offers]
        prices = [offer["price_usd"] for offer in circuit_offers]
        
        geo_ratios = []
        for offer in circuit_offers:
            src_city = offer["origin_city"]
            dst_city = offer["destination_city"]
            gc_dist = self.static_graph.get_city_distance(src_city, dst_city)
            # Estimate actual flight distance from duration (assuming 750 km/h cruising) or GC dist minimum
            est_actual_dist = max(gc_dist, (offer["duration_minutes"] / 60.0) * 700.0)
            ratio = (est_actual_dist / gc_dist) if gc_dist > 0 else 1.0
            geo_ratios.append(ratio)

        # Min-Max Normalization across legs in this circuit (or set of options)
        def min_max_norm(values: List[float]) -> List[float]:
            min_v, max_v = min(values), max(values)
            if abs(max_v - min_v) < 1e-6:
                return [0.0 for _ in values]
            return [(v - min_v) / (max_v - min_v) for v in values]

        norm_t = min_max_norm([float(d) for d in durations])
        norm_p = min_max_norm(prices)
        norm_g = min_max_norm(geo_ratios)

        scored_legs = []
        total_composite_score = 0.0

        for i, offer in enumerate(circuit_offers):
            leg_score = (
                self.w_t * norm_t[i] +
                self.w_p * norm_p[i] +
                self.w_g * norm_g[i]
            )
            total_composite_score += leg_score
            
            leg_info = dict(offer)
            leg_info["leg_score"] = round(leg_score, 4)
            scored_legs.append(leg_info)

        return {
            "legs": scored_legs,
            "total_price_usd": round(total_price, 2),
            "total_duration_minutes": total_duration_mins,
            "total_duration_formatted": f"{total_duration_mins // 60}h {total_duration_mins % 60}m",
            "total_score": round(total_composite_score, 4),
        }
