"""
scheduler.py
All the "smart planner" brains live here:
- working out occupied vs free time on any given day (school/tuition/fixed commitments)
- priority scoring of goals (deadline + importance + remaining work)
- recommending what to work on next
- building a suggested time-blocked schedule for a day
- auto-adjusting when tasks are missed (overdue -> rescheduled + bumped priority)
"""
from datetime import datetime, date

DAY_START = "06:00"
DAY_END = "23:00"


def _to_minutes(hhmm):
    h, m = map(int, hhmm.split(":"))
    return h * 60 + m


def _to_hhmm(mins):
    mins = mins % (24 * 60)
    return f"{mins // 60:02d}:{mins % 60:02d}"


def occupied_blocks_for_date(commitments, target_date):
    """Return sorted list of (start_min, end_min, title) for a given date,
    expanding recurring weekly commitments and one-off dated ones."""
    weekday = target_date.weekday()  # 0=Mon
    date_str = target_date.strftime("%Y-%m-%d")
    blocks = []
    for c in commitments:
        if c.get("recurring"):
            if weekday in c.get("days_of_week", []):
                blocks.append((_to_minutes(c["start_time"]), _to_minutes(c["end_time"]), c["title"]))
        else:
            if c.get("date") == date_str:
                blocks.append((_to_minutes(c["start_time"]), _to_minutes(c["end_time"]), c["title"]))
    blocks.sort(key=lambda b: b[0])
    return blocks


def free_slots_for_date(commitments, target_date, day_start=DAY_START, day_end=DAY_END):
    """Compute free time slots for a date, given occupied commitment blocks."""
    occupied = occupied_blocks_for_date(commitments, target_date)
    start = _to_minutes(day_start)
    end = _to_minutes(day_end)
    free = []
    cursor = start
    for (b_start, b_end, _title) in occupied:
        b_start = max(b_start, start)
        b_end = min(b_end, end)
        if b_start > cursor:
            free.append((cursor, b_start))
        cursor = max(cursor, b_end)
    if cursor < end:
        free.append((cursor, end))
    return [
        {"start": _to_hhmm(s), "end": _to_hhmm(e), "minutes": e - s}
        for s, e in free if e - s >= 15
    ]


def is_time_free(commitments, target_date, start_hhmm, end_hhmm):
    """True if the requested window does not overlap any occupied block."""
    s, e = _to_minutes(start_hhmm), _to_minutes(end_hhmm)
    for (b_start, b_end, _title) in occupied_blocks_for_date(commitments, target_date):
        if s < b_end and e > b_start:
            return False
    return True


def days_until(deadline_str):
    if not deadline_str:
        return 9999
    try:
        d = datetime.strptime(deadline_str, "%Y-%m-%d").date()
    except ValueError:
        return 9999
    return (d - date.today()).days


def hours_remaining(goal):
    target = float(goal.get("target_hours") or 0)
    logged = float(goal.get("hours_logged") or 0)
    return max(target - logged, 0)


def goal_priority_score(goal):
    """Higher = more urgent/important. Combines importance, deadline
    proximity, and remaining workload. Overdue goals are bumped hardest."""
    if goal.get("status") == "completed":
        return -1
    importance = float(goal.get("importance", 3))
    remaining = hours_remaining(goal)
    if remaining <= 0:
        return -1
    d_left = days_until(goal.get("deadline"))

    if d_left <= 0:
        urgency = 60
    else:
        urgency = min(50 / d_left, 50)

    workload_pressure = min(remaining / max(d_left, 1) * 5, 25) if d_left > 0 else 25
    score = (importance * 6) + urgency + workload_pressure
    return round(score, 1)


def rank_goals(goals):
    scored = [(g, goal_priority_score(g)) for g in goals if g.get("status") != "completed"]
    scored.sort(key=lambda gs: gs[1], reverse=True)
    return scored


def recommend_next(goals, tasks):
    """Recommend the single best thing to work on right now."""
    today = date.today().strftime("%Y-%m-%d")
    pending_today = [t for t in tasks if not t.get("completed") and t.get("date") == today]
    if pending_today:
        pending_today.sort(key=lambda t: t.get("priority_boost", 0), reverse=True)
        return {"type": "task", "item": pending_today[0]}

    ranked = rank_goals(goals)
    if ranked:
        top_goal, score = ranked[0]
        return {"type": "goal", "item": top_goal, "score": score}
    return None


def weekly_hours_needed(goal):
    """How many hours/week are needed to finish this goal on time."""
    remaining = hours_remaining(goal)
    d_left = days_until(goal.get("deadline"))
    if d_left <= 0:
        return remaining
    weeks_left = max(d_left / 7, 1 / 7)
    return round(remaining / weeks_left, 2)


def suggest_schedule_for_date(goals, commitments, target_date):
    """Allocate free slots on a date to the highest-priority active goals."""
    slots = free_slots_for_date(commitments, target_date)
    ranked = [g for g, score in rank_goals(goals) if score > 0]
    if not ranked:
        return []

    suggestions = []
    goal_idx = 0
    remaining_need = {g["id"]: min(hours_remaining(g) * 60, 180) for g in ranked}

    for slot in slots:
        slot_start = _to_minutes(slot["start"])
        slot_left = slot["minutes"]
        safety = 0
        while slot_left >= 25 and safety < len(ranked) * 4:
            safety += 1
            g = ranked[goal_idx % len(ranked)]
            need = remaining_need.get(g["id"], 0)
            if need <= 0:
                goal_idx += 1
                if all(v <= 0 for v in remaining_need.values()):
                    break
                continue
            block_len = int(min(slot_left, need, 90))
            if block_len < 25:
                break
            suggestions.append({
                "start": _to_hhmm(slot_start),
                "end": _to_hhmm(slot_start + block_len),
                "minutes": block_len,
                "goal_id": g["id"],
                "goal_title": g["title"],
            })
            slot_start += block_len
            slot_left -= block_len
            remaining_need[g["id"]] -= block_len
            goal_idx += 1
    return suggestions


def auto_adjust_overdue(tasks):
    """Find tasks whose date has passed and are not completed, mark overdue
    and bump them to today with a priority boost so they surface first."""
    today = date.today().strftime("%Y-%m-%d")
    adjusted = []
    for t in tasks:
        if t.get("completed"):
            continue
        if t.get("date") and t["date"] < today:
            t["overdue_from"] = t.get("overdue_from") or t["date"]
            t["date"] = today
            t["priority_boost"] = t.get("priority_boost", 0) + 10
            adjusted.append(t)
    return adjusted
