// ============================================================
// Pilot — Personal AI Planner frontend
// ============================================================

const api = {
  get: (url) => fetch(url).then(r => r.json()),
  post: (url, body) => fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) }).then(r => r.json()),
  put: (url, body) => fetch(url, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) }).then(r => r.json()),
  del: (url) => fetch(url, { method: "DELETE" }).then(r => r.json()),
};

const fmtDate = (d) => d.toISOString().slice(0, 10);
const todayStr = () => fmtDate(new Date());

// ------------------------------------------------------------
// Navigation
// ------------------------------------------------------------
const TITLES = {
  dashboard: "Dashboard", goals: "Goals", tasks: "Daily Tasks", calendar: "Calendar & Scheduling",
  commitments: "School, Tuition & Commitments", habits: "Habit Tracker", smart: "Smart Planner", reports: "Weekly Report",
};

document.querySelectorAll(".nav-item").forEach(btn => {
  btn.addEventListener("click", () => switchView(btn.dataset.view));
});

function switchView(view) {
  document.querySelectorAll(".nav-item").forEach(b => b.classList.toggle("active", b.dataset.view === view));
  document.querySelectorAll(".view").forEach(v => v.classList.toggle("active", v.id === `view-${view}`));
  document.getElementById("viewTitle").textContent = TITLES[view];
  if (view === "dashboard") loadDashboard();
  if (view === "goals") loadGoals();
  if (view === "tasks") loadTasks();
  if (view === "calendar") loadWeekCalendar();
  if (view === "commitments") loadCommitments();
  if (view === "habits") loadHabits();
  if (view === "smart") loadSmartPlanner();
  if (view === "reports") loadReports();
}

// ------------------------------------------------------------
// Modal helpers
// ------------------------------------------------------------
const overlay = document.getElementById("modalOverlay");
const modalBox = document.getElementById("modalBox");

function openModal(html) {
  modalBox.innerHTML = html;
  overlay.classList.remove("hidden");
}
function closeModal() { overlay.classList.add("hidden"); }
overlay.addEventListener("click", (e) => { if (e.target === overlay) closeModal(); });

// ------------------------------------------------------------
// Dashboard
// ------------------------------------------------------------
async function loadDashboard() {
  const d = await api.get("/api/dashboard");
  document.getElementById("statActiveGoals").textContent = d.active_goals;
  document.getElementById("statCompletedGoals").textContent = d.completed_goals;
  document.getElementById("statHours").textContent = d.total_hours_logged;
  document.getElementById("statTodayDone").textContent = d.today_tasks_done;
  document.getElementById("statTodayTotal").textContent = d.today_tasks_total;
  document.getElementById("statStreak").textContent = `${d.current_streak} 🔥`;
  document.getElementById("statBestStreak").textContent = `${d.best_streak} 🏆`;
  document.getElementById("sidebarStreak").textContent = d.current_streak;

  renderReminders(d.reminders);
  renderPulse("priorityPulse", d.goals);
  renderRecommendation(d.recommendation);
}

function renderReminders(reminders) {
  document.getElementById("reminderCount").textContent = reminders.length;
  const panel = document.getElementById("reminderPanel");
  if (!reminders.length) {
    panel.innerHTML = `<div class="muted">No reminders — you're all caught up.</div>`;
  } else {
    panel.innerHTML = reminders.map(r => `<div class="reminder-item ${r.severity}">${escapeHtml(r.text)}</div>`).join("");
  }
}
document.getElementById("bellBtn").addEventListener("click", () => {
  document.getElementById("reminderPanel").classList.toggle("hidden");
});

