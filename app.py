from flask import Flask, render_template, request, redirect, url_for, send_file, session, flash
import sqlite3
import json
import csv
import io
import os
from datetime import datetime
from dotenv import load_dotenv
import random
import string
# @app.route("/lead-dashboard")
# def lead_dashboard():
#     return home()

def ensure_column_exists(table_name, column_name, column_type):
    """Check if a column exists, and add it if missing."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [info[1] for info in cursor.fetchall()]
    if column_name not in columns:
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
        conn.commit()
    conn.close()
# Optional Gemini import (if available)
try:
    import google.generativeai as genai
    GENAI = True
except Exception:
    GENAI = False

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "task_manager_secret")
DB_PATH = "inter_team_task.db"


# ---------------- Utility DB helpers ----------------
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_column_exists(table, column, definition):
    """Add column if not exists (simple handler)."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    cols = [r[1] for r in cur.fetchall()]
    if column not in cols:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        conn.commit()
    conn.close()


# ---------------- DB INIT / MIGRATION ----------------
def init_db():
    conn = get_db()
    cur = conn.cursor()

    # tasks table (if doesn't exist) - ensure team_id column exists
    cur.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task TEXT,
        assigned_to TEXT,
        priority TEXT,
        status TEXT,
        created_at TEXT,
        sub_tasks TEXT,
        explanation TEXT,
        team_id INTEGER
    );
    """)

    # users table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        display_name TEXT,
        password TEXT,
        role TEXT,
        team_id INTEGER,
        member_code TEXT
    );
    """)

    # teams table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS teams (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        team_code TEXT,
        lead_id INTEGER,
        member_count INTEGER
    );
    """)

    # submissions table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS submissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id INTEGER,
        member_id INTEGER,
        github_link TEXT,
        submitted_on TEXT
    );
    """)

    conn.commit()
    conn.close()


# initialize DB (creates tables if missing)
if not os.path.exists(DB_PATH):
    init_db()
else:
    # ensure team_id column exists in tasks if DB older
    ensure_column_exists("tasks", "team_id", "INTEGER")


# ---------------- Auth Helpers ----------------
def create_member_codes(team_code, count):
    """Return list of unique member codes for a team, e.g., TEAM123-01, TEAM123-02"""
    codes = []
    for i in range(1, count + 1):
        codes.append(f"{team_code}-{i:02d}")
    return codes


def generate_team_code():
    return "TEAM" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))


def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    conn.close()
    return user


def login_required(role=None):
    def decorator(fn):
        from functools import wraps
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = current_user()
            if not user:
                return redirect(url_for("landing"))
            if role and user["role"] != role:
                flash("Access denied", "danger")
                return redirect(url_for("home_for_role"))
            return fn(*args, **kwargs)
        return wrapper
    return decorator


# ---------------- Landing / Role selection ----------------
@app.route("/")
def landing():
    # Simple landing page - choose lead or member
    return render_template("landing.html")


@app.route("/home")
def home_for_role():
    """Redirect to appropriate dashboard based on session role."""
    user = current_user()
    if not user:
        return redirect(url_for("landing"))
    if user["role"] == "lead":
        return redirect(url_for("lead_dashboard"))
    else:
        return redirect(url_for("member_dashboard"))


# ---------------- Lead: Register / Login ----------------
@app.route("/lead-register", methods=["GET", "POST"])
def lead_register():
    if request.method == "POST":
        username = request.form.get("username").strip()
        display_name = request.form.get("display_name").strip() or username
        password = request.form.get("password").strip()
        if not username or not password:
            flash("Provide username and password", "warning")
            return redirect(url_for("lead_register"))

        conn = get_db()
        existing = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        if existing:
            flash("Username already exists", "danger")
            conn.close()
            return redirect(url_for("lead_register"))

        conn.execute("INSERT INTO users (username, display_name, password, role) VALUES (?, ?, ?, ?)",
                     (username, display_name, password, "lead"))
        conn.commit()
        conn.close()
        flash("Lead account created. Login now.", "success")
        return redirect(url_for("lead_login"))
    return render_template("lead_register.html")


@app.route("/lead-login", methods=["GET", "POST"])
def lead_login():
    if request.method == "POST":
        username = request.form.get("username").strip()
        password = request.form.get("password").strip()
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE username=? AND password=? AND role='lead'", (username, password)).fetchone()
        conn.close()
        if user:
            session["user_id"] = user["id"]
            session["role"] = "lead"
            session["team_id"] = user["team_id"]
            return redirect(url_for("lead_dashboard"))
        else:
            flash("Invalid credentials", "danger")
            return redirect(url_for("lead_login"))
    return render_template("lead_login.html")


