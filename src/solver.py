import itertools
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from src.config import AppConfig
from src.static_graph import StaticFlightGraph
from src.flight_engine import FlightEngine
from src.cost_engine import CostEngine


def find_optimal_routes(config: AppConfig) -> Dict[str, any]:
    """
    Solves the multi-destination flight route optimization problem.
    Performs Static Graph Pruning and Stay Duration Grid Search to find
    the optimal city route order AND cheapest/optimal stay duration schedule.
    """
    home = config.trip_settings.home_city
    destinations = config.trip_settings.destinations
    start_date_str = config.trip_settings.start_date

    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")

    static_graph = StaticFlightGraph()
    flight_engine = FlightEngine(
        cache_file=config.cache_settings.cache_file,
        cache_ttl_hours=config.cache_settings.cache_ttl_hours,
        static_graph=static_graph,
    )
    cost_engine = CostEngine(config.cost_weights, static_graph)

    # 1. Generate all permutations
    all_perms = list(itertools.permutations(destinations))
    total_permutations = len(all_perms)

    surviving_circuits = []
    pruned_by_static_graph = 0
    schedules_evaluated = 0

    # 2 & 3. Build circuits and perform Static Pruning
    for perm in all_perms:
        circuit_cities = [home] + list(perm) + [home]
        
        valid_static = True
        for i in range(len(circuit_cities) - 1):
            src_city = circuit_cities[i]
            dst_city = circuit_cities[i + 1]
            if not static_graph.has_direct_city_flight(src_city, dst_city):
                valid_static = False
                break

        if not valid_static:
            pruned_by_static_graph += 1
            continue

        # 4. Stay Duration Grid Search for this route permutation
        dest_cities = list(perm)
        stay_ranges = [config.trip_settings.get_stay_range_for_city(c) for c in dest_cities]
        stay_options = [list(range(r[0], r[1] + 1)) for r in stay_ranges]

        best_circuit_offers = None
        best_circuit_price = float("inf")

        for stay_tuple in itertools.product(*stay_options):
            schedules_evaluated += 1
            current_date = start_date
            circuit_offers = []
            valid_schedule = True

            for i in range(len(circuit_cities) - 1):
                src_city = circuit_cities[i]
                dst_city = circuit_cities[i + 1]
                leg_date_str = current_date.strftime("%Y-%m-%d")

                offer = flight_engine.get_direct_city_offer(src_city, dst_city, leg_date_str)
                if offer is None:
                    valid_schedule = False
                    break
                
                offer_copy = dict(offer)
                offer_copy["departure_date"] = leg_date_str
                
                # Stay duration spent in dst_city
                stay_days = stay_tuple[i] if i < len(stay_tuple) else 0
                offer_copy["stay_days"] = stay_days
                circuit_offers.append(offer_copy)

                current_date += timedelta(days=stay_days)

            if not valid_schedule:
                continue

            tot_price = sum(leg["price_usd"] for leg in circuit_offers)
            if tot_price < best_circuit_price:
                best_circuit_price = tot_price
                best_circuit_offers = circuit_offers

        if best_circuit_offers:
            surviving_circuits.append(best_circuit_offers)

    # 5. Global Multi-Objective Cost Normalization across optimal candidate schedules
    scored_itineraries = []

    if surviving_circuits:
        durations = [sum(leg["duration_minutes"] for leg in c) for c in surviving_circuits]
        prices = [sum(leg["price_usd"] for leg in c) for c in surviving_circuits]
        
        detours = []
        for c in surviving_circuits:
            detour_sum = 0.0
            for leg in c:
                gc = static_graph.get_city_distance(leg["origin_city"], leg["destination_city"])
                est_act = max(gc, (leg["duration_minutes"] / 60.0) * 700.0)
                detour_sum += (est_act / gc) if gc > 0 else 1.0
            detours.append(detour_sum)

        min_d, max_d = min(durations), max(durations)
        min_p, max_p = min(prices), max(prices)
        min_g, max_g = min(detours), max(detours)

        w_t = config.cost_weights.weight_time
        w_p = config.cost_weights.weight_price
        w_g = config.cost_weights.weight_geo_deviation

        for k, circuit_offers in enumerate(surviving_circuits):
            tot_dur = durations[k]
            tot_price = prices[k]
            tot_detour = detours[k]

            norm_t = (tot_dur - min_d) / (max_d - min_d) if (max_d - min_d) > 1e-6 else 0.0
            norm_p = (tot_price - min_p) / (max_p - min_p) if (max_p - min_p) > 1e-6 else 0.0
            norm_g = (tot_detour - min_g) / (max_g - min_g) if (max_g - min_g) > 1e-6 else 0.0

            total_score = w_t * norm_t + w_p * norm_p + w_g * norm_g

            route_str = " -> ".join([leg["origin_city"] for leg in circuit_offers] + [circuit_offers[-1]["destination_city"]])
            total_trip_days = sum(leg["stay_days"] for leg in circuit_offers)

            scored_itineraries.append({
                "route_string": route_str,
                "circuit_cities": [leg["origin_city"] for leg in circuit_offers] + [circuit_offers[-1]["destination_city"]],
                "legs": circuit_offers,
                "total_price_usd": round(tot_price, 2),
                "total_duration_minutes": tot_dur,
                "total_duration_formatted": f"{tot_dur // 60}h {tot_dur % 60}m",
                "total_trip_days": total_trip_days,
                "total_score": round(total_score, 4),
            })

        # Sort by total score ascending
        scored_itineraries.sort(key=lambda x: x["total_score"])

    return {
        "total_permutations": total_permutations,
        "pruned_by_static_graph": pruned_by_static_graph,
        "schedules_evaluated": schedules_evaluated,
        "valid_itineraries_count": len(scored_itineraries),
        "itineraries": scored_itineraries,
    }
