"""
notifications.py
-----------------
Delay Notification Module. Simulates weather/transport/safety alerts
deterministically (seeded by trip id) so demos are repeatable. A detected
delay is returned as minutes so recommender.build_itinerary() can actually
reschedule the day -- the trip continues, it doesn't cancel.
"""

import random
from db import get_db, now

SAFETY_TIPS = [
    "Keep a digital and physical copy of your ID and hotel booking.",
    "Share your daily itinerary with a family member or friend.",
    "Carry a basic first-aid kit and any personal medication.",
    "Check local emergency numbers for your destination before you travel.",
    "Avoid isolated areas after dark; prefer well-reviewed transport after sunset.",
]

WEATHER_CONDITIONS = [
    ("Clear skies expected", "info"),
    ("Light rain possible in the afternoon — carry an umbrella", "weather"),
    ("High heat advisory — stay hydrated and plan outdoor activities early", "weather"),
    ("Cool and pleasant conditions expected", "info"),
]


def generate_notifications(trip_row, force_delay=False):
    rnd = random.Random(trip_row["id"])
    conn = get_db()

    messages = []
    delay_minutes = None

    weather_msg, weather_type = rnd.choice(WEATHER_CONDITIONS)
    messages.append((f"Weather update: {weather_msg}.", weather_type))

    if force_delay or rnd.random() < 0.4:
        delay_minutes = rnd.choice([15, 30, 45, 60])
        messages.append(
            (f"Your outbound transport is delayed by approximately {delay_minutes} minutes. "
             f"Day 1's schedule has been automatically shifted forward — nothing is cancelled.", "delay")
        )

    messages.append((f"Safety tip: {rnd.choice(SAFETY_TIPS)}", "safety"))
    messages.append(("Hotel check-in is typically after 12:00 PM; check-out by 11:00 AM.", "info"))

    for msg, ntype in messages:
        conn.execute(
            "INSERT INTO notifications (trip_id, message, ntype, created_at) VALUES (?,?,?,?)",
            (trip_row["id"], msg, ntype, now())
        )
    conn.commit()
    conn.close()
    return delay_minutes


def get_notifications(trip_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM notifications WHERE trip_id=? ORDER BY id DESC", (trip_id,)
    ).fetchall()
    conn.close()
    return rows