@app.route("/lead-logout")
def lead_logout():
    session.clear()
    return redirect(url_for("landing"))


# ---------------- Member: Join / Login ----------------
@app.route("/member-join", methods=["GET", "POST"])
def member_join():
    if request.method == "POST":
        display_name = request.form.get("display_name").strip()
        username = request.form.get("username").strip()
        password = request.form.get("password").strip()
        member_code = request.form.get("member_code").strip()
        if not member_code or not username or not password:
            flash("Fill all fields", "warning")
            return redirect(url_for("member_join"))

        conn = get_db()
        # find team by member_code
        team = conn.execute("SELECT * FROM teams WHERE team_code = substr(?, 1, instr(?, '-') - 1)", (member_code, member_code)).fetchone()
        # fallback: try matching member_code in users table (if leads pre-created codes)
        if not team:
            # attempt to locate team by parsing before hyphen
            code_part = member_code.split("-")[0]
            team = conn.execute("SELECT * FROM teams WHERE team_code=?", (code_part,)).fetchone()

        if not team:
            flash("Invalid join code", "danger")
            conn.close()
            return redirect(url_for("member_join"))

        # check if member_code already used
        exists = conn.execute("SELECT * FROM users WHERE member_code=?", (member_code,)).fetchone()
        if exists:
            flash("This join code is already used", "danger")
            conn.close()
            return redirect(url_for("member_join"))

        conn.execute("INSERT INTO users (username, display_name, password, role, team_id, member_code) VALUES (?, ?, ?, ?, ?, ?)",
                     (username, display_name, password, "member", team["id"], member_code))
        conn.commit()
        conn.close()
        flash("Joined successfully. Login now.", "success")
        return redirect(url_for("member_login"))
    return render_template("member_join.html")


@app.route("/member-login", methods=["GET", "POST"])
def member_login():
    if request.method == "POST":
        username = request.form.get("username").strip()
        password = request.form.get("password").strip()
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE username=? AND password=? AND role='member'", (username, password)).fetchone()
        conn.close()
        if user:
            session["user_id"] = user["id"]
            session["role"] = "member"
            session["team_id"] = user["team_id"]
            return redirect(url_for("member_dashboard"))
        else:
            flash("Invalid credentials", "danger")
            return redirect(url_for("member_login"))
    return render_template("member_login.html")


@app.route("/member-logout")
def member_logout():
    session.clear()
    return redirect(url_for("landing"))


# ---------------- Lead: Create Team & Dashboard ----------------
@app.route("/lead/create-team", methods=["GET", "POST"])
@login_required(role="lead")
def create_team():
    user = current_user()
    if request.method == "POST":
        member_count = int(request.form.get("member_count", 1))
        team_code = generate_team_code()
        conn = get_db()
        cur = conn.cursor()
        cur.execute("INSERT INTO teams (team_code, lead_id, member_count) VALUES (?, ?, ?)",
                    (team_code, user["id"], member_count))
        team_id = cur.lastrowid
        # generate member codes
        codes = create_member_codes(team_code, member_count)
        # Save member_code placeholders in users table for tracking (optional)
        # We do not create user rows yet; codes are shown to lead
        conn.commit()
        conn.close()
        return render_template("create_team_done.html", team_code=team_code, codes=codes)
    return render_template("create_team.html")


@app.route("/lead/dashboard")
@login_required(role="lead")
def lead_dashboard():
    user = current_user()
    conn = get_db()
    # tasks for this lead's team(s) - assume lead has a team created
    team = conn.execute("SELECT * FROM teams WHERE lead_id=?", (user["id"],)).fetchone()
    team_id = team["id"] if team else None
    tasks = []
    if team_id:
        tasks = conn.execute("SELECT * FROM tasks WHERE team_id=? ORDER BY id DESC", (team_id,)).fetchall()
    conn.close()
    return render_template("lead_dashboard.html", tasks=tasks, team=team, user=user)


# ---------------- Member Dashboard ----------------
@app.route("/member/dashboard")
@login_required(role="member")
def member_dashboard():
    user = current_user()
    conn = get_db()
    # show tasks for user's team
    tasks = conn.execute("SELECT * FROM tasks WHERE team_id=? ORDER BY id DESC", (user["team_id"],)).fetchall()
    # show submissions by this member
    submissions = conn.execute("SELECT * FROM submissions WHERE member_id=?", (user["id"],)).fetchall()
    conn.close()
    return render_template("member_dashboard.html", tasks=tasks, submissions=submissions, user=user)


