from functools import wraps

from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from models import Task, User, db

app = Flask(__name__)
app.secret_key = "task-manager-secret-key-change-in-production"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///tasks.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

PRIORITIES = {"low", "medium", "high"}
STATUSES = {"pending", "in_progress", "completed"}


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped


def api_login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": "Login required."}), 401
        return view(*args, **kwargs)

    return wrapped


def task_to_dict(task):
    return {
        "id": task.id,
        "title": task.title,
        "description": task.description or "",
        "priority": task.priority,
        "status": task.status,
        "due_date": task.due_date,
        "user_id": task.user_id,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
    }


def validate_task(data, partial=False):
    errors = []
    if not partial or "title" in data:
        title = (data.get("title") or "").strip()
        if not title:
            errors.append("Title is required.")
    if "priority" in data and data["priority"] not in PRIORITIES:
        errors.append("Priority must be low, medium, or high.")
    if "status" in data and data["status"] not in STATUSES:
        errors.append("Status must be pending, in_progress, or completed.")
    return errors


def get_task_for_user(task_id, user_id):
    return Task.query.filter_by(id=task_id, user_id=user_id).first()


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("index"))

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""

        if not username or not password:
            flash("Username and password are required.", "error")
            return render_template("login.html")

        user = User.query.filter_by(username=username).first()

        if not user or not check_password_hash(user.password, password):
            flash("Invalid username or password.", "error")
            return render_template("login.html")

        session["user_id"] = user.id
        session["username"] = user.username
        return redirect(url_for("index"))

    return render_template("login.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if "user_id" in session:
        return redirect(url_for("index"))

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""

        if not username or not password:
            flash("Username and password are required.", "error")
            return render_template("signup.html")

        if len(username) < 3:
            flash("Username must be at least 3 characters.", "error")
            return render_template("signup.html")

        if len(password) < 4:
            flash("Password must be at least 4 characters.", "error")
            return render_template("signup.html")

        if User.query.filter_by(username=username).first():
            flash("Username already exists.", "error")
            return render_template("signup.html")

        user = User(
            username=username,
            password=generate_password_hash(password),
        )
        db.session.add(user)
        db.session.commit()

        session["user_id"] = user.id
        session["username"] = user.username
        return redirect(url_for("index"))

    return render_template("signup.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    tasks = (
        Task.query.filter_by(user_id=session["user_id"])
        .order_by(Task.created_at.desc())
        .all()
    )
    return render_template("index.html", username=session.get("username"), tasks=tasks)


@app.route("/api/tasks", methods=["GET"])
@api_login_required
def list_tasks():
    user_id = session["user_id"]
    status = request.args.get("status")
    priority = request.args.get("priority")
    search = request.args.get("search", "").strip()

    query = Task.query.filter_by(user_id=user_id)

    if status:
        query = query.filter_by(status=status)
    if priority:
        query = query.filter_by(priority=priority)
    if search:
        like = f"%{search}%"
        query = query.filter(
            db.or_(Task.title.ilike(like), Task.description.ilike(like))
        )

    tasks = query.order_by(Task.created_at.desc()).all()
    return jsonify([task_to_dict(t) for t in tasks])


@app.route("/api/tasks/<int:task_id>", methods=["GET"])
@api_login_required
def get_task(task_id):
    task = get_task_for_user(task_id, session["user_id"])
    if not task:
        return jsonify({"error": "Task not found."}), 404
    return jsonify(task_to_dict(task))


@app.route("/api/tasks", methods=["POST"])
@api_login_required
def create_task():
    data = request.get_json(silent=True) or {}
    errors = validate_task(data)
    if errors:
        return jsonify({"errors": errors}), 400

    task = Task(
        title=data["title"].strip(),
        description=(data.get("description") or "").strip(),
        priority=data.get("priority", "medium"),
        status=data.get("status", "pending"),
        due_date=data.get("due_date") or None,
        user_id=session["user_id"],
    )
    db.session.add(task)
    db.session.commit()

    return jsonify(task_to_dict(task)), 201


@app.route("/api/tasks/<int:task_id>", methods=["PUT"])
@api_login_required
def update_task(task_id):
    task = get_task_for_user(task_id, session["user_id"])
    if not task:
        return jsonify({"error": "Task not found."}), 404

    data = request.get_json(silent=True) or {}
    errors = validate_task(data, partial=True)
    if errors:
        return jsonify({"errors": errors}), 400

    for key in ("title", "description", "priority", "status", "due_date"):
        if key in data:
            value = data[key]
            if key == "title":
                value = (value or "").strip()
            elif key == "description":
                value = (value or "").strip()
            elif key == "due_date":
                value = value or None
            setattr(task, key, value)

    db.session.commit()
    return jsonify(task_to_dict(task))


@app.route("/api/tasks/<int:task_id>", methods=["DELETE"])
@api_login_required
def delete_task(task_id):
    task = get_task_for_user(task_id, session["user_id"])
    if not task:
        return jsonify({"error": "Task not found."}), 404

    db.session.delete(task)
    db.session.commit()
    return "", 204


@app.route("/api/stats", methods=["GET"])
@api_login_required
def stats():
    user_id = session["user_id"]
    counts = {status: 0 for status in STATUSES}

    rows = (
        db.session.query(Task.status, db.func.count(Task.id))
        .filter_by(user_id=user_id)
        .group_by(Task.status)
        .all()
    )
    for status, count in rows:
        counts[status] = count

    return jsonify(counts)


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5000)
