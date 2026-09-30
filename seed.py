"""
seed.py
-------
Populates the database with demo tourism data, including approximate
real-world coordinates for each hotel/restaurant/activity (scattered
realistically around each destination's actual location) so the Genetic
Algorithm route optimizer and the KML map export have real geography to
work with. Coordinates are generated deterministically (seeded by name)
rather than hand-typed for every single entity.
"""

import random
from db import init_db, get_db, now
from werkzeug.security import generate_password_hash

# Picsum Photos: a free image service built for reliable hotlinking placeholder
# photos. Each destination gets a consistent (seeded) photo. These are
# attractive travel-style stock photos, not photos of the specific named
# place -- swap image_url for a real photo URL or /static/img/... path anytime.
def _picsum(seed):
    return f"https://picsum.photos/seed/{seed}/600/400"

IMAGE_URLS = {
    "Spiti Valley": _picsum("spiti-valley"),
    "Hampi": _picsum("hampi-ruins"),
    "Wayanad": _picsum("wayanad-hills"),
    "Majuli Island": _picsum("majuli-island"),
    "Goa Beaches": _picsum("goa-beach"),
    "Rishikesh": _picsum("rishikesh-ganges"),
    "Kaziranga": _picsum("kaziranga-park"),
    "Pushkar": _picsum("pushkar-lake"),
    "Khonoma Village": _picsum("khonoma-village"),
    "Coorg": _picsum("coorg-coffee"),
}

# Approximate real-world center coordinates for each destination
CENTER_COORDS = {
    "Spiti Valley": (32.2465, 78.0104),
    "Hampi": (15.3350, 76.4600),
    "Wayanad": (11.6854, 76.1320),
    "Majuli Island": (26.9520, 94.1630),
    "Goa Beaches": (15.5430, 73.7550),
    "Rishikesh": (30.0869, 78.2676),
    "Kaziranga": (26.5775, 93.1714),
    "Pushkar": (26.4899, 74.5511),
    "Khonoma Village": (25.6294, 94.0439),
    "Coorg": (12.4244, 75.7382),
}


def _scatter(dest_name, entity_name):
    """Deterministic small offset (~2-10km) from a destination's center,
    so every hotel/restaurant/activity within a destination has a distinct,
    repeatable, realistic-looking coordinate."""
    base_lat, base_lon = CENTER_COORDS[dest_name]
    rnd = random.Random(f"{dest_name}:{entity_name}")
    d_lat = rnd.uniform(-0.08, 0.08)
    d_lon = rnd.uniform(-0.08, 0.08)
    return round(base_lat + d_lat, 5), round(base_lon + d_lon, 5)


DESTINATIONS = [
    ("Spiti Valley", "Himachal Pradesh",
     "A high-altitude cold desert valley known for Buddhist monasteries, remote villages and stark Himalayan landscapes.",
     "Adventure", 1, 2200, 4.7, "spiti"),
    ("Hampi", "Karnataka",
     "UNESCO World Heritage ruins of the Vijayanagara Empire, boulder landscapes, and river-side villages.",
     "Heritage", 1, 1400, 4.6, "hampi"),
    ("Wayanad", "Kerala",
     "Misty hills, spice plantations, tribal heritage villages and wildlife sanctuaries in the Western Ghats.",
     "Nature", 1, 1800, 4.5, "wayanad"),
    ("Majuli Island", "Assam",
     "The world's largest river island, home to Assamese neo-Vaishnavite monasteries and mask-making villages.",
     "Community", 1, 1200, 4.4, "majuli"),
    ("Goa Beaches", "Goa",
     "Coastal beach towns with Portuguese heritage, water sports, and nightlife.",
     "Beach", 0, 2500, 4.3, "goa"),
    ("Rishikesh", "Uttarakhand",
     "Yoga capital on the Ganges, known for ashrams, river rafting and spiritual retreats.",
     "Spiritual", 0, 1600, 4.5, "rishikesh"),
    ("Kaziranga", "Assam",
     "National park famous for the one-horned rhinoceros and community-run jungle safaris.",
     "Wildlife", 1, 2000, 4.6, "kaziranga"),
    ("Pushkar", "Rajasthan",
     "Desert town with a sacred lake, camel fairs, and artisan bazaars.",
     "Spiritual", 0, 1300, 4.2, "pushkar"),
    ("Khonoma Village", "Nagaland",
     "India's first 'green village', a Naga heritage site with terraced farming and community homestays.",
     "Community", 1, 1000, 4.8, "khonoma"),
    ("Coorg", "Karnataka",
     "Coffee plantation hills with trekking trails, waterfalls and homestay-based tourism.",
     "Nature", 1, 1900, 4.5, "coorg"),
]

