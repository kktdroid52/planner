"""
app.py
Personal AI Planner - Flask backend.

Run with:  python app.py
Then open: http://localhost:5000
"""
from datetime import datetime, date, timedelta
from flask import Flask, jsonify, request, render_template

import storage
import scheduler

app = Flask(__name__)

# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def goals_db():
    return storage.load("goals")


def tasks_db():
    return storage.load("tasks")


def commitments_db():
    return storage.load("commitments")


def habits_db():
    return storage.load("habits")


def state_db():
    return storage.load("state")


def goal_progress(goal):
    target = float(goal.get("target_hours") or 0)
    logged = float(goal.get("hours_logged") or 0)
    pct = 0 if target <= 0 else min(round(logged / target * 100, 1), 100)
    return pct


def recompute_goal_status(goal):
    if goal_progress(goal) >= 100 and goal.get("target_hours"):
        goal["status"] = "completed"
    elif goal.get("status") == "completed" and goal_progress(goal) < 100:
        goal["status"] = "active"


def bump_streak():
    """Call whenever a task is completed. Increases the daily streak the
    first time a task is completed on a given day."""
    state = state_db()
    today = storage.today_str()
    last = state.get("last_active_date")
    if last == today:
        pass  # already counted today
    else:
        yesterday = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
        if last == yesterday:
            state["current_streak"] = state.get("current_streak", 0) + 1
        else:
            state["current_streak"] = 1
        state["best_streak"] = max(state.get("best_streak", 0), state["current_streak"])
        state["last_active_date"] = today
    storage.save("state", state)
    return state


def check_streak_decay():
    """If the user missed yesterday AND today hasn't happened yet, the
    streak shown should reflect reality (not silently keep an old streak
    alive). We don't reset on load eagerly -- only when a new day with no
    activity has fully passed -- so today's pending tasks don't kill the
    streak prematurely. This is called read-only for display."""
    state = state_db()
    last = state.get("last_active_date")
    if not last:
        return state
    last_date = datetime.strptime(last, "%Y-%m-%d").date()
    gap = (date.today() - last_date).days
    if gap >= 2:
        state["current_streak"] = 0
        storage.save("state", state)
    return state


# ----------------------------------------------------------------------
# Page
# ----------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


# ----------------------------------------------------------------------
# Goals
# ----------------------------------------------------------------------

@app.route("/api/goals", methods=["GET"])
def get_goals():
    goals = goals_db()
    for g in goals:
        g["progress_pct"] = goal_progress(g)
        g["hours_remaining"] = scheduler.hours_remaining(g)
        g["days_until_deadline"] = scheduler.days_until(g.get("deadline"))
        g["priority_score"] = scheduler.goal_priority_score(g)
        g["weekly_hours_needed"] = scheduler.weekly_hours_needed(g)
    return jsonify(goals)


@app.route("/api/goals", methods=["POST"])
def create_goal():
    data = request.get_json(force=True)
    goals = goals_db()
    goal = {
        "id": storage.new_id(),
        "title": data.get("title", "Untitled goal"),
        "description": data.get("description", ""),
        "deadline": data.get("deadline"),  # YYYY-MM-DD or None
        "importance": int(data.get("importance", 3)),
        "target_hours": float(data.get("target_hours", 0) or 0),
        "hours_logged": 0,
        "status": "active",
        "created_at": storage.now_iso(),
    }
    goals.append(goal)
    storage.save("goals", goals)
    return jsonify(goal), 201


@app.route("/api/goals/<goal_id>", methods=["PUT"])
def update_goal(goal_id):
    data = request.get_json(force=True)
    goals = goals_db()
    for g in goals:
        if g["id"] == goal_id:
            for field in ["title", "description", "deadline", "importance", "target_hours", "status"]:
                if field in data:
                    g[field] = data[field]
            recompute_goal_status(g)
            storage.save("goals", goals)
            return jsonify(g)
    return jsonify({"error": "not found"}), 404


@app.route("/api/goals/<goal_id>", methods=["DELETE"])
def delete_goal(goal_id):
    goals = goals_db()
    goals = [g for g in goals if g["id"] != goal_id]
    storage.save("goals", goals)
    # also detach tasks
    tasks = tasks_db()
    for t in tasks:
        if t.get("goal_id") == goal_id:
            t["goal_id"] = None
    storage.save("tasks", tasks)
    return jsonify({"ok": True})