# ---------------- Submit GitHub Link ----------------
@app.route("/submit/<int:task_id>", methods=["GET", "POST"])
@login_required(role="member")
def submit_github(task_id):
    user = current_user()
    if request.method == "POST":
        link = request.form.get("github_link", "").strip()
        created = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = get_db()
        conn.execute("INSERT INTO submissions (task_id, member_id, github_link, submitted_on) VALUES (?, ?, ?, ?)",
                     (task_id, user["id"], link, created))
        conn.commit()
        conn.close()
        flash("Submitted link. Team Lead will review.", "success")
        return redirect(url_for("member_dashboard"))
    # GET -> show form
    conn = get_db()
    task = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    conn.close()
    return render_template("submit_link.html", task=task)


# ---------------- Member marks task done (notifies lead) ----------------
@app.route("/member-mark-done/<int:task_id>")
@login_required(role="member")
def member_mark_done(task_id):
    user = current_user()
    conn = get_db()
    # Ensure task belongs to the member's team
    task = conn.execute("SELECT * FROM tasks WHERE id=? AND team_id=?", (task_id, user["team_id"])).fetchone()
    if not task:
        conn.close()
        flash("Task not found or not allowed", "danger")
        return redirect(url_for("member_dashboard"))
    conn.execute("UPDATE tasks SET status=? WHERE id=?", ("Done", task_id))
    conn.commit()
    conn.close()
    flash("Marked done - team lead will review the submission.", "success")
    return redirect(url_for("member_dashboard"))


# ---------------- AI Chatbot for Members ----------------
@app.route("/ai-chat", methods=["GET", "POST"])
@login_required(role="member")
def ai_chat():
    user = current_user()
    response_text = None
    error = None
    if request.method == "POST":
        question = request.form.get("question", "").strip()
        if question:
            if GENAI and os.getenv("GEMINI_API_KEY"):
                try:
                    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
                    model_name = os.getenv("GEMINI_MODEL", "models/gemini-2.5-flash")
                    model = genai.GenerativeModel(model_name)
                    prompt = f"You are an assistant for students building projects. Answer concisely and help debug or suggest steps for: {question}"
                    resp = model.generate_content(prompt)
                    response_text = getattr(resp, "text", "") or str(resp)
                except Exception as e:
                    error = f"AI error: {e}"
            else:
                # fallback canned response
                response_text = "AI not configured. Try asking about specific errors or steps (e.g., 'How to set up JWT auth in Flask?')."
    return render_template("ai_chat.html", response=response_text, error=error)