function renderPulse(containerId, goals) {
  const el = document.getElementById(containerId);
  if (!goals || !goals.length) { el.innerHTML = `<div class="muted">No active goals yet.</div>`; return; }
  const maxScore = Math.max(...goals.map(g => g.priority_score || g.score || 0), 1);
  el.innerHTML = goals.map(g => {
    const score = g.priority_score ?? 0;
    const pct = Math.max(Math.min((score / maxScore) * 100, 100), 4);
    return `
      <div class="pulse-row">
        <div class="pulse-meta">
          <div class="pulse-title">${escapeHtml(g.title)}</div>
          <div class="pulse-bar-track"><div class="pulse-bar-fill" style="width:${pct}%"></div></div>
        </div>
        <div class="pulse-score">${score}</div>
      </div>`;
  }).join("");
}

function renderRecommendation(rec) {
  const el = document.getElementById("recommendation");
  if (!rec || !rec.item) { el.innerHTML = `<div class="muted">Nothing urgent — add a goal or task to get a recommendation.</div>`; return; }
  if (rec.type === "task") {
    el.innerHTML = `<div class="rec-title">✅ ${escapeHtml(rec.item.title)}</div><div class="muted">A task is already scheduled for today — knock it out first.</div>`;
  } else {
    el.innerHTML = `<div class="rec-title">🎯 ${escapeHtml(rec.item.title)}</div><div class="muted">Highest priority goal right now (score ${rec.score}). Consider blocking time for it today.</div>`;
  }
}

// ------------------------------------------------------------
// Goals
// ------------------------------------------------------------
let goalsCache = [];

async function loadGoals() {
  goalsCache = await api.get("/api/goals");
  renderGoals();
}

function renderGoals() {
  const el = document.getElementById("goalsList");
  if (!goalsCache.length) { el.innerHTML = `<div class="card muted">No goals yet. Click "+ New goal" to add one.</div>`; return; }
  const sorted = [...goalsCache].sort((a, b) => (b.priority_score || 0) - (a.priority_score || 0));
  el.innerHTML = sorted.map(g => {
    const tags = [];
    if (g.status === "completed") tags.push(`<span class="tag done">✓ completed</span>`);
    if (g.deadline) {
      if (g.days_until_deadline < 0) tags.push(`<span class="tag overdue">overdue ${Math.abs(g.days_until_deadline)}d</span>`);
      else tags.push(`<span class="tag deadline">due in ${g.days_until_deadline}d</span>`);
    }
    tags.push(`<span class="tag">importance ${g.importance}/5</span>`);
    tags.push(`<span class="tag">${g.weekly_hours_needed}h/week needed</span>`);
    return `
      <div class="goal-card">
        <div class="goal-top">
          <div>
            <div class="goal-title">${escapeHtml(g.title)}</div>
            ${g.description ? `<div class="goal-desc">${escapeHtml(g.description)}</div>` : ""}
          </div>
          <div class="goal-actions">
            <button class="btn small" onclick="openLogHoursModal('${g.id}')">+ log hours</button>
            <button class="btn small" onclick="openGoalModal('${g.id}')">edit</button>
            <button class="btn small danger" onclick="deleteGoal('${g.id}')">delete</button>
          </div>
        </div>
        <div class="goal-tags">${tags.join("")}</div>
        <div class="progress-track"><div class="progress-fill" style="width:${g.progress_pct}%"></div></div>
        <div class="goal-stats-row">
          <span>${g.progress_pct}% complete</span>
          <span>${g.hours_logged || 0}h logged of ${g.target_hours || 0}h target</span>
          <span>${g.hours_remaining}h remaining</span>
        </div>
      </div>`;
  }).join("");
}