HOTELS = {
    "Spiti Valley": [("Spiti Ecosphere Homestay", 1200, 4.8, 1), ("Hotel Spiti Serai", 3200, 4.3, 0)],
    "Hampi": [("Hampi Heritage Homestay", 900, 4.6, 1), ("Hampi Boulders Resort", 4500, 4.5, 0)],
    "Wayanad": [("Tribal Trails Homestay", 1100, 4.7, 1), ("Wayanad Wild Resort", 3800, 4.2, 0)],
    "Majuli Island": [("Majuli Cultural Homestay", 700, 4.6, 1), ("La Maison de Ananda", 1800, 4.3, 0)],
    "Goa Beaches": [("Beachside Budget Inn", 1500, 3.9, 0), ("Goa Grand Resort", 6000, 4.4, 0)],
    "Rishikesh": [("Ganga View Ashram Stay", 800, 4.4, 0), ("Rishikesh Riverside Resort", 3500, 4.3, 0)],
    "Kaziranga": [("Kaziranga Community Lodge", 1000, 4.7, 1), ("Wild Grass Resort", 3200, 4.4, 0)],
    "Pushkar": [("Pushkar Desert Camp", 1200, 4.1, 0), ("Lake View Haveli", 2800, 4.3, 0)],
    "Khonoma Village": [("Khonoma Homestay Collective", 600, 4.9, 1)],
    "Coorg": [("Coorg Plantation Homestay", 1300, 4.7, 1), ("Coorg Hillside Resort", 4200, 4.4, 0)],
}

RESTAURANTS = {
    "Spiti Valley": [("Spiti Kitchen", "Himachali/Tibetan", 300, 4.5, 1), ("Sol Cafe", "Multi-cuisine", 450, 4.2, 0)],
    "Hampi": [("Mango Tree Restaurant", "South Indian", 250, 4.4, 1), ("Laughing Buddha", "Multi-cuisine", 350, 4.3, 0)],
    "Wayanad": [("Tribal Kitchen", "Kerala", 280, 4.5, 1), ("Wayanad Spice Garden Cafe", "Multi-cuisine", 400, 4.1, 0)],
    "Majuli Island": [("Majuli Village Kitchen", "Assamese", 200, 4.6, 1)],
    "Goa Beaches": [("Beach Shack Grill", "Goan Seafood", 500, 4.3, 1), ("Curlies", "Multi-cuisine", 600, 4.0, 0)],
    "Rishikesh": [("Ganga Beach Cafe", "Vegetarian/Continental", 300, 4.4, 0), ("Ayurvedic Cafe", "Healthy", 350, 4.2, 1)],
    "Kaziranga": [("Kaziranga Village Kitchen", "Assamese", 280, 4.5, 1)],
    "Pushkar": [("Sunset Cafe", "Rajasthani", 300, 4.2, 0), ("Pushkar Rooftop Cafe", "Multi-cuisine", 400, 4.1, 0)],
    "Khonoma Village": [("Khonoma Naga Kitchen", "Naga", 250, 4.8, 1)],
    "Coorg": [("Coorg Homestyle Kitchen", "Kodava", 320, 4.6, 1), ("Plantation Cafe", "Multi-cuisine", 400, 4.3, 0)],
}

