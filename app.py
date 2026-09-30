"""
app.py
------
AI-Based Smart Trip Planner for Community Tourism System
Application (Business Logic) Layer -- Flask routes.

Modules implemented (mapping to synopsis Section 4 + requested enhancements):
  - User Authentication          -> /register /login /logout
  - Trip Preference Collection   -> /plan (public to view/submit; login only required to confirm)
  - AI Recommendation Engine     -> recommender.py
  - Itinerary Generator          -> recommender.py, /itinerary/<trip_id>
  - Route Optimization (GA)      -> routeopt.py, applied inside build_itinerary()
  - Delay Notification Module    -> notifications.py
  - Community Tourism Integration-> destination.community_tourism flags surfaced throughout
  - Feedback & Rating System     -> /feedback/<destination_id>
  - Administrator Dashboard      -> /admin/*
  - Group Trip Poll & Merge      -> /group/*
  - Export to PDF / KML          -> /itinerary/<trip_id>/export/<fmt>
"""

import secrets
import string
from collections import Counter
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, g, Response

from werkzeug.security import generate_password_hash, check_password_hash

from db import init_db, get_db, now
from recommender import score_destinations, score_destinations_for_group, build_itinerary, INTEREST_TAGS
from notifications import generate_notifications, get_notifications
from exporter import generate_kml, generate_pdf
import seed as seed_module

app = Flask(__name__)
app.secret_key = "dev-secret-key-change-in-production"


with app.app_context():
    init_db()
    seed_module.run()


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not g.user:
            session.clear()
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login", next=request.path))
        return f(*args, **kwargs)
    return wrapper


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not g.user or g.user["role"] != "admin":
            flash("Admin access required.", "danger")
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return wrapper


@app.before_request
def load_user():
    g.user = None
    if "user_id" in session:
        conn = get_db()
        g.user = conn.execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()
        conn.close()


# ---------------------------------------------------------------------------
# Public pages
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    conn = get_db()
    destinations = conn.execute(
        "SELECT * FROM destinations ORDER BY rating DESC LIMIT 6"
    ).fetchall()
    conn.close()
    return render_template("index.html", destinations=destinations)