function openGoalModal(id) {
  const g = id ? goalsCache.find(x => x.id === id) : null;
  openModal(`
    <h3>${g ? "Edit goal" : "New goal"}</h3>
    <div class="field"><label>Title</label><input id="gTitle" value="${g ? escapeAttr(g.title) : ""}" placeholder="e.g. Finish photography portfolio"></div>
    <div class="field"><label>Description</label><textarea id="gDesc" rows="2">${g ? escapeHtml(g.description || "") : ""}</textarea></div>
    <div class="field-row">
      <div class="field"><label>Deadline</label><input type="date" id="gDeadline" value="${g && g.deadline ? g.deadline : ""}"></div>
      <div class="field"><label>Importance (1-5)</label><input type="number" id="gImportance" min="1" max="5" value="${g ? g.importance : 3}"></div>
    </div>
    <div class="field"><label>Target hours</label><input type="number" id="gTargetHours" min="0" step="0.5" value="${g ? g.target_hours : 10}"></div>
    <div class="modal-actions">
      <button class="btn" onclick="closeModal()">Cancel</button>
      <button class="btn primary" onclick="saveGoal('${id || ""}')">Save</button>
    </div>
  `);
}

async function saveGoal(id) {
  const payload = {
    title: document.getElementById("gTitle").value || "Untitled goal",
    description: document.getElementById("gDesc").value,
    deadline: document.getElementById("gDeadline").value || null,
    importance: parseInt(document.getElementById("gImportance").value || 3),
    target_hours: parseFloat(document.getElementById("gTargetHours").value || 0),
  };
  if (id) await api.put(`/api/goals/${id}`, payload);
  else await api.post("/api/goals", payload);
  closeModal();
  loadGoals();
}

async function deleteGoal(id) {
  if (!confirm("Delete this goal? Linked tasks will be unlinked, not deleted.")) return;
  await api.del(`/api/goals/${id}`);
  loadGoals();
}

function openLogHoursModal(id) {
  openModal(`
    <h3>Log hours worked</h3>
    <div class="field"><label>Hours</label><input type="number" id="logHoursVal" min="0" step="0.25" value="1"></div>
    <div class="modal-actions">
      <button class="btn" onclick="closeModal()">Cancel</button>
      <button class="btn primary" onclick="submitLogHours('${id}')">Log</button>
    </div>
  `);
}
async function submitLogHours(id) {
  const hours = parseFloat(document.getElementById("logHoursVal").value || 0);
  await api.post(`/api/goals/${id}/log_hours`, { hours });
  closeModal();
  loadGoals();
}

document.getElementById("newGoalBtn").addEventListener("click", () => openGoalModal(null));

// ------------------------------------------------------------
// Tasks
// ------------------------------------------------------------
let tasksCache = [];
document.getElementById("taskDateFilter").value = todayStr();
document.getElementById("taskDateFilter").addEventListener("change", loadTasks);

async function loadTasks() {
  const dateVal = document.getElementById("taskDateFilter").value;
  const url = dateVal ? `/api/tasks?date=${dateVal}` : "/api/tasks";
  tasksCache = await api.get(url);
  goalsCache = await api.get("/api/goals");
  renderTasks();
}

function renderTasks() {
  const el = document.getElementById("tasksList");
  if (!tasksCache.length) { el.innerHTML = `<div class="card muted">No tasks for this date.</div>`; return; }
  el.innerHTML = tasksCache.map(t => {
    const goal = goalsCache.find(g => g.id === t.goal_id);
    const overdue = t.overdue_from && !t.completed;
    return `
      <div class="task-row ${t.completed ? "completed" : ""} ${overdue ? "overdue" : ""}">
        <button class="task-check" onclick="toggleTask('${t.id}')">${t.completed ? "✓" : ""}</button>
        <div>
          <div class="task-title">${escapeHtml(t.title)}</div>
          <div class="task-meta">${goal ? "🎯 " + escapeHtml(goal.title) + " · " : ""}${t.duration_minutes} min ${overdue ? "· overdue from " + t.overdue_from : ""}</div>
        </div>
        <div class="task-spacer"></div>
        <button class="btn small" onclick="deleteTask('${t.id}')">delete</button>
      </div>`;
  }).join("");
}

async function toggleTask(id) {
  await api.post(`/api/tasks/${id}/complete`);
  loadTasks();
}
async function deleteTask(id) {
  await api.del(`/api/tasks/${id}`);
  loadTasks();
}