ACTIVITIES = {
    "Spiti Valley": [
        ("Key Monastery Visit", "Spiritual", "Guided visit to one of the oldest Tibetan Buddhist monasteries.", 100, 3, 0),
        ("Village Homestay Trek", "Trekking", "Community-guided trek between remote Spiti villages.", 500, 6, 1),
        ("Chandratal Lake Excursion", "Nature", "Day trip to the high-altitude 'Moon Lake'.", 800, 8, 0),
    ],
    "Hampi": [
        ("Virupaksha Temple & Bazaar Walk", "Heritage", "Guided walking tour through temple ruins and old bazaar street.", 200, 3, 1),
        ("Boulder Sunset Trek", "Trekking", "Trek up Hampi's granite boulders for sunset views.", 150, 2, 0),
        ("Coracle Ride on Tungabhadra", "Adventure", "Traditional round-boat ride run by local boatmen.", 300, 1, 1),
    ],
    "Wayanad": [
        ("Edakkal Caves Trek", "Trekking", "Trek to prehistoric rock carvings inside Edakkal Caves.", 250, 3, 0),
        ("Tribal Heritage Village Tour", "Community", "Guided tour of a Kuruma/Paniya tribal settlement.", 400, 3, 1),
        ("Spice Plantation Walk", "Nature", "Walk through a working spice plantation with a local farmer guide.", 200, 2, 1),
    ],
    "Majuli Island": [
        ("Satra Monastery Visit", "Spiritual", "Visit a neo-Vaishnavite monastery and watch traditional mask-making.", 100, 3, 1),
        ("Pottery Village Workshop", "Art & Craft", "Hands-on pottery session with local Mishing artisans.", 300, 2, 1),
        ("Island Cycling Tour", "Nature", "Cycle through paddy fields and riverside villages.", 250, 3, 0),
    ],
    "Goa Beaches": [
        ("Water Sports Package", "Adventure", "Parasailing, jet-ski and banana boat combo.", 1500, 3, 0),
        ("Old Goa Heritage Walk", "Heritage", "Guided walk through Portuguese-era churches.", 300, 2, 0),
        ("Sunset Cruise", "Beach", "Evening cruise on the Mandovi river.", 700, 2, 0),
    ],
    "Rishikesh": [
        ("White Water Rafting", "Adventure", "Grade II-III rapids on the Ganges.", 900, 3, 0),
        ("Yoga & Meditation Session", "Spiritual", "Morning session at a riverside ashram.", 200, 2, 0),
        ("Beatles Ashram Walk", "Heritage", "Self-guided walk through the graffiti-covered ashram ruins.", 150, 2, 0),
    ],
    "Kaziranga": [
        ("Jeep Safari - Central Range", "Wildlife", "Community-guided jeep safari for rhino sightings.", 1500, 4, 1),
        ("Elephant-Back Safari", "Wildlife", "Early morning safari through grasslands.", 1800, 2, 0),
        ("Village Craft Visit", "Community", "Visit a local bamboo/cane craft workshop.", 200, 2, 1),
    ],
    "Pushkar": [
        ("Pushkar Lake Aarti", "Spiritual", "Evening prayer ceremony at the sacred lake ghats.", 0, 1, 0),
        ("Camel Safari", "Adventure", "Sunset camel ride into the Thar desert fringe.", 600, 3, 0),
        ("Artisan Bazaar Walk", "Art & Craft", "Guided shopping walk through silver and textile stalls.", 100, 2, 1),
    ],
    "Khonoma Village": [
        ("Terrace Farming Walk", "Community", "Guided walk through Angami terrace farms with a village elder.", 300, 3, 1),
        ("Khonoma Fort Trail", "Trekking", "Short heritage trek to the old village fort site.", 150, 2, 1),
        ("Naga Weaving Demonstration", "Art & Craft", "Hands-on traditional loom weaving session.", 250, 2, 1),
    ],
    "Coorg": [
        ("Coffee Plantation Tour", "Nature", "Guided walk through a working coffee estate.", 300, 2, 1),
        ("Abbey Falls Trek", "Trekking", "Short trek to a scenic waterfall.", 100, 2, 0),
        ("Kodava Cooking Class", "Food", "Hands-on cooking class with a local Kodava family.", 500, 3, 1),
    ],
}

