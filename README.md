# Pilot — Personal AI Planner

A full-stack Python web app (Flask backend + HTML/CSS/JS frontend, JSON storage)
implementing every module on your checklist:

- 🎯 Goal Management — create goals with deadline, importance, target hours
- 📋 Daily Task System — schedule, complete, delete tasks; can link to a goal
- 📅 Calendar & Scheduling — weekly calendar view of occupied + free time
- 🏫 School & Tuition Integration — recurring/one-off fixed commitments that
  block out time so goals/tasks only ever get suggested into free slots
- 📊 Progress Tracking — completion %, progress bars, total hours, dashboard
- 🔥 Productivity Tracking — daily streak counter + best streak record
- 🏆 Reports — weekly report: tasks completed, completion rate, hours worked,
  top goal of the week, daily breakdown
- 🔔 Reminders — deadline reminders, upcoming/today tasks, overdue alerts
- 🤖 Smart Planner / AI — priority scoring (deadline + importance + workload),
  hours-needed-per-week calculator, "what to work on next" recommendation,
  auto-suggested time-blocked schedule, auto-adjust when tasks are missed
- 🔥 Habit Tracker — daily check-off habits (Meditation, Walk, Photo Post, etc.)
  with streaks
- 💾 JSON Storage — everything auto-saves to /data/*.json, no database needed

## 1. Install

You need Python 3.9+ installed. Then, from this folder:

```
pip install -r requirements.txt
```

(This just installs Flask.)

## 2. Run

```
python app.py
```

Then open your browser to:

```
http://localhost:5000
```

That's it — the whole app (dashboard, goals, tasks, calendar, commitments,
habits, smart planner, reports) lives on that one page with a sidebar to
switch between sections.

## 3. How your data is stored

The first time you run it, a `data/` folder is created next to `app.py`
with these files — all plain JSON, easy to back up or inspect:

- `goals.json`
- `tasks.json`
- `commitments.json` (school / tuition / fixed commitments)
- `habits.json`
- `state.json` (streak tracking)

Delete the `data/` folder at any time to start completely fresh.

## 4. Suggested first steps in the app

1. Go to **School & Tuition** → add your school hours and tuition as
   recurring commitments (pick the days of the week + start/end time).
2. Go to **Goals** → add a goal with a deadline, importance (1–5) and a
   target number of hours.
3. Go to **Smart Planner** → see your goals ranked by urgency, and a
   suggested time-blocked schedule for today built only out of your free time.
4. Go to **Tasks** → add/complete daily tasks (optionally linked to a goal —
   completing a linked task logs hours toward it automatically).
5. Go to **Habits** → add things like Meditation, Walk, Photo Post and tap
   the checkmark each day to build a streak.
6. Check the **Dashboard** daily — it shows your streak, reminders, and the
   single thing the AI recommends you work on next.
7. Check **Reports** weekly for your completion rate and top gsoal.

## 5. Project structure

```
app.py            Flask backend — all REST API routes
scheduler.py       Smart planner logic: free-slot detection, priority
                    scoring, schedule suggestions, auto-adjust overdue
storage.py          JSON load/save helpers
templates/index.html  Single-page frontend shell
static/style.css      Design system
static/app.js         All frontend logic (fetches the API, renders views)
data/                 Auto-created — your JSON data lives here
```

## 6. Notes / things you can extend later

The "Future Advanced Features" from your original list (GUI via Tkinter,
Google Calendar sync, Pomodoro timer, expense tracking, mobile app, etc.)
aren't built yet — this version covers every module you checked off.
Since this is a normal Flask + JSON app, those are all addable later
without re-architecting anything.
