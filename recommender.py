"""
recommender.py
---------------
The "AI-Based Recommendation Engine", "Itinerary Generator", and route
optimization modules described in the synopsis and requested enhancements.

This uses rule-based / weighted scoring for destination and item selection
(a deliberate, documented simplification -- see Section 10 of the synopsis),
and a real Genetic Algorithm (routeopt.py) to sequence each day's stops into
an efficient geographic route.
"""

from db import get_db
from routeopt import optimize_route

INTEREST_TAGS = [
    "Heritage", "Nature", "Adventure", "Beach", "Spiritual",
    "Wildlife", "Food", "Community", "Art & Craft", "Trekking",
]


def score_destinations(interests, budget, duration_days, community_pref=False):
    conn = get_db()
    rows = conn.execute("SELECT * FROM destinations").fetchall()
    conn.close()

    interests = set(interests or [])
    scored = []
    daily_budget_target = budget / max(duration_days, 1)

    for r in rows:
        d = dict(r)
        score = 0.0

        if d["category"] in interests:
            score += 5.0

        if community_pref and d["community_tourism"]:
            score += 3.0
        elif d["community_tourism"]:
            score += 1.0

        if d["avg_daily_cost"] <= daily_budget_target:
            score += 3.0
        elif d["avg_daily_cost"] <= daily_budget_target * 1.3:
            score += 1.0
        else:
            score -= 2.0

        score += (d["rating"] - 3.0)

        d["score"] = round(score, 2)
        scored.append(d)

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored


def score_destinations_for_group(interest_counts, total_budget, duration_days, member_count):
    """
    Group-trip variant of score_destinations: instead of a single traveler's
    interest list, takes a {interest_tag: number_of_members_who_picked_it}
    count and weights destinations by how many group members would be happy,
    not just whether one person likes it.
    """
    conn = get_db()
    rows = conn.execute("SELECT * FROM destinations").fetchall()
    conn.close()

    scored = []
    daily_budget_target = total_budget / max(duration_days, 1)
    max_votes = max(interest_counts.values()) if interest_counts else 1

    for r in rows:
        d = dict(r)
        score = 0.0

        votes = interest_counts.get(d["category"], 0)
        if votes:
            # Scale 0-5 points by how popular this category is with the group
            score += 5.0 * (votes / max(max_votes, 1))

        if d["community_tourism"]:
            score += 1.5

        if d["avg_daily_cost"] <= daily_budget_target:
            score += 3.0
        elif d["avg_daily_cost"] <= daily_budget_target * 1.3:
            score += 1.0
        else:
            score -= 2.0

        score += (d["rating"] - 3.0)

        d["score"] = round(score, 2)
        d["group_votes"] = votes
        scored.append(d)

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored


def _best_within_budget(rows, budget_left, key="price_per_night"):
    if not rows:
        return None
    affordable = [r for r in rows if r[key] <= budget_left]
    pool = affordable if affordable else rows
    return max(pool, key=lambda r: r["rating"]) if affordable else min(pool, key=lambda r: r[key])


def recommend_hotel(destination_id, nightly_budget, prefer_homestay=False):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM hotels WHERE destination_id=?", (destination_id,)
    ).fetchall()
    conn.close()
    rows = [dict(r) for r in rows]
    if prefer_homestay:
        homestays = [r for r in rows if r["is_homestay"]]
        if homestays:
            rows = homestays
    return _best_within_budget(rows, nightly_budget, "price_per_night")


def recommend_restaurant(destination_id, meal_budget, exclude_ids=None):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM restaurants WHERE destination_id=?", (destination_id,)
    ).fetchall()
    conn.close()
    rows = [dict(r) for r in rows]
    exclude_ids = exclude_ids or set()
    rows = [r for r in rows if r["id"] not in exclude_ids] or rows
    return _best_within_budget(rows, meal_budget, "price_per_meal")


def recommend_activities(destination_id, interests, count):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM activities WHERE destination_id=?", (destination_id,)
    ).fetchall()
    conn.close()
    rows = [dict(r) for r in rows]
    interests = set(interests or [])

    def act_score(a):
        s = 0
        if a["category"] in interests:
            s += 4
        if a["community_run"]:
            s += 2
        return s

    rows.sort(key=act_score, reverse=True)
    return rows[:count]


def recommend_transport(destination_id, budget):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM transport_options WHERE destination_id=?", (destination_id,)
    ).fetchall()
    conn.close()
    rows = [dict(r) for r in rows]
    if not rows:
        return None
    affordable = [r for r in rows if r["cost"] <= budget]
    pool = affordable if affordable else rows
    return min(pool, key=lambda r: r["duration_hours"])


PACE_ACTIVITIES_PER_DAY = {"relaxed": 2, "balanced": 3, "packed": 4}


def shift_time(time_str, minutes):
    if not time_str or ":" not in time_str:
        return time_str
    try:
        h, m = (int(p) for p in time_str.split(":"))
    except ValueError:
        return time_str
    total = (h * 60 + m + minutes) % (24 * 60)
    return f"{total // 60:02d}:{total % 60:02d}"