@app.route("/destinations")
def destinations_list():
    conn = get_db()
    category = request.args.get("category")
    if category:
        rows = conn.execute(
            "SELECT * FROM destinations WHERE category=? ORDER BY rating DESC", (category,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM destinations ORDER BY rating DESC").fetchall()
    conn.close()
    return render_template("destinations.html", destinations=rows, categories=INTEREST_TAGS, active=category)


@app.route("/destination/<int:dest_id>")
def destination_detail(dest_id):
    conn = get_db()
    dest = conn.execute("SELECT * FROM destinations WHERE id=?", (dest_id,)).fetchone()
    hotels = conn.execute("SELECT * FROM hotels WHERE destination_id=?", (dest_id,)).fetchall()
    restaurants = conn.execute("SELECT * FROM restaurants WHERE destination_id=?", (dest_id,)).fetchall()
    activities = conn.execute("SELECT * FROM activities WHERE destination_id=?", (dest_id,)).fetchall()
    reviews = conn.execute(
        """SELECT feedback.*, users.name as user_name FROM feedback
           JOIN users ON users.id = feedback.user_id
           WHERE destination_id=? ORDER BY feedback.id DESC""", (dest_id,)
    ).fetchall()
    conn.close()
    if not dest:
        flash("Destination not found.", "danger")
        return redirect(url_for("destinations_list"))
    return render_template("destination_detail.html", dest=dest, hotels=hotels,
                            restaurants=restaurants, activities=activities, reviews=reviews)


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        if not name or not email or len(password) < 6:
            flash("Please provide a valid name, email and a password of at least 6 characters.", "danger")
            return render_template("register.html")

        conn = get_db()
        existing = conn.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
        if existing:
            flash("An account with that email already exists.", "danger")
            conn.close()
            return render_template("register.html")

        conn.execute(
            "INSERT INTO users (name, email, password_hash, role, created_at) VALUES (?,?,?,?,?)",
            (name, email, generate_password_hash(password), "traveler", now())
        )
        conn.commit()
        conn.close()
        flash("Account created! Please log in.", "success")
        next_url = request.args.get("next")
        return redirect(url_for("login", next=next_url) if next_url else url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        conn.close()

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["role"] = user["role"]
            session["name"] = user["name"]
            flash(f"Welcome back, {user['name']}!", "success")
            next_url = request.args.get("next")
            return redirect(next_url or (url_for("admin_dashboard") if user["role"] == "admin" else url_for("index")))
        flash("Invalid email or password.", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


# ---------------------------------------------------------------------------
# Trip planning (preference collection -> AI recommendation -> itinerary)
# Publicly viewable/submittable; login is only required at the confirm step.
# ---------------------------------------------------------------------------
@app.route("/plan", methods=["GET", "POST"])
def plan_trip():
    if request.method == "POST":
        try:
            budget = float(request.form["budget"])
            duration_days = int(request.form["duration_days"])
            travelers_count = int(request.form["travelers_count"])
        except (ValueError, KeyError):
            flash("Please choose a budget, duration and traveler count.", "danger")
            return render_template("plan_trip.html", interest_tags=INTEREST_TAGS)

        interests = request.form.getlist("interests")
        pace = request.form.get("pace", "balanced")
        community_pref = request.form.get("community_pref") == "on"
        force_delay_demo = request.form.get("force_delay_demo") == "on"

        if budget <= 0 or duration_days <= 0 or travelers_count <= 0:
            flash("Budget, duration and traveler count must be greater than zero.", "danger")
            return render_template("plan_trip.html", interest_tags=INTEREST_TAGS)

        ranked = score_destinations(interests, budget, duration_days, community_pref)

        session["pending_trip"] = {
            "budget": budget, "duration_days": duration_days,
            "travelers_count": travelers_count, "interests": interests,
            "pace": pace, "community_pref": community_pref,
            "force_delay_demo": force_delay_demo,
        }
        return render_template("recommendations.html", ranked=ranked[:5])

    return render_template("plan_trip.html", interest_tags=INTEREST_TAGS)


@app.route("/plan/confirm/<int:dest_id>", methods=["GET", "POST"])
def confirm_trip(dest_id):
    prefs = session.get("pending_trip")
    if not prefs:
        flash("Your trip preferences expired. Please plan again.", "warning")
        return redirect(url_for("plan_trip"))

    if not g.user:
        session.clear()
        flash("Please log in or sign up to save and view your itinerary.", "warning")
        return redirect(url_for("login", next=url_for("confirm_trip", dest_id=dest_id)))

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO trips (user_id, destination_id, duration_days, travelers_count,
           budget, interests, pace, status, created_at) VALUES (?,?,?,?,?,?,?,?,?)""",
        (session["user_id"], dest_id, prefs["duration_days"], prefs["travelers_count"],
         prefs["budget"], ",".join(prefs["interests"]), prefs["pace"], "planned", now())
    )
    trip_id = cur.lastrowid
    conn.commit()
    conn.close()

    if prefs.get("force_delay_demo"):
        session["force_delay_trip_id"] = trip_id

    session.pop("pending_trip", None)
    return redirect(url_for("view_itinerary", trip_id=trip_id))


def _build_and_store_itinerary(conn, trip, dest):
    """Shared by solo and group trip confirmation: builds itinerary items +
    notifications for a freshly-created trip row if it doesn't have items yet."""
    items = conn.execute(
        "SELECT * FROM itinerary_items WHERE trip_id=? ORDER BY day_number, start_time", (trip["id"],)
    ).fetchall()
    if items:
        return items

    force_delay = session.pop("force_delay_trip_id", None) == trip["id"]
    delay_minutes = generate_notifications(trip, force_delay=force_delay)

    interests = trip["interests"].split(",") if trip["interests"] else []
    itinerary, total_cost, warnings = build_itinerary(
        trip["destination_id"], trip["duration_days"], trip["travelers_count"],
        trip["budget"], interests, trip["pace"],
        community_pref=bool(dest["community_tourism"]),
        delay_minutes=delay_minutes
    )
    for item in itinerary:
        conn.execute(
            """INSERT INTO itinerary_items (trip_id, day_number, item_type, title, start_time, cost, notes, latitude, longitude)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (trip["id"], item["day"], item["type"], item["title"], item["time"], item["cost"], item["notes"],
             item.get("lat"), item.get("lon"))
        )
    conn.commit()
    for w in warnings:
        flash(w, "warning")
    return conn.execute(
        "SELECT * FROM itinerary_items WHERE trip_id=? ORDER BY day_number, start_time", (trip["id"],)
    ).fetchall()


@app.route("/itinerary/<int:trip_id>")
@login_required
def view_itinerary(trip_id):
    conn = get_db()
    trip = conn.execute("SELECT * FROM trips WHERE id=?", (trip_id,)).fetchone()
    if not trip:
        conn.close()
        flash("Trip not found.", "danger")
        return redirect(url_for("my_trips"))

    is_owner = trip["user_id"] == session["user_id"]
    is_admin = session.get("role") == "admin"
    is_room_member = False
    if trip["room_id"]:
        member_row = conn.execute(
            "SELECT 1 FROM room_members WHERE room_id=? AND user_id=?",
            (trip["room_id"], session["user_id"])
        ).fetchone()
        is_room_member = member_row is not None

    if not (is_owner or is_admin or is_room_member):
        conn.close()
        flash("Trip not found.", "danger")
        return redirect(url_for("my_trips"))

    dest = conn.execute("SELECT * FROM destinations WHERE id=?", (trip["destination_id"],)).fetchone()
    items = _build_and_store_itinerary(conn, trip, dest)

    days = {}
    total_cost = 0
    for it in items:
        days.setdefault(it["day_number"], []).append(it)
        total_cost += it["cost"]

    alerts = get_notifications(trip_id)
    conn.close()

    return render_template("itinerary.html", trip=trip, dest=dest, days=days,
                            total_cost=total_cost, alerts=alerts)


@app.route("/itinerary/<int:trip_id>/export/<fmt>")
@login_required
def export_itinerary(trip_id, fmt):
    conn = get_db()
    trip = conn.execute("SELECT * FROM trips WHERE id=?", (trip_id,)).fetchone()
    if not trip:
        conn.close()
        flash("Trip not found.", "danger")
        return redirect(url_for("my_trips"))

    is_owner = trip["user_id"] == session["user_id"]
    is_admin = session.get("role") == "admin"
    is_room_member = False
    if trip["room_id"]:
        member_row = conn.execute(
            "SELECT 1 FROM room_members WHERE room_id=? AND user_id=?",
            (trip["room_id"], session["user_id"])
        ).fetchone()
        is_room_member = member_row is not None
    if not (is_owner or is_admin or is_room_member):
        conn.close()
        flash("Trip not found.", "danger")
        return redirect(url_for("my_trips"))

    dest = conn.execute("SELECT * FROM destinations WHERE id=?", (trip["destination_id"],)).fetchone()
    items = conn.execute(
        "SELECT * FROM itinerary_items WHERE trip_id=? ORDER BY day_number, start_time", (trip_id,)
    ).fetchall()
    conn.close()

    days = {}
    total_cost = 0
    for it in items:
        days.setdefault(it["day_number"], []).append(it)
        total_cost += it["cost"]

    safe_name = "".join(c if c.isalnum() else "_" for c in dest["name"])

    if fmt == "pdf":
        pdf_bytes = generate_pdf(trip, dest, days, total_cost)
        return Response(pdf_bytes, mimetype="application/pdf", headers={
            "Content-Disposition": f"attachment; filename={safe_name}_itinerary.pdf"
        })
    elif fmt == "kml":
        kml_text = generate_kml(trip, dest, days)
        return Response(kml_text, mimetype="application/vnd.google-earth.kml+xml", headers={
            "Content-Disposition": f"attachment; filename={safe_name}_itinerary.kml"
        })
    else:
        flash("Unknown export format.", "danger")
        return redirect(url_for("view_itinerary", trip_id=trip_id))


@app.route("/my-trips")
@login_required
def my_trips():
    conn = get_db()
    trips = conn.execute(
        """SELECT trips.*, destinations.name as dest_name, destinations.image_seed,
                  trip_rooms.name as room_name
           FROM trips JOIN destinations ON destinations.id = trips.destination_id
           LEFT JOIN trip_rooms ON trip_rooms.id = trips.room_id
           WHERE trips.user_id=? ORDER BY trips.id DESC""", (session["user_id"],)
    ).fetchall()
    conn.close()
    return render_template("my_trips.html", trips=trips)


# ---------------------------------------------------------------------------
# Group Trip "Poll & Merge"
# ---------------------------------------------------------------------------
def _generate_room_code():
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(6))


@app.route("/group/create", methods=["GET", "POST"])
@login_required
def group_create():
    if request.method == "POST":
        try:
            duration_days = int(request.form["duration_days"])
        except (ValueError, KeyError):
            flash("Please choose a trip duration.", "danger")
            return render_template("group_create.html")

        name = request.form.get("name", "").strip() or "Untitled Group Trip"
        pace = request.form.get("pace", "balanced")
        community_pref = request.form.get("community_pref") == "on"

        code = _generate_room_code()
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO trip_rooms (code, name, creator_user_id, status, created_at) VALUES (?,?,?,?,?)",
            (code, name, session["user_id"], "collecting", now())
        )
        room_id = cur.lastrowid
        cur.execute(
            "INSERT INTO room_members (room_id, user_id, joined_at) VALUES (?,?,?)",
            (room_id, session["user_id"], now())
        )
        conn.commit()
        conn.close()

        session[f"room_settings_{code}"] = {"duration_days": duration_days, "pace": pace, "community_pref": community_pref}
        flash("Group trip created! Share the invite link with friends.", "success")
        return redirect(url_for("group_room", code=code))

    return render_template("group_create.html")


@app.route("/group/<code>")
@login_required
def group_room(code):
    conn = get_db()
    room = conn.execute("SELECT * FROM trip_rooms WHERE code=?", (code,)).fetchone()
    if not room:
        conn.close()
        flash("Group trip not found.", "danger")
        return redirect(url_for("group_create"))

    is_member = conn.execute(
        "SELECT 1 FROM room_members WHERE room_id=? AND user_id=?", (room["id"], session["user_id"])
    ).fetchone() is not None

    members = conn.execute(
        """SELECT users.id, users.name,
                  (SELECT 1 FROM room_preferences rp WHERE rp.room_id=? AND rp.user_id=users.id) as has_submitted
           FROM room_members JOIN users ON users.id = room_members.user_id
           WHERE room_members.room_id=? ORDER BY room_members.joined_at""",
        (room["id"], room["id"])
    ).fetchall()

    my_prefs = None
    if is_member:
        my_prefs = conn.execute(
            "SELECT * FROM room_preferences WHERE room_id=? AND user_id=?", (room["id"], session["user_id"])
        ).fetchone()

    linked_trip = conn.execute(
        "SELECT * FROM trips WHERE room_id=? ORDER BY id DESC LIMIT 1", (room["id"],)
    ).fetchone()
    conn.close()

    is_creator = room["creator_user_id"] == session["user_id"]
    submitted_count = sum(1 for m in members if m["has_submitted"])

    return render_template("group_room.html", room=room, members=members, is_member=is_member,
                            my_prefs=my_prefs, is_creator=is_creator, submitted_count=submitted_count,
                            interest_tags=INTEREST_TAGS, linked_trip=linked_trip)


@app.route("/group/<code>/join", methods=["POST"])
@login_required
def group_join(code):
    conn = get_db()
    room = conn.execute("SELECT * FROM trip_rooms WHERE code=?", (code,)).fetchone()
    if not room:
        conn.close()
        flash("Group trip not found.", "danger")
        return redirect(url_for("group_create"))
    existing = conn.execute(
        "SELECT 1 FROM room_members WHERE room_id=? AND user_id=?", (room["id"], session["user_id"])
    ).fetchone()
    if not existing:
        conn.execute(
            "INSERT INTO room_members (room_id, user_id, joined_at) VALUES (?,?,?)",
            (room["id"], session["user_id"], now())
        )
        conn.commit()
        flash(f"You joined \"{room['name']}\"!", "success")
    conn.close()
    return redirect(url_for("group_room", code=code))


@app.route("/group/<code>/preferences", methods=["POST"])
@login_required
def group_submit_preferences(code):
    conn = get_db()
    room = conn.execute("SELECT * FROM trip_rooms WHERE code=?", (code,)).fetchone()
    if not room:
        conn.close()
        flash("Group trip not found.", "danger")
        return redirect(url_for("group_create"))

    is_member = conn.execute(
        "SELECT 1 FROM room_members WHERE room_id=? AND user_id=?", (room["id"], session["user_id"])
    ).fetchone()
    if not is_member:
        conn.close()
        flash("Join this group trip first.", "warning")
        return redirect(url_for("group_room", code=code))

    try:
        budget = float(request.form["budget"])
    except (ValueError, KeyError):
        flash("Please choose your budget.", "danger")
        return redirect(url_for("group_room", code=code))
    interests = request.form.getlist("interests")

    existing = conn.execute(
        "SELECT id FROM room_preferences WHERE room_id=? AND user_id=?", (room["id"], session["user_id"])
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE room_preferences SET budget=?, interests=?, submitted_at=? WHERE id=?",
            (budget, ",".join(interests), now(), existing["id"])
        )
    else:
        conn.execute(
            "INSERT INTO room_preferences (room_id, user_id, budget, interests, submitted_at) VALUES (?,?,?,?,?)",
            (room["id"], session["user_id"], budget, ",".join(interests), now())
        )
    conn.commit()
    conn.close()
    flash("Your preferences are in!", "success")
    return redirect(url_for("group_room", code=code))


@app.route("/group/<code>/generate", methods=["POST"])
@login_required
def group_generate(code):
    conn = get_db()
    room = conn.execute("SELECT * FROM trip_rooms WHERE code=?", (code,)).fetchone()
    if not room or room["creator_user_id"] != session["user_id"]:
        conn.close()
        flash("Only the trip creator can generate the group itinerary.", "danger")
        return redirect(url_for("group_room", code=code))

    prefs_rows = conn.execute("SELECT * FROM room_preferences WHERE room_id=?", (room["id"],)).fetchall()
    conn.close()

    if not prefs_rows:
        flash("No one has submitted their preferences yet.", "warning")
        return redirect(url_for("group_room", code=code))

    settings = session.get(f"room_settings_{code}", {"duration_days": 3, "pace": "balanced", "community_pref": False})

    total_budget = sum(r["budget"] for r in prefs_rows)
    interest_counter = Counter()
    for r in prefs_rows:
        for tag in (r["interests"] or "").split(","):
            if tag:
                interest_counter[tag] += 1

    ranked = score_destinations_for_group(
        dict(interest_counter), total_budget, settings["duration_days"], len(prefs_rows)
    )

    session["pending_group_trip"] = {
        "room_code": code,
        "budget": total_budget,
        "duration_days": settings["duration_days"],
        "travelers_count": len(prefs_rows),
        "interests": [tag for tag, _ in interest_counter.most_common()],
        "pace": settings["pace"],
        "community_pref": settings["community_pref"],
    }
    return render_template("group_recommendations.html", ranked=ranked[:5], room=room, member_count=len(prefs_rows))


@app.route("/group/<code>/confirm/<int:dest_id>", methods=["POST"])
@login_required
def group_confirm(code, dest_id):
    prefs = session.get("pending_group_trip")
    if not prefs or prefs.get("room_code") != code:
        flash("Group trip preferences expired. Please generate again.", "warning")
        return redirect(url_for("group_room", code=code))

    conn = get_db()
    room = conn.execute("SELECT * FROM trip_rooms WHERE code=?", (code,)).fetchone()
    if not room or room["creator_user_id"] != session["user_id"]:
        conn.close()
        flash("Only the trip creator can confirm the group itinerary.", "danger")
        return redirect(url_for("group_room", code=code))

    cur = conn.cursor()
    cur.execute(
        """INSERT INTO trips (user_id, destination_id, duration_days, travelers_count,
           budget, interests, pace, status, room_id, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (session["user_id"], dest_id, prefs["duration_days"], prefs["travelers_count"],
         prefs["budget"], ",".join(prefs["interests"]), prefs["pace"], "planned", room["id"], now())
    )
    trip_id = cur.lastrowid
    conn.execute("UPDATE trip_rooms SET status='confirmed' WHERE id=?", (room["id"],))
    conn.commit()
    conn.close()

    session.pop("pending_group_trip", None)
    return redirect(url_for("view_itinerary", trip_id=trip_id))


# ---------------------------------------------------------------------------
# Feedback & rating
# ---------------------------------------------------------------------------
@app.route("/feedback/<int:dest_id>", methods=["POST"])
@login_required
def submit_feedback(dest_id):
    rating = int(request.form["rating"])
    comment = request.form.get("comment", "").strip()
    conn = get_db()
    conn.execute(
        "INSERT INTO feedback (user_id, destination_id, rating, comment, created_at) VALUES (?,?,?,?,?)",
        (session["user_id"], dest_id, rating, comment, now())
    )
    avg = conn.execute(
        "SELECT AVG(rating) a FROM feedback WHERE destination_id=?", (dest_id,)
    ).fetchone()["a"]
    conn.execute("UPDATE destinations SET rating=? WHERE id=?", (round(avg, 1), dest_id))
    conn.commit()
    conn.close()
    flash("Thanks for your feedback!", "success")
    return redirect(url_for("destination_detail", dest_id=dest_id))


# ---------------------------------------------------------------------------
# Admin dashboard
# ---------------------------------------------------------------------------
@app.route("/admin")
@login_required
@admin_required
def admin_dashboard():
    conn = get_db()
    stats = {
        "users": conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"],
        "destinations": conn.execute("SELECT COUNT(*) c FROM destinations").fetchone()["c"],
        "trips": conn.execute("SELECT COUNT(*) c FROM trips").fetchone()["c"],
        "feedback": conn.execute("SELECT COUNT(*) c FROM feedback").fetchone()["c"],
    }
    recent_trips = conn.execute(
        """SELECT trips.*, users.name as user_name, destinations.name as dest_name
           FROM trips JOIN users ON users.id=trips.user_id
           JOIN destinations ON destinations.id=trips.destination_id
           ORDER BY trips.id DESC LIMIT 10"""
    ).fetchall()
    top_destinations = conn.execute(
        "SELECT * FROM destinations ORDER BY rating DESC LIMIT 5"
    ).fetchall()
    conn.close()
    return render_template("admin_dashboard.html", stats=stats,
                            recent_trips=recent_trips, top_destinations=top_destinations)


@app.route("/admin/destinations")
@login_required
@admin_required
def admin_destinations():
    conn = get_db()
    rows = conn.execute("SELECT * FROM destinations ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("admin_destinations.html", destinations=rows, categories=INTEREST_TAGS)


@app.route("/admin/destinations/add", methods=["POST"])
@login_required
@admin_required
def admin_add_destination():
    conn = get_db()
    conn.execute(
        """INSERT INTO destinations (name, state, description, category, community_tourism,
           avg_daily_cost, rating, image_seed, image_url) VALUES (?,?,?,?,?,?,?,?,?)""",
        (request.form["name"], request.form.get("state", ""), request.form.get("description", ""),
         request.form["category"], 1 if request.form.get("community_tourism") == "on" else 0,
         float(request.form["avg_daily_cost"]), float(request.form.get("rating", 4.0)),
         request.form["name"].lower().replace(" ", "-"),
         request.form.get("image_url") or None)
    )
    conn.commit()
    conn.close()
    flash("Destination added.", "success")
    return redirect(url_for("admin_destinations"))


@app.route("/admin/destinations/delete/<int:dest_id>", methods=["POST"])
@login_required
@admin_required
def admin_delete_destination(dest_id):
    conn = get_db()
    conn.execute("DELETE FROM destinations WHERE id=?", (dest_id,))
    conn.commit()
    conn.close()
    flash("Destination removed.", "info")
    return redirect(url_for("admin_destinations"))


@app.route("/admin/users")
@login_required
@admin_required
def admin_users():
    conn = get_db()
    rows = conn.execute("SELECT * FROM users ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("admin_users.html", users=rows)


@app.route("/admin/feedback")
@login_required
@admin_required
def admin_feedback():
    conn = get_db()
    rows = conn.execute(
        """SELECT feedback.*, users.name as user_name, destinations.name as dest_name
           FROM feedback JOIN users ON users.id=feedback.user_id
           JOIN destinations ON destinations.id=feedback.destination_id
           ORDER BY feedback.id DESC"""
    ).fetchall()
    conn.close()
    return render_template("admin_feedback.html", feedback=rows)


if __name__ == "__main__":
    app.run(debug=True, use_reloader=False, host="0.0.0.0", port=5000)