function openTaskModal() {
  const goalOptions = goalsCache.map(g => `<option value="${g.id}">${escapeAttr(g.title)}</option>`).join("");
  openModal(`
    <h3>New task</h3>
    <div class="field"><label>Title</label><input id="tTitle" placeholder="e.g. Edit 10 photos"></div>
    <div class="field"><label>Linked goal (optional)</label><select id="tGoal"><option value="">— none —</option>${goalOptions}</select></div>
    <div class="field-row">
      <div class="field"><label>Date</label><input type="date" id="tDate" value="${document.getElementById("taskDateFilter").value || todayStr()}"></div>
      <div class="field"><label>Duration (min)</label><input type="number" id="tDuration" value="30" min="5"></div>
    </div>
    <div class="modal-actions">
      <button class="btn" onclick="closeModal()">Cancel</button>
      <button class="btn primary" onclick="saveTask()">Save</button>
    </div>
  `);
}
async function saveTask() {
  const payload = {
    title: document.getElementById("tTitle").value || "Untitled task",
    goal_id: document.getElementById("tGoal").value || null,
    date: document.getElementById("tDate").value || todayStr(),
    duration_minutes: parseInt(document.getElementById("tDuration").value || 30),
  };
  await api.post("/api/tasks", payload);
  closeModal();
  loadTasks();
}
document.getElementById("newTaskBtn").addEventListener("click", async () => {
  goalsCache = await api.get("/api/goals");
  openTaskModal();
});

// ------------------------------------------------------------
// Calendar (week view)
// ------------------------------------------------------------
let weekStart = startOfWeek(new Date());
function startOfWeek(d) {
  const date = new Date(d);
  const day = (date.getDay() + 6) % 7; // Monday=0
  date.setDate(date.getDate() - day);
  date.setHours(0, 0, 0, 0);
  return date;
}

document.getElementById("weekPrevBtn").addEventListener("click", () => { weekStart.setDate(weekStart.getDate() - 7); loadWeekCalendar(); });
document.getElementById("weekNextBtn").addEventListener("click", () => { weekStart.setDate(weekStart.getDate() + 7); loadWeekCalendar(); });
document.getElementById("weekTodayBtn").addEventListener("click", () => { weekStart = startOfWeek(new Date()); loadWeekCalendar(); });

async function loadWeekCalendar() {
  const days = await api.get(`/api/calendar/week?start=${fmtDate(weekStart)}`);
  const el = document.getElementById("weekCalendar");
  el.innerHTML = days.map(d => {
    const blocks = [];
    d.occupied.forEach(b => blocks.push(`<div class="block occupied">${b.start}–${b.end} ${escapeHtml(b.title)}</div>`));
    d.tasks.forEach(t => blocks.push(`<div class="block task ${t.completed ? "completed" : ""}">${t.duration_minutes}min — ${escapeHtml(t.title)}</div>`));
    d.free_slots.forEach(s => blocks.push(`<div class="block free">${s.start}–${s.end} free</div>`));
    const isToday = d.date === todayStr();
    return `
      <div class="day-col" style="${isToday ? "border-color:#d99a2b;" : ""}">
        <div class="day-col-head">${d.weekday}<span class="d">${d.date}</span></div>
        ${blocks.join("") || `<div class="muted" style="font-size:0.75rem">Nothing scheduled</div>`}
      </div>`;
  }).join("");
}