@app.route("/api/goals/<goal_id>/log_hours", methods=["POST"])
def log_hours(goal_id):
    data = request.get_json(force=True)
    hours = float(data.get("hours", 0))
    goals = goals_db()
    for g in goals:
        if g["id"] == goal_id:
            g["hours_logged"] = float(g.get("hours_logged", 0)) + hours
            recompute_goal_status(g)
            storage.save("goals", goals)
            return jsonify(g)
    return jsonify({"error": "not found"}), 404


# ----------------------------------------------------------------------
# Tasks
# ----------------------------------------------------------------------

@app.route("/api/tasks", methods=["GET"])
def get_tasks():
    tasks = tasks_db()
    scheduler.auto_adjust_overdue(tasks)
    storage.save("tasks", tasks)
    date_filter = request.args.get("date")
    if date_filter:
        tasks = [t for t in tasks if t.get("date") == date_filter]
    return jsonify(tasks)


@app.route("/api/tasks", methods=["POST"])
def create_task():
    data = request.get_json(force=True)
    tasks = tasks_db()
    task = {
        "id": storage.new_id(),
        "title": data.get("title", "Untitled task"),
        "goal_id": data.get("goal_id"),
        "date": data.get("date", storage.today_str()),
        "start_time": data.get("start_time"),
        "end_time": data.get("end_time"),
        "duration_minutes": int(data.get("duration_minutes", 30)),
        "completed": False,
        "completed_at": None,
        "created_at": storage.now_iso(),
        "priority_boost": 0,
    }
    tasks.append(task)
    storage.save("tasks", tasks)
    return jsonify(task), 201


@app.route("/api/tasks/<task_id>", methods=["PUT"])
def update_task(task_id):
    data = request.get_json(force=True)
    tasks = tasks_db()
    for t in tasks:
        if t["id"] == task_id:
            for field in ["title", "date", "start_time", "end_time", "duration_minutes", "goal_id"]:
                if field in data:
                    t[field] = data[field]
            storage.save("tasks", tasks)
            return jsonify(t)
    return jsonify({"error": "not found"}), 404


@app.route("/api/tasks/<task_id>", methods=["DELETE"])
def delete_task(task_id):
    tasks = tasks_db()
    tasks = [t for t in tasks if t["id"] != task_id]
    storage.save("tasks", tasks)
    return jsonify({"ok": True})


@app.route("/api/tasks/<task_id>/complete", methods=["POST"])
def complete_task(task_id):
    tasks = tasks_db()
    target = None
    for t in tasks:
        if t["id"] == task_id:
            t["completed"] = not t.get("completed")
            t["completed_at"] = storage.now_iso() if t["completed"] else None
            target = t
    storage.save("tasks", tasks)

    if target and target["completed"]:
        bump_streak()
        if target.get("goal_id"):
            goals = goals_db()
            for g in goals:
                if g["id"] == target["goal_id"]:
                    g["hours_logged"] = float(g.get("hours_logged", 0)) + (target.get("duration_minutes", 30) / 60)
                    recompute_goal_status(g)
            storage.save("goals", goals)
    return jsonify(target)


# ----------------------------------------------------------------------
# Commitments (school / tuition / fixed schedule) & Calendar
# ----------------------------------------------------------------------

@app.route("/api/commitments", methods=["GET"])
def get_commitments():
    return jsonify(commitments_db())


@app.route("/api/commitments", methods=["POST"])
def create_commitment():
    data = request.get_json(force=True)
    commitments = commitments_db()
    c = {
        "id": storage.new_id(),
        "title": data.get("title", "Commitment"),
        "type": data.get("type", "fixed"),  # school / tuition / fixed
        "recurring": bool(data.get("recurring", True)),
        "days_of_week": data.get("days_of_week", []),  # [0..6], Mon=0
        "date": data.get("date"),  # used if not recurring
        "start_time": data["start_time"],
        "end_time": data["end_time"],
    }
    commitments.append(c)
    storage.save("commitments", commitments)
    return jsonify(c), 201


@app.route("/api/commitments/<cid>", methods=["DELETE"])
def delete_commitment(cid):
    commitments = commitments_db()
    commitments = [c for c in commitments if c["id"] != cid]
    storage.save("commitments", commitments)
    return jsonify({"ok": True})


@app.route("/api/calendar/day")
def calendar_day():
    date_str = request.args.get("date", storage.today_str())
    target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    commitments = commitments_db()
    occupied = scheduler.occupied_blocks_for_date(commitments, target_date)
    free = scheduler.free_slots_for_date(commitments, target_date)
    tasks = [t for t in tasks_db() if t.get("date") == date_str]
    return jsonify({
        "date": date_str,
        "occupied": [{"start": scheduler._to_hhmm(s), "end": scheduler._to_hhmm(e), "title": title} for s, e, title in occupied],
        "free_slots": free,
        "tasks": tasks,
    })


