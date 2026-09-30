"""
routeopt.py
-----------
Genetic Algorithm route optimizer for daily itinerary sequencing.

WHY A GENETIC ALGORITHM, NOT THE GOOGLE MAPS MATRIX API
=========================================================
Reordering a day's stops into the shortest possible route is the classic
Traveling Salesperson Problem (TSP). The Google Maps Matrix API can supply
real-world drive-time distances between points, but it requires a paid
Google Cloud account and an API key -- a real deployment risk right before
a live demo, and unnecessary for proving the algorithm itself works.

Instead, this module computes real geographic (great-circle) distances
between stops using the Haversine formula, then runs an actual Genetic
Algorithm -- population of candidate routes, tournament selection, order
crossover, swap mutation, elitism across generations -- to search for the
shortest total route. The GA's job (searching a huge space of possible
orderings for a low-cost one) is identical whether the distance numbers
come from Haversine or a paid API; swapping in the Matrix API later only
means replacing `haversine_km()` with a real API call, everything else
(the GA itself) stays the same.

For the small number of stops in a single day (typically 2-5), an exact
brute-force search would also work, but the GA is what was asked for and
scales to larger stop counts without changes.
"""

import math
import random


def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance between two lat/lon points, in kilometers."""
    if None in (lat1, lon1, lat2, lon2):
        return 0.0
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _route_distance(order, points, start):
    """Total distance of visiting `points` (list of (lat,lon)) in `order`,
    starting from `start` (lat, lon)."""
    total = 0.0
    prev = start
    for idx in order:
        pt = points[idx]
        total += haversine_km(prev[0], prev[1], pt[0], pt[1])
        prev = pt
    return total


def _order_crossover(parent1, parent2, rng):
    """Order crossover (OX): preserves relative order, standard for TSP-style GAs."""
    size = len(parent1)
    if size < 2:
        return list(parent1)
    a, b = sorted(rng.sample(range(size), 2))
    child = [None] * size
    child[a:b] = parent1[a:b]
    fill = [g for g in parent2 if g not in child]
    pos = 0
    for i in range(size):
        if child[i] is None:
            child[i] = fill[pos]
            pos += 1
    return child


def _swap_mutate(route, rng, rate=0.2):
    route = list(route)
    if len(route) >= 2 and rng.random() < rate:
        i, j = rng.sample(range(len(route)), 2)
        route[i], route[j] = route[j], route[i]
    return route


def optimize_route(stops, start_point, generations=150, population_size=30, seed=None):
    """
    Reorders `stops` (a list of dicts, each with 'latitude' and 'longitude')
    into the geographically shortest visiting sequence using a Genetic Algorithm,
    starting from `start_point` (lat, lon) -- typically the day's hotel/base.

    Returns (ordered_stops, total_distance_km, per_leg_distances_km).
    Falls back to the original order (0 distance reported) if fewer than 2
    stops have usable coordinates, since there's nothing to optimize.
    """
    usable = [s for s in stops if s.get("latitude") is not None and s.get("longitude") is not None]
    if len(usable) < 2 or start_point[0] is None:
        return stops, 0.0, []

    rng = random.Random(seed)
    points = [(s["latitude"], s["longitude"]) for s in usable]
    n = len(points)

    # Initial population: random permutations of stop indices
    population = [rng.sample(range(n), n) for _ in range(population_size)]

    def fitness(route):
        return _route_distance(route, points, start_point)

    best = min(population, key=fitness)
    best_dist = fitness(best)

    for _ in range(generations):
        population.sort(key=fitness)
        # Elitism: keep the best 2 routes unchanged
        next_gen = population[:2]
        while len(next_gen) < population_size:
            # Tournament selection (pick best of 3 random candidates)
            p1 = min(rng.sample(population, min(3, len(population))), key=fitness)
            p2 = min(rng.sample(population, min(3, len(population))), key=fitness)
            child = _order_crossover(p1, p2, rng)
            child = _swap_mutate(child, rng)
            next_gen.append(child)
        population = next_gen
        candidate = min(population, key=fitness)
        candidate_dist = fitness(candidate)
        if candidate_dist < best_dist:
            best, best_dist = candidate, candidate_dist

    ordered_usable = [usable[i] for i in best]

    # Re-attach any stops that had no coordinates, appended at the end unordered
    unusable = [s for s in stops if s not in usable]
    ordered_stops = ordered_usable + unusable

    # Per-leg distances for display
    legs = []
    prev = start_point
    for s in ordered_usable:
        d = haversine_km(prev[0], prev[1], s["latitude"], s["longitude"])
        legs.append(round(d, 1))
        prev = (s["latitude"], s["longitude"])

    return ordered_stops, round(best_dist, 1), legs
