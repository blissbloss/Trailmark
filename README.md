# AI-Based Smart Trip Planner for Community Tourism System

A Flask web app that collects a traveler's preferences, scores destinations with
a rule-based recommendation engine, builds a full day-wise itinerary with
genetic-algorithm route optimization, and supports solo and group trip planning.

## 1. Quick start

```bash
cd smart_trip_planner
pip install -r requirements.txt
python app.py
```

Open **http://localhost:5000**. The database is created and seeded automatically
on first run.

**Demo admin account:** `admin@trailmark.demo` / `admin123`

## 2. Feature map

| Feature | Implementation |
|---|---|
| User Authentication | `app.py` — register/login/logout, Werkzeug password hashing |
| Browse-before-login | `/plan` is public (view + submit); login only required at "Build itinerary" |
| Non-editable inputs | Budget, duration, travelers are `<select>` dropdowns — no free typing |
| AI Recommendation Engine | `recommender.py` — rule-based weighted scoring |
| Itinerary Generator | `recommender.py` `build_itinerary()` |
| **Genetic Algorithm route optimization** | `routeopt.py` — real GA (tournament selection, order crossover, swap mutation, elitism) minimizing Haversine-distance travel between each day's stops |
| Delay Notification / auto-reschedule | `notifications.py` — a detected delay shifts the rest of Day 1 forward instead of cancelling |
| **Group Trip "Poll & Merge"** | `/group/*` routes — create a room, invite via link, each member submits budget/interests, creator merges and generates one itinerary for the group |
| **Export to PDF / KML** | `exporter.py`, `/itinerary/<id>/export/<pdf\|kml>` — print-ready PDF and a KML file for Google My Maps import |
| Feedback & Rating | `/feedback/<destination_id>`, live rating recalculation |
| Administrator Dashboard | `/admin/*` |

## 3. The Genetic Algorithm route optimizer

Reordering a day's stops into the shortest route is the classic Traveling
Salesperson Problem. `routeopt.py` runs a real genetic algorithm:

- **Chromosome:** a candidate visiting order (permutation of stop indices)
- **Fitness:** total trip distance via the Haversine formula (real great-circle
  distance between lat/lon points)
- **Selection:** tournament selection (best of 3 random candidates)
- **Crossover:** order crossover (OX) — preserves relative stop order
- **Mutation:** swap mutation
- **Elitism:** the best 2 routes carry over unchanged each generation

This searches the same kind of space the Google Maps Matrix API + a route
optimizer would, but needs no paid API key or network dependency — swapping
in real drive-time data later only means replacing `haversine_km()`.

## 4. Group Trip flow

1. A logged-in user creates a room (`/group/create`) with a trip name, duration and pace.
2. They share the room's invite link.
3. Each friend logs in/signs up, joins, and submits their own budget + interests.
4. The creator clicks "Generate group itinerary" — `score_destinations_for_group()`
   merges everyone's interests (weighted by how many members picked each tag) and
   sums their budgets, then ranks destinations for the whole group.
5. The creator confirms a destination; the resulting trip is linked to the room
   (`trips.room_id`), and **every room member** — not just the creator — can view
   the shared itinerary.

## 5. Export formats

- **PDF** (`reportlab`): a clean, print-ready day-by-day table with times, items and costs.
- **KML**: an XML placemark file for every stop with coordinates, grouped into
  folders by day. Opens directly via Google My Maps → Import, or Google Earth.
  No Google API key needed — KML is an open, documented format.

## 6. Entity-relationship summary

```
users(1)──<trips>──(1)destinations          users(1)──<feedback>──(1)destinations
   │            │
   │            ├──<itinerary_items (with lat/lon)
   │            └──<notifications
   │
   ├──<trip_rooms (creator)
   │        │
   │        ├──<room_members>──(1)users
   │        ├──<room_preferences>──(1)users
   │        └──<trips (room_id)
```

Full column definitions: `db.py` (SQLite, used by the running app) and
`schema_mysql.sql` (MySQL DDL for production).

## 7. Project structure

```
smart_trip_planner/
├── app.py                 # Flask routes
├── db.py                  # SQLite schema + connection helper
├── schema_mysql.sql        # Production MySQL DDL
├── recommender.py         # Recommendation engine + itinerary generator
├── routeopt.py             # Genetic Algorithm route optimizer
├── exporter.py              # PDF / KML export
├── notifications.py       # Delay/weather/safety notification simulator
├── seed.py                 # Demo data with coordinates
├── requirements.txt
├── templates/               # Jinja2 templates
├── static/css/style.css     # Design system
└── instance/trip_planner.db  # created automatically on first run
```