@app.route("/api/calendar/week")
def calendar_week():
    start_str = request.args.get("start", storage.today_str())
    start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
    commitments = commitments_db()
    tasks = tasks_db()
    days = []
    for i in range(7):
        d = start_date + timedelta(days=i)
        d_str = d.strftime("%Y-%m-%d")
        occupied = scheduler.occupied_blocks_for_date(commitments, d)
        days.append({
            "date": d_str,
            "weekday": d.strftime("%A"),
            "occupied": [{"start": scheduler._to_hhmm(s), "end": scheduler._to_hhmm(e), "title": title} for s, e, title in occupied],
            "free_slots": scheduler.free_slots_for_date(commitments, d),
            "tasks": [t for t in tasks if t.get("date") == d_str],
        })
    return jsonify(days)


# ----------------------------------------------------------------------
# Habits
# ----------------------------------------------------------------------

@app.route("/api/habits", methods=["GET"])
def get_habits():
    habits = habits_db()
    for h in habits:
        h["streak"], h["best_streak"] = _habit_streaks(h)
    return jsonify(habits)


def _habit_streaks(habit):
    log = habit.get("log", {})
    cur = 0
    d = date.today()
    while log.get(d.strftime("%Y-%m-%d")):
        cur += 1
        d -= timedelta(days=1)
    best = max(habit.get("best_streak", 0), cur)
    return cur, best


@app.route("/api/habits", methods=["POST"])
def create_habit():
    data = request.get_json(force=True)
    habits = habits_db()
    h = {
        "id": storage.new_id(),
        "name": data.get("name", "New habit"),
        "icon": data.get("icon", "✅"),
        "log": {},
        "best_streak": 0,
        "created_at": storage.now_iso(),
    }
    habits.append(h)
    storage.save("habits", habits)
    return jsonify(h), 201


@app.route("/api/habits/<hid>/toggle", methods=["POST"])
def toggle_habit(hid):
    data = request.get_json(silent=True) or {}
    day = data.get("date", storage.today_str())
    habits = habits_db()
    target = None
    for h in habits:
        if h["id"] == hid:
            log = h.setdefault("log", {})
            log[day] = not log.get(day, False)
            cur, best = _habit_streaks(h)
            h["best_streak"] = max(h.get("best_streak", 0), best)
            target = h
    storage.save("habits", habits)
    return jsonify(target)


@app.route("/api/habits/<hid>", methods=["DELETE"])
def delete_habit(hid):
    habits = habits_db()
    habits = [h for h in habits if h["id"] != hid]
    storage.save("habits", habits)
    return jsonify({"ok": True})


# ----------------------------------------------------------------------
# Dashboard / Progress / Productivity
# ----------------------------------------------------------------------

@app.route("/api/dashboard")
def dashboard():
    goals = goals_db()
    tasks = tasks_db()
    scheduler.auto_adjust_overdue(tasks)
    storage.save("tasks", tasks)
    state = check_streak_decay()

    for g in goals:
        g["progress_pct"] = goal_progress(g)

    active_goals = [g for g in goals if g.get("status") != "completed"]
    completed_goals = [g for g in goals if g.get("status") == "completed"]
    total_hours_logged = round(sum(float(g.get("hours_logged", 0)) for g in goals), 2)

    today = storage.today_str()
    today_tasks = [t for t in tasks if t.get("date") == today]
    today_done = [t for t in today_tasks if t.get("completed")]

    reminders = build_reminders(goals, tasks)
    recommendation = scheduler.recommend_next(goals, tasks)

    return jsonify({
        "active_goals": len(active_goals),
        "completed_goals": len(completed_goals),
        "total_hours_logged": total_hours_logged,
        "today_tasks_total": len(today_tasks),
        "today_tasks_done": len(today_done),
        "current_streak": state.get("current_streak", 0),
        "best_streak": state.get("best_streak", 0),
        "reminders": reminders,
        "recommendation": recommendation,
        "goals": sorted(active_goals, key=lambda g: scheduler.goal_priority_score(g), reverse=True),
    })