# ---------------- Keep existing core routes (task CRUD, AI suggestions, etc.) ----------------
# We preserve your previous routes so nothing breaks. We'll wrap add-task to associate team when lead adds.
# ADD TASK (Team Lead assigns task to a member)
@app.route("/add-task", methods=["GET", "POST"])
def add_task():
    # Only team lead can add tasks
    if session.get("role") != "lead":
        return redirect(url_for("home"))

    conn = get_db()

    if request.method == "POST":
        task = request.form.get("task", "").strip()
        assigned_user_id = request.form.get("assigned_to")
        priority = request.form.get("priority", "Medium")
        status = "To-Do"
        created = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Basic validation
        if not task or not assigned_user_id:
            conn.close()
            return redirect(url_for("add_task"))

        conn.execute("""
            INSERT INTO tasks (task, assigned_to, priority, status, created_at, team_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            task,
            assigned_user_id,
            priority,
            status,
            created,
            session["team_id"]
        ))

        conn.commit()
        conn.close()
        return redirect(url_for("task_list"))

    # GET: load team members dynamically
    members = conn.execute("""
        SELECT id, display_name
        FROM users
        WHERE team_id=? AND role='member'
    """, (session["team_id"],)).fetchall()

    conn.close()
    return render_template("add_task.html", members=members)


# Keep other existing routes (task_list, ai-suggestions, ai-subtasks, explain, update-status, delete, export-csv, delay-prediction)
# We'll adapt task_list to show tasks based on role/team

@app.route("/task-list")
def task_list():
    user = current_user()
    conn = get_db()
    if user and user["role"] == "lead":
        # show tasks for lead's team
        team = conn.execute("SELECT * FROM teams WHERE lead_id=?", (user["id"],)).fetchone()
        team_id = team["id"] if team else None
        if team_id:
            tasks = conn.execute("SELECT * FROM tasks WHERE team_id=? ORDER BY id DESC", (team_id,)).fetchall()
        else:
            tasks = []
    elif user and user["role"] == "member":
        tasks = conn.execute("SELECT * FROM tasks WHERE team_id=? ORDER BY id DESC", (user["team_id"],)).fetchall()
    else:
        # show all tasks (for admins or general)
        tasks = conn.execute("SELECT * FROM tasks ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("task_list.html", tasks=tasks)

# AI SUGGESTIONS (Lead only) – generate tasks and allow assignment to members
@app.route("/ai-suggestions", methods=["GET", "POST"])
@login_required(role="lead")
def ai_suggestions_lead():
    suggestions = []
    error = None
    project_desc = ""

    user = current_user()
    conn = get_db()

    # get team
    team = conn.execute(
        "SELECT * FROM teams WHERE lead_id=?",
        (user["id"],)
    ).fetchone()

    team_id = team["id"] if team else None

    # load team members for dropdown
    members = conn.execute("""
        SELECT id, display_name
        FROM users
        WHERE team_id=? AND role='member'
    """, (team_id,)).fetchall()

    if request.method == "POST":
        project_desc = request.form.get("project_desc", "").strip()

        if project_desc:
            if GENAI and os.getenv("GEMINI_API_KEY"):
                try:
                    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
                    model = genai.GenerativeModel(
                        os.getenv("GEMINI_MODEL", "models/gemini-2.5-flash")
                    )

                    prompt = f"""
Return ONLY JSON in this format:
{{ "tasks": ["task1","task2","task3","task4","task5","task6"] }}

Project: {project_desc}
"""
                    resp = model.generate_content(prompt)
                    data = json.loads(resp.text)
                    suggestions = data.get("tasks", [])

                except Exception as e:
                    error = f"AI error: {e}"

            # fallback if AI fails
            if not suggestions:
                suggestions = [
                    "Define project scope and requirements",
                    "Design UI/UX wireframes",
                    "Set up backend & database",
                    "Implement core features and APIs",
                    "Integrate AI and business logic",
                    "Test, document and deploy"
                ]

    conn.close()

    return render_template(
        "ai_suggestion.html",
        suggestions=suggestions,
        members=members,
        project_desc=project_desc,
        error=error
    )


# ADD AI SUGGESTION AS TASK (assigned to selected member)
@app.route("/add-suggestion", methods=["POST"])
@login_required(role="lead")
def add_suggestion_lead():
    text = request.form.get("task_text", "").strip()
    assigned_to = request.form.get("assigned_to")

    if not text or not assigned_to:
        return redirect(url_for("ai_suggestions_lead"))

    user = current_user()
    conn = get_db()

    team = conn.execute(
        "SELECT * FROM teams WHERE lead_id=?",
        (user["id"],)
    ).fetchone()

    team_id = team["id"] if team else None
    created = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn.execute("""
        INSERT INTO tasks (task, assigned_to, priority, status, created_at, team_id)
        VALUES (?, ?, 'Medium', 'To-Do', ?, ?)
    """, (text, assigned_to, created, team_id))

    conn.commit()
    conn.close()

    return redirect(url_for("lead_dashboard"))



# AI Subtasks route (lead-only)
@app.route("/ai-subtasks/<int:task_id>")
@login_required(role="lead")
def ai_subtasks_lead(task_id):
    # same as earlier but only for lead
    conn = get_db()
    task = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    conn.close()
    if not task:
        flash("Task not found", "danger")
        return redirect(url_for("lead_dashboard"))

    suggestions = []
    error = None
    if GENAI and os.getenv("GEMINI_API_KEY"):
        try:
            genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
            model_name = os.getenv("GEMINI_MODEL", "models/gemini-2.5-flash")
            model = genai.GenerativeModel(model_name)
            prompt = f"""
You are an expert software engineer. Break the following task into a JSON object with key "subtasks" containing 5 detailed subtasks (each short and actionable). Return ONLY the JSON.

Task: {task['task']}

Exact format:
{{ "subtasks": ["subtask1", "subtask2", "subtask3", "subtask4", "subtask5"] }}
"""
            resp = model.generate_content(prompt)
            text = getattr(resp, "text", "") or str(resp)
            data = json.loads(text)
            if isinstance(data, dict) and "subtasks" in data and isinstance(data["subtasks"], list):
                suggestions = data["subtasks"]
        except Exception as e:
            error = f"AI error: {e}"
    if not suggestions:
        suggestions = [
            "Analyze requirements and acceptance criteria",
            "Create module-level design and diagrams",
            "Implement core logic and endpoints",
            "Write unit and integration tests",
            "Run manual tests and deploy to staging"
        ]
    return render_template("ai_subtasks.html", task=task, suggestions=suggestions, error=error)


# Explain task (both lead and member can view explanation)
@app.route("/explain/<int:task_id>")
def explain_task_shared(task_id):
    conn = get_db()
    task = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    conn.close()
    if not task:
        return "Task not found", 404
    explanation = ""
    error = None
    if GENAI and os.getenv("GEMINI_API_KEY"):
        try:
            genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
            model_name = os.getenv("GEMINI_MODEL", "models/gemini-2.5-flash")
            model = genai.GenerativeModel(model_name)
            prompt = f"Explain this task in 3 short sentences: {task['task']}"
            resp = model.generate_content(prompt)
            explanation = getattr(resp, "text", "") or str(resp)
        except Exception as e:
            error = f"AI error: {e}"
    if not explanation:
        explanation = f"Fallback: This task '{task['task']}' should be broken into subtasks and implemented based on priority."
    return render_template("task_explanation.html", task=task, explanation=explanation, error=error)


# update-status (lead can update statuses; members use member-mark-done route)
@app.route("/update-status/<int:task_id>/<string:new_status>")
@login_required(role="lead")
def update_status_lead(task_id, new_status):
    conn = get_db()
    conn.execute("UPDATE tasks SET status=? WHERE id=?", (new_status, task_id))
    conn.commit()
    conn.close()
    flash("Status updated", "success")
    return redirect(url_for("lead_dashboard"))


@app.route("/delete-task/<int:task_id>")
@login_required(role="lead")
def delete_task_lead(task_id):
    conn = get_db()
    conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))
    conn.commit()
    conn.close()
    flash("Task deleted", "success")
    return redirect(url_for("lead_dashboard"))


# Delay prediction route (shared)
@app.route("/delay-prediction")
def delay_prediction_shared():
    conn = get_db()
    tasks = conn.execute("SELECT * FROM tasks ORDER BY id DESC").fetchall()
    conn.close()
    predictions = []
    for t in tasks:
        if t["priority"] == "High" and t["status"] != "Done":
            pred = "High Delay Risk"
        elif t["status"] == "In Progress":
            pred = "Possibly Delayed"
        else:
            pred = "On Track"
        predictions.append({"task": t["task"], "assigned_to": t["assigned_to"], "priority": t["priority"], "status": t["status"], "prediction": pred})
    # For role-based view, the template can filter
    return render_template("delay_prediction.html", predictions=predictions)


# Export CSV (lead only)
@app.route("/export-csv")
@login_required(role="lead")
def export_csv_lead():
    user = current_user()
    conn = get_db()
    team = conn.execute("SELECT * FROM teams WHERE lead_id=?", (user["id"],)).fetchone()
    tasks = []
    if team:
        tasks = conn.execute("SELECT * FROM tasks WHERE team_id=? ORDER BY id DESC", (team["id"],)).fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Task", "Assigned", "Priority", "Status", "Created", "Subtasks"])
    for t in tasks:
        writer.writerow([t["id"], t["task"], t["assigned_to"], t["priority"], t["status"], t["created_at"], t["sub_tasks"]])
    mem = io.BytesIO(output.getvalue().encode())
    mem.seek(0)
    return send_file(mem, mimetype="text/csv", download_name="tasks.csv", as_attachment=True)
@app.route("/profile")
def profile():
    if "user_id" not in session:
        return redirect("/")

    role = session.get("role")
    team_id = session.get("team_id")

    conn = get_db()

    if role == "lead":
        team = conn.execute(
            "SELECT * FROM teams WHERE id=?",
            (team_id,)
        ).fetchone()

        members = conn.execute(
            "SELECT display_name, username FROM users WHERE team_id=? AND role='member'",
            (team_id,)
        ).fetchall()

        conn.close()
        return render_template(
            "profile_lead.html",
            team=team,
            members=members
        )

    else:
        user = conn.execute(
            "SELECT * FROM users WHERE id=?",
            (session["user_id"],)
        ).fetchone()

        conn.close()
        return render_template(
            "profile_member.html",
            user=user
        )
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")



# ---------------- Run App ----------------
if __name__ == "__main__":
    app.run(debug=True)
 