// ------------------------------------------------------------
// Commitments
// ------------------------------------------------------------
let commitmentsCache = [];
async function loadCommitments() {
  commitmentsCache = await api.get("/api/commitments");
  renderCommitments();
}
function renderCommitments() {
  const el = document.getElementById("commitmentsList");
  if (!commitmentsCache.length) { el.innerHTML = `<div class="card muted">No fixed commitments yet — add school hours, tuition, or recurring activities.</div>`; return; }
  const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  el.innerHTML = commitmentsCache.map(c => {
    const when = c.recurring ? c.days_of_week.map(i => DAYS[i]).join(", ") : c.date;
    return `
      <div class="commitment-row">
        <span class="commitment-type">${escapeHtml(c.type)}</span>
        <div>
          <div class="task-title">${escapeHtml(c.title)}</div>
          <div class="task-meta">${c.start_time}–${c.end_time} · ${when || "—"}</div>
        </div>
        <div class="task-spacer"></div>
        <button class="btn small danger" onclick="deleteCommitment('${c.id}')">delete</button>
      </div>`;
  }).join("");
}
async function deleteCommitment(id) {
  await api.del(`/api/commitments/${id}`);
  loadCommitments();
}
function openCommitmentModal() {
  openModal(`
    <h3>Add commitment</h3>
    <div class="field"><label>Title</label><input id="cTitle" placeholder="e.g. School, Math tuition, Evening walk"></div>
    <div class="field"><label>Type</label>
      <select id="cType"><option value="school">School</option><option value="tuition">Tuition</option><option value="fixed">Fixed / other</option></select>
    </div>
    <div class="field-row">
      <div class="field"><label>Start time</label><input type="time" id="cStart" value="09:00"></div>
      <div class="field"><label>End time</label><input type="time" id="cEnd" value="10:00"></div>
    </div>
    <div class="field">
      <label>Recurs on (leave blank for a one-off date)</label>
      <div class="checkbox-row" id="cDays">
        ${["Mon","Tue","Wed","Thu","Fri","Sat","Sun"].map((d,i) => `<label><input type="checkbox" value="${i}"> ${d}</label>`).join("")}
      </div>
    </div>
    <div class="field"><label>One-off date (optional, used if no days checked)</label><input type="date" id="cDate"></div>
    <div class="modal-actions">
      <button class="btn" onclick="closeModal()">Cancel</button>
      <button class="btn primary" onclick="saveCommitment()">Save</button>
    </div>
  `);
}
async function saveCommitment() {
  const days = [...document.querySelectorAll("#cDays input:checked")].map(cb => parseInt(cb.value));
  const recurring = days.length > 0;
  const payload = {
    title: document.getElementById("cTitle").value || "Commitment",
    type: document.getElementById("cType").value,
    start_time: document.getElementById("cStart").value,
    end_time: document.getElementById("cEnd").value,
    recurring,
    days_of_week: days,
    date: recurring ? null : (document.getElementById("cDate").value || todayStr()),
  };
  await api.post("/api/commitments", payload);
  closeModal();
  loadCommitments();
}
document.getElementById("newCommitmentBtn").addEventListener("click", openCommitmentModal);

// ------------------------------------------------------------
// Habits
// ------------------------------------------------------------
let habitsCache = [];
async function loadHabits() {
  habitsCache = await api.get("/api/habits");
  renderHabits();
}
function renderHabits() {
  const el = document.getElementById("habitsList");
  if (!habitsCache.length) { el.innerHTML = `<div class="card muted">No habits yet — try Meditation, Walk, or Photo Post.</div>`; return; }
  const today = todayStr();
  el.innerHTML = habitsCache.map(h => {
    const doneToday = !!(h.log && h.log[today]);
    return `
      <div class="habit-row">
        <div class="habit-icon">${h.icon}</div>
        <div class="habit-name">${escapeHtml(h.name)}</div>
        <div class="habit-streak">🔥 ${h.streak} · best ${h.best_streak}</div>
        <button class="habit-toggle ${doneToday ? "done" : ""}" onclick="toggleHabit('${h.id}')">${doneToday ? "✓" : ""}</button>
        <button class="btn small danger" onclick="deleteHabit('${h.id}')">delete</button>
      </div>`;
  }).join("");
}
async function toggleHabit(id) {
  await api.post(`/api/habits/${id}/toggle`, { date: todayStr() });
  loadHabits();
}
async function deleteHabit(id) {
  await api.del(`/api/habits/${id}`);
  loadHabits();
}
function openHabitModal() {
  openModal(`
    <h3>New habit</h3>
    <div class="field"><label>Name</label><input id="hName" placeholder="e.g. Meditation"></div>
    <div class="field"><label>Icon (emoji)</label><input id="hIcon" value="✅" maxlength="2"></div>
    <div class="modal-actions">
      <button class="btn" onclick="closeModal()">Cancel</button>
      <button class="btn primary" onclick="saveHabit()">Save</button>
    </div>
  `);
}
async function saveHabit() {
  await api.post("/api/habits", { name: document.getElementById("hName").value || "New habit", icon: document.getElementById("hIcon").value || "✅" });
  closeModal();
  loadHabits();
}
document.getElementById("newHabitBtn").addEventListener("click", openHabitModal);

