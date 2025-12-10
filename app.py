from flask import Flask, render_template, request, redirect, url_for, send_file
import sqlite3
import json
import csv
import io
import os
from datetime import datetime
from dotenv import load_dotenv


try:
    import google.generativeai as genai
    GENAI = True
except:
    GENAI = False

load_dotenv()

app = Flask(__name__)
app.secret_key = "task_manager_secret"
DB_PATH = "inter_team_task.db"


#Database Initialization
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task TEXT,
            assigned_to TEXT,
            priority TEXT,
            status TEXT,
            created_at TEXT,
            sub_tasks TEXT,
            explanation TEXT
        );
    """)
    conn.commit()
    conn.close()


if not os.path.exists(DB_PATH):
    init_db()


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------
# DASHBOARD
# ---------------------------------------------------
@app.route("/")
def home():
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    todo = conn.execute("SELECT COUNT(*) FROM tasks WHERE status='To-Do'").fetchone()[0]
    inprog = conn.execute("SELECT COUNT(*) FROM tasks WHERE status='In Progress'").fetchone()[0]
    done = conn.execute("SELECT COUNT(*) FROM tasks WHERE status='Done'").fetchone()[0]
    conn.close()

    return render_template("dashboard.html",
                           total=total, todo=todo, inprog=inprog, done=done)


# ---------------------------------------------------
# TASK LIST
# ---------------------------------------------------
@app.route("/task-list")
def task_list():
    conn = get_db()
    tasks = conn.execute("SELECT * FROM tasks ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("task_list.html", tasks=tasks)


# ---------------------------------------------------
# ADD TASK
# ---------------------------------------------------
@app.route("/add-task", methods=["GET", "POST"])
def add_task():
    if request.method == "POST":
        task = request.form["task"]
        assigned = request.form["assigned_to"]
        priority = request.form["priority"]
        status = request.form["status"]
        created = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn = get_db()
        conn.execute("""
            INSERT INTO tasks (task, assigned_to, priority, status, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (task, assigned, priority, status, created))
        conn.commit()
        conn.close()

        return redirect(url_for("task_list"))

    return render_template("add_task.html")


# ---------------------------------------------------
# VIEW TASK (With Subtasks)
# ---------------------------------------------------
@app.route("/task/<int:task_id>")
def view_task(task_id):
    conn = get_db()
    task = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    conn.close()

    if not task:
        return "Task Not Found", 404

    subtasks = []
    if task["sub_tasks"]:
        try:
            subtasks = json.loads(task["sub_tasks"])
        except:
            subtasks = []

    return render_template("view_task.html", task=task, subtasks=subtasks)


# ---------------------------------------------------
# ADD SUBTASK
# ---------------------------------------------------
@app.route("/add-subtask/<int:task_id>", methods=["POST"])
def add_subtask(task_id):
    new_subtask = request.form["subtask"]

    conn = get_db()
    task = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()

    subtasks = []
    if task["sub_tasks"]:
        try:
            subtasks = json.loads(task["sub_tasks"])
        except:
            subtasks = []

    subtasks.append(new_subtask)

    conn.execute(
        "UPDATE tasks SET sub_tasks=? WHERE id=?",
        (json.dumps(subtasks), task_id)
    )
    conn.commit()
    conn.close()

    return redirect(url_for("view_task", task_id=task_id))


# ---------------------------------------------------
# UPDATE STATUS (Fixes Play + Tick Buttons)
# ---------------------------------------------------
@app.route("/update-status/<int:task_id>/<string:new_status>")
def update_status(task_id, new_status):
    conn = get_db()
    conn.execute("UPDATE tasks SET status=? WHERE id=?", (new_status, task_id))
    conn.commit()
    conn.close()
    return redirect(url_for("task_list"))


# ---------------------------------------------------
# DELETE TASK
# ---------------------------------------------------
@app.route("/delete-task/<int:task_id>")
def delete_task(task_id):
    conn = get_db()
    conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("task_list"))


# ---------------------------------------------------
# EXPLAIN TASK (AI or fallback)
# ---------------------------------------------------
@app.route("/explain/<int:task_id>")
def explain_task(task_id):
    conn = get_db()
    task = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    conn.close()

    if not task:
        return "Task not found.", 404

    explanation = ""

    if GENAI and os.getenv("GEMINI_API_KEY"):
        try:
            genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
            model = genai.GenerativeModel("models/gemini-2.5-flash")

            prompt = f"""
            Explain this task in simple terms in 3–5 sentences:

            Task: {task['task']}
            Priority: {task['priority']}
            Status: {task['status']}
            Subtasks: {task['sub_tasks']}
            """

            resp = model.generate_content(prompt)
            explanation = resp.text.strip()

        except:
            explanation = ""

    if not explanation:
        explanation = f"The task '{task['task']}' should be completed based on its priority. Break into subtasks and finish step-by-step."

    return render_template("task_explanation.html", task=task, explanation=explanation)


# ---------------------------------------------------
# EXPORT CSV
# ---------------------------------------------------
@app.route("/export-csv")
def export_csv():
    conn = get_db()
    tasks = conn.execute("SELECT * FROM tasks").fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Task", "Assigned", "Priority", "Status", "Created", "Subtasks"])

    for t in tasks:
        writer.writerow([
            t["id"], t["task"], t["assigned_to"], t["priority"],
            t["status"], t["created_at"], t["sub_tasks"]
        ])

    mem = io.BytesIO(output.getvalue().encode())
    mem.seek(0)

    return send_file(mem,
                     mimetype="text/csv",
                     download_name="tasks.csv",
                     as_attachment=True)


# ---------------------------------------------------
# DELAY PREDICTION
# ---------------------------------------------------
@app.route("/delay-prediction")
def delay_prediction():
    conn = get_db()
    tasks = conn.execute("SELECT * FROM tasks").fetchall()
    conn.close()

    predictions = []

    for t in tasks:
        if t["priority"] == "High" and t["status"] != "Done":
            pred = "High Delay Risk"
        elif t["status"] == "In Progress":
            pred = "Possibly Delayed"
        else:
            pred = "On Track"

        predictions.append({
            "task": t["task"],
            "assigned_to": t["assigned_to"],
            "priority": t["priority"],
            "status": t["status"],
            "prediction": pred
        })

    return render_template("delay_prediction.html", predictions=predictions)


# ---------------------------------------------------
# RUN APP
# ---------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)