def build_itinerary(destination_id, duration_days, travelers_count, budget,
                     interests, pace="balanced", community_pref=False, delay_minutes=None):
    """
    Builds a full day-wise itinerary. Each day's activities are additionally
    passed through the Genetic Algorithm route optimizer (routeopt.py) so
    they're visited in an efficient geographic order starting from that
    day's hotel, rather than in an arbitrary order.

    Returns (itinerary: list[dict], total_cost: float, warnings: list[str])
    """
    conn = get_db()
    dest_row = conn.execute("SELECT latitude, longitude FROM destinations WHERE id=?", (destination_id,)).fetchone()
    conn.close()
    dest_coords = (dest_row["latitude"], dest_row["longitude"]) if dest_row else (None, None)

    itinerary = []
    warnings = []
    total_cost = 0.0
    activities_per_day = PACE_ACTIVITIES_PER_DAY.get(pace, 3)

    per_day_budget = budget / max(duration_days, 1)
    nightly_hotel_budget = per_day_budget * 0.35 * travelers_count
    meal_budget = per_day_budget * 0.15 * travelers_count
    activity_budget_share = per_day_budget * 0.35 * travelers_count

    transport = recommend_transport(destination_id, budget * 0.15)
    if transport:
        cost = transport["cost"] * travelers_count
        total_cost += cost
        itinerary.append({
            "day": 1, "type": "transport", "time": "06:00",
            "title": f"Depart via {transport['mode']}",
            "cost": round(cost, 2),
            "notes": f"Approx. {transport['duration_hours']}h journey to destination."
        })
    else:
        warnings.append("No transport options found in the database for this destination.")

    hotel = recommend_hotel(destination_id, nightly_hotel_budget, prefer_homestay=community_pref)
    if not hotel:
        warnings.append("No hotel/homestay data found for this destination.")

    hotel_coords = (hotel.get("latitude"), hotel.get("longitude")) if hotel else dest_coords

    used_activity_ids = set()

    for day in range(1, duration_days + 1):
        if hotel:
            night_cost = hotel["price_per_night"]
            total_cost += night_cost
            itinerary.append({
                "day": day, "type": "hotel", "time": "12:00" if day == 1 else "check-in",
                "title": f"Stay: {hotel['name']}{' (Community Homestay)' if hotel['is_homestay'] else ''}",
                "cost": round(night_cost, 2),
                "notes": f"Rating {hotel['rating']}/5 · ₹{hotel['price_per_night']:.0f}/night",
                "lat": hotel.get("latitude"), "lon": hotel.get("longitude"),
            })

        todays_count = activities_per_day
        if day == duration_days and duration_days > 1:
            todays_count = max(1, activities_per_day - 1)

        candidates = recommend_activities(destination_id, interests, todays_count + len(used_activity_ids) + 2)
        candidates = [a for a in candidates if a["id"] not in used_activity_ids]
        todays_activities = candidates[:todays_count]

        # --- Genetic Algorithm route optimization for today's stop order ---
        route_note = None
        if len(todays_activities) >= 2 and hotel_coords[0] is not None:
            ordered, total_km, legs = optimize_route(todays_activities, hotel_coords, seed=destination_id * 100 + day)
            if total_km > 0:
                todays_activities = ordered
                route_note = f"Route optimized by genetic algorithm: {total_km} km total across {len(legs)} stops."

        start_hour = 9
        for i, act in enumerate(todays_activities):
            if start_hour >= 20:
                break
            used_activity_ids.add(act["id"])
            cost = act["cost"] * travelers_count
            total_cost += cost
            notes = act["description"] or f"Category: {act['category']}"
            if route_note and i == 0:
                notes = f"{notes} {route_note}"
            itinerary.append({
                "day": day, "type": "activity",
                "time": f"{start_hour:02d}:00",
                "title": act["name"] + (" (Community-run)" if act["community_run"] else ""),
                "cost": round(cost, 2),
                "notes": notes,
                "lat": act.get("latitude"), "lon": act.get("longitude"),
            })
            start_hour += int(act["duration_hours"]) + 1

        lunch = recommend_restaurant(destination_id, meal_budget / 2)
        dinner = recommend_restaurant(destination_id, meal_budget / 2,
                                       exclude_ids={lunch["id"]} if lunch else None)
        for meal_slot, meal, time in (("Lunch", lunch, "13:00"), ("Dinner", dinner, "20:00")):
            if meal:
                cost = meal["price_per_meal"] * travelers_count
                total_cost += cost
                itinerary.append({
                    "day": day, "type": "restaurant", "time": time,
                    "title": f"{meal_slot} at {meal['name']}" + (" (Local-owned)" if meal["local_owned"] else ""),
                    "cost": round(cost, 2),
                    "notes": f"{meal['cuisine']} · Rating {meal['rating']}/5",
                    "lat": meal.get("latitude"), "lon": meal.get("longitude"),
                })

    return_transport = recommend_transport(destination_id, budget * 0.15)
    if return_transport:
        cost = return_transport["cost"] * travelers_count
        total_cost += cost
        itinerary.append({
            "day": duration_days, "type": "transport", "time": "18:00",
            "title": f"Return via {return_transport['mode']}",
            "cost": round(cost, 2),
            "notes": "Check for delays 2 hours before departure."
        })

    if total_cost > budget:
        warnings.append(
            f"Estimated cost ₹{total_cost:.0f} exceeds your budget of ₹{budget:.0f} "
            f"by ₹{total_cost - budget:.0f}. Consider a homestay, fewer activities, or a longer duration."
        )

    if delay_minutes:
        for item in itinerary:
            if item["day"] == 1 and item["type"] != "transport":
                old_time = item["time"]
                new_time = shift_time(old_time, delay_minutes)
                if new_time != old_time:
                    item["time"] = new_time
                    tag = f"Rescheduled from {old_time} (+{delay_minutes} min transport delay)."
                    item["notes"] = f"{item['notes']} {tag}".strip() if item.get("notes") else tag
        warnings.append(
            f"Transport delay of {delay_minutes} minutes detected — Day 1's schedule was "
            f"shifted forward automatically. Your trip continues as planned, just later."
        )

    itinerary.sort(key=lambda x: (x["day"], x["time"]))
    return itinerary, round(total_cost, 2), warnings