TRANSPORT = {
    "Spiti Valley": [("Bus", 900, 12), ("Cab", 4500, 10)],
    "Hampi": [("Train", 600, 8), ("Bus", 400, 9)],
    "Wayanad": [("Bus", 350, 6), ("Cab", 2200, 5)],
    "Majuli Island": [("Train+Ferry", 500, 7), ("Bus+Ferry", 300, 8)],
    "Goa Beaches": [("Flight", 3500, 2), ("Train", 800, 12)],
    "Rishikesh": [("Bus", 450, 6), ("Train", 500, 7)],
    "Kaziranga": [("Bus", 600, 5), ("Cab", 3000, 4)],
    "Pushkar": [("Train", 400, 6), ("Bus", 300, 7)],
    "Khonoma Village": [("Cab", 1200, 2), ("Bus", 200, 3)],
    "Coorg": [("Bus", 400, 6), ("Cab", 2500, 5)],
}


def run():
    init_db()
    conn = get_db()
    cur = conn.cursor()

    existing = cur.execute("SELECT COUNT(*) c FROM destinations").fetchone()["c"]
    if existing > 0:
        print("Database already seeded. Skipping.")
        conn.close()
        return

    name_to_id = {}
    for name, state, desc, category, community, cost, rating, seed in DESTINATIONS:
        clat, clon = CENTER_COORDS[name]
        cur.execute(
            """INSERT INTO destinations
               (name, state, description, category, community_tourism, avg_daily_cost, rating, image_seed, image_url, latitude, longitude)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (name, state, desc, category, community, cost, rating, seed, IMAGE_URLS.get(name), clat, clon)
        )
        name_to_id[name] = cur.lastrowid

    for name, hotels in HOTELS.items():
        did = name_to_id[name]
        for hname, price, rating, homestay in hotels:
            lat, lon = _scatter(name, hname)
            cur.execute(
                "INSERT INTO hotels (destination_id, name, price_per_night, rating, is_homestay, latitude, longitude) VALUES (?,?,?,?,?,?,?)",
                (did, hname, price, rating, homestay, lat, lon)
            )

    for name, restaurants in RESTAURANTS.items():
        did = name_to_id[name]
        for rname, cuisine, price, rating, local in restaurants:
            lat, lon = _scatter(name, rname)
            cur.execute(
                "INSERT INTO restaurants (destination_id, name, cuisine, price_per_meal, rating, local_owned, latitude, longitude) VALUES (?,?,?,?,?,?,?,?)",
                (did, rname, cuisine, price, rating, local, lat, lon)
            )

    for name, activities in ACTIVITIES.items():
        did = name_to_id[name]
        for aname, category, desc, cost, hours, community in activities:
            lat, lon = _scatter(name, aname)
            cur.execute(
                """INSERT INTO activities
                   (destination_id, name, category, description, cost, duration_hours, community_run, latitude, longitude)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (did, aname, category, desc, cost, hours, community, lat, lon)
            )

    for name, options in TRANSPORT.items():
        did = name_to_id[name]
        for mode, cost, hours in options:
            cur.execute(
                "INSERT INTO transport_options (destination_id, mode, cost, duration_hours) VALUES (?,?,?,?)",
                (did, mode, cost, hours)
            )

    # Default admin account for the Administrator Dashboard
    cur.execute(
        "INSERT INTO users (name, email, password_hash, role, created_at) VALUES (?,?,?,?,?)",
        ("System Admin", "dimpiyaduvanshi8@gmail.com", generate_password_hash("dimpi123"), "admin", now())
    )

    conn.commit()
    conn.close()
    print(f"Seeded {len(DESTINATIONS)} destinations with hotels, restaurants, activities, transport options and coordinates, plus 1 admin account.")


if __name__ == "__main__":
    run()