// ------------------------------------------------------------
// Smart Planner
// ------------------------------------------------------------
async function loadSmartPlanner() {
  const [priorities, schedule] = await Promise.all([
    api.get("/api/smart/priorities"),
    api.get(`/api/smart/schedule?date=${todayStr()}`),
  ]);
  renderPulse("smartPriorities", priorities);

  const schedEl = document.getElementById("smartSchedule");
  schedEl.innerHTML = schedule.length
    ? schedule.map(b => `<div class="sched-block"><span class="sched-time">${b.start}–${b.end}</span><span>${escapeHtml(b.goal_title)}</span><span class="muted">${b.minutes}min</span></div>`).join("")
    : `<div class="muted">No free slots or active goals to schedule today.</div>`;

  const table = document.getElementById("weeklyHoursTable");
  if (!priorities.length) {
    table.innerHTML = `<div class="muted">No active goals.</div>`;
  } else {
    table.innerHTML = `<table>
      <tr><th>Goal</th><th>Hours remaining</th><th>Days left</th><th>Hours/week needed</th></tr>
      ${priorities.map(g => `<tr><td>${escapeHtml(g.title)}</td><td>${g.hours_remaining}</td><td>${g.days_until_deadline === 9999 ? "—" : g.days_until_deadline}</td><td>${g.weekly_hours_needed}</td></tr>`).join("")}
    </table>`;
  }
}
document.getElementById("refreshSmartBtn").addEventListener("click", async () => {
  await api.post("/api/smart/auto_adjust");
  loadSmartPlanner();
});

// ------------------------------------------------------------
// Reports
// ------------------------------------------------------------
async function loadReports() {
  const r = await api.get("/api/reports/weekly");
  document.getElementById("repScheduled").textContent = r.tasks_scheduled;
  document.getElementById("repCompleted").textContent = r.tasks_completed;
  document.getElementById("repRate").textContent = r.completion_rate + "%";
  document.getElementById("repHours").textContent = r.hours_worked;

  document.getElementById("repTopGoal").innerHTML = r.top_goal
    ? `<div class="rec-title">🏆 ${escapeHtml(r.top_goal.title)}</div><div class="muted">${r.top_goal.hours}h logged this week</div>`
    : `<div class="muted">No goal hours logged this week yet.</div>`;

  const maxTotal = Math.max(...r.daily_breakdown.map(d => d.total), 1);
  document.getElementById("repDaily").innerHTML = r.daily_breakdown.map(d => {
    const pct = d.total ? (d.completed / d.total) * 100 : 0;
    return `<div class="daily-row"><span class="dlabel">${d.weekday} ${d.date.slice(5)}</span><div class="dbar-track"><div class="dbar-fill" style="width:${pct}%"></div></div><span>${d.completed}/${d.total}</span></div>`;
  }).join("");
}

// ------------------------------------------------------------
// Utils
// ------------------------------------------------------------
function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function escapeAttr(str) { return escapeHtml(str); }

// ------------------------------------------------------------
// Init
// ------------------------------------------------------------
loadDashboard();