def build_reminders(goals, tasks):
    reminders = []
    today = date.today()

    for g in goals:
        if g.get("status") == "completed":
            continue
        d_left = scheduler.days_until(g.get("deadline"))
        if g.get("deadline"):
            if d_left < 0:
                reminders.append({"type": "overdue_goal", "text": f"Goal \"{g['title']}\" is overdue by {-d_left} day(s).", "severity": "high"})
            elif d_left <= 3:
                reminders.append({"type": "deadline", "text": f"Goal \"{g['title']}\" is due in {d_left} day(s).", "severity": "medium"})

    for t in tasks:
        if t.get("completed"):
            continue
        if not t.get("date"):
            continue
        t_date = datetime.strptime(t["date"], "%Y-%m-%d").date()
        delta = (t_date - today).days
        if delta < 0 or t.get("overdue_from"):
            reminders.append({"type": "overdue_task", "text": f"Task \"{t['title']}\" is overdue.", "severity": "high"})
        elif delta == 0:
            reminders.append({"type": "today", "text": f"\"{t['title']}\" is scheduled for today.", "severity": "low"})
        elif delta == 1:
            reminders.append({"type": "upcoming", "text": f"\"{t['title']}\" is due tomorrow.", "severity": "low"})
    return reminders


@app.route("/api/reminders")
def reminders_endpoint():
    return jsonify(build_reminders(goals_db(), tasks_db()))


# ----------------------------------------------------------------------
# Smart Planner / AI features
# ----------------------------------------------------------------------

@app.route("/api/smart/recommend")
def smart_recommend():
    return jsonify(scheduler.recommend_next(goals_db(), tasks_db()) or {})


@app.route("/api/smart/priorities")
def smart_priorities():
    goals = goals_db()
    ranked = scheduler.rank_goals(goals)
    return jsonify([
        {**g, "progress_pct": goal_progress(g), "priority_score": score,
         "weekly_hours_needed": scheduler.weekly_hours_needed(g)}
        for g, score in ranked
    ])


@app.route("/api/smart/schedule")
def smart_schedule():
    date_str = request.args.get("date", storage.today_str())
    target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    suggestions = scheduler.suggest_schedule_for_date(goals_db(), commitments_db(), target_date)
    return jsonify(suggestions)


@app.route("/api/smart/auto_adjust", methods=["POST"])
def smart_auto_adjust():
    tasks = tasks_db()
    adjusted = scheduler.auto_adjust_overdue(tasks)
    storage.save("tasks", tasks)
    return jsonify({"adjusted_count": len(adjusted), "tasks": adjusted})


# ----------------------------------------------------------------------
# Reports
# ----------------------------------------------------------------------

@app.route("/api/reports/weekly")
def weekly_report():
    end = date.today()
    start = end - timedelta(days=6)
    tasks = tasks_db()
    goals = {g["id"]: g for g in goals_db()}

    in_range = [t for t in tasks if t.get("date") and start.strftime("%Y-%m-%d") <= t["date"] <= end.strftime("%Y-%m-%d")]
    completed = [t for t in in_range if t.get("completed")]
    completion_rate = round(len(completed) / len(in_range) * 100, 1) if in_range else 0
    hours_worked = round(sum(t.get("duration_minutes", 0) for t in completed) / 60, 2)

    hours_by_goal = {}
    for t in completed:
        if t.get("goal_id"):
            hours_by_goal[t["goal_id"]] = hours_by_goal.get(t["goal_id"], 0) + t.get("duration_minutes", 0) / 60

    top_goal = None
    if hours_by_goal:
        top_id = max(hours_by_goal, key=hours_by_goal.get)
        g = goals.get(top_id)
        if g:
            top_goal = {"title": g["title"], "hours": round(hours_by_goal[top_id], 2)}

    daily_breakdown = []
    for i in range(7):
        d = start + timedelta(days=i)
        d_str = d.strftime("%Y-%m-%d")
        day_tasks = [t for t in in_range if t["date"] == d_str]
        day_done = [t for t in day_tasks if t.get("completed")]
        daily_breakdown.append({
            "date": d_str,
            "weekday": d.strftime("%a"),
            "total": len(day_tasks),
            "completed": len(day_done),
        })

    return jsonify({
        "range": {"start": start.strftime("%Y-%m-%d"), "end": end.strftime("%Y-%m-%d")},
        "tasks_scheduled": len(in_range),
        "tasks_completed": len(completed),
        "completion_rate": completion_rate,
        "hours_worked": hours_worked,
        "top_goal": top_goal,
        "daily_breakdown": daily_breakdown,
    })


if __name__ == "__main__":
    app.run(debug=True, port=5000)
