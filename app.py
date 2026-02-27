import csv
import os
import random
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from flask import Flask, Response, g, redirect, render_template, request, session, url_for


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "app.db"
SOURCE_CSV = BASE_DIR / "data" / "Sheets" / "500_goldenset_final_sheet.csv"


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    app.config["ADMIN_EMAIL"] = os.environ.get("ADMIN_EMAIL", "admin@local")
    app.config["ADMIN_PASSWORD"] = os.environ.get("ADMIN_PASSWORD", "admin123")

    def get_db() -> sqlite3.Connection:
        if "db" not in g:
            g.db = sqlite3.connect(DB_PATH)
            g.db.row_factory = sqlite3.Row
        return g.db

    @app.teardown_appcontext
    def close_db(_error):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    def init_db() -> None:
        db = get_db()
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                username TEXT,
                is_admin INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT,
                q_gu TEXT NOT NULL,
                q_en TEXT,
                search_results TEXT,
                a_en TEXT,
                a_gu TEXT,
                active INTEGER NOT NULL DEFAULT 1
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_questions_unique
            ON questions(category, q_gu, q_en);

            CREATE TABLE IF NOT EXISTS assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                question_id INTEGER NOT NULL,
                UNIQUE(user_id, question_id),
                FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(question_id) REFERENCES questions(id)
            );

            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                question_id INTEGER NOT NULL,
                submission_status TEXT NOT NULL DEFAULT 'submitted',
                q_translation_rating INTEGER,
                q_translation_comment TEXT,
                search_rating INTEGER,
                search_issue_type TEXT,
                search_comment TEXT,
                answer_accuracy_rating INTEGER,
                answer_translation_rating INTEGER,
                answer_comment TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(user_id, question_id),
                FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(question_id) REFERENCES questions(id)
            );

            CREATE TABLE IF NOT EXISTS suggested_questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                question_text_gu TEXT NOT NULL,
                question_text_en TEXT,
                status TEXT NOT NULL DEFAULT 'new',
                notes TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );
            """
        )
        migrate_db()
        db.commit()

    def migrate_db() -> None:
        db = get_db()
        feedback_columns = {
            row["name"] for row in db.execute("PRAGMA table_info(feedback)").fetchall()
        }
        if "submission_status" not in feedback_columns:
            db.execute(
                "ALTER TABLE feedback ADD COLUMN submission_status TEXT NOT NULL DEFAULT 'submitted'"
            )
            db.execute(
                "UPDATE feedback SET submission_status='submitted' WHERE submission_status IS NULL OR submission_status=''"
            )

    def parse_search_sections(raw_text: str):
        text = (raw_text or "").strip()
        if not text:
            return [{"title": "Search Context", "body": ""}]

        lines = text.splitlines()
        sections = []
        current = []
        current_title = "Search Context"

        def flush():
            nonlocal current, current_title
            body = "\n".join(current).strip()
            if body:
                sections.append({"title": current_title, "body": body})
            current = []

        for line in lines:
            stripped = line.strip()
            is_header = (
                stripped.lower().startswith("query")
                or stripped.lower().startswith("question")
                or stripped.lower().startswith("retrieved")
                or stripped.lower().startswith("response")
                or stripped.lower().startswith("result")
            ) and len(stripped) <= 120
            if is_header and not current and current_title == "Search Context":
                current_title = stripped[:120]
                continue
            if is_header and current:
                flush()
                current_title = stripped[:120]
                continue
            current.append(line)

        flush()
        if not sections:
            sections.append({"title": "Search Context", "body": text})
        return sections

    def get_pending_question_for_user(user_id: int) -> Optional[sqlite3.Row]:
        return get_db().execute(
            """
            SELECT q.*
            FROM assignments a
            JOIN questions q ON q.id = a.question_id
            LEFT JOIN feedback f
              ON f.user_id = a.user_id
             AND f.question_id = a.question_id
             AND f.submission_status = 'submitted'
            WHERE a.user_id = ? AND q.active = 1 AND f.id IS NULL
            ORDER BY q.id
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()

    def get_user_progress(user_id: int):
        row = get_db().execute(
            """
            SELECT
              COUNT(DISTINCT a.question_id) AS assigned,
              COUNT(DISTINCT f.question_id) AS completed
            FROM assignments a
            LEFT JOIN feedback f
              ON f.question_id = a.question_id
             AND f.user_id = a.user_id
             AND f.submission_status = 'submitted'
            WHERE a.user_id = ?
            """,
            (user_id,),
        ).fetchone()
        assigned = row["assigned"] or 0
        completed = row["completed"] or 0
        return {"assigned": assigned, "completed": completed, "remaining": max(assigned - completed, 0)}

    def get_feedback(user_id: int, question_id: int) -> Optional[sqlite3.Row]:
        return get_db().execute(
            """
            SELECT *
            FROM feedback
            WHERE user_id = ? AND question_id = ?
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (user_id, question_id),
        ).fetchone()

    def bootstrap_questions_if_empty() -> None:
        db = get_db()
        count = db.execute("SELECT COUNT(*) AS c FROM questions").fetchone()["c"]
        if count > 0 or not SOURCE_CSV.exists():
            return

        with SOURCE_CSV.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            rows = []
            for row in reader:
                rows.append(
                    (
                        (row.get("Category") or "").strip(),
                        (row.get("Q (Gu)") or "").strip(),
                        (row.get("Q (En)") or "").strip(),
                        row.get("Search Results") or "",
                        row.get("A(En)") or "",
                        row.get("A (Gu)") or "",
                    )
                )

        db.executemany(
            """
            INSERT OR IGNORE INTO questions
            (category, q_gu, q_en, search_results, a_en, a_gu)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        db.commit()

    def bootstrap_users_if_empty() -> None:
        # No default annotator seeding; users are expected from admin import or sync scripts.
        return

    def as_int(value: str, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def get_required_int(form_value: str) -> Optional[int]:
        try:
            return int(form_value)
        except (TypeError, ValueError):
            return None

    @app.before_request
    def ensure_bootstrapped():
        init_db()
        bootstrap_questions_if_empty()
        bootstrap_users_if_empty()

    def current_user():
        user_id = session.get("user_id")
        if not user_id:
            return None
        return get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

    def require_user():
        user = current_user()
        if not user:
            return redirect(url_for("annotator_login"))
        return user

    def require_admin():
        if not session.get("is_admin"):
            return None
        return {"email": session.get("admin_email")}

    @app.route("/")
    def home():
        if session.get("user_id"):
            return redirect(url_for("annotate"))
        return redirect(url_for("annotator_login"))

    @app.route("/annotator/login", methods=["GET", "POST"])
    def annotator_login():
        db = get_db()
        if request.method == "POST":
            email = (request.form.get("email") or "").strip().lower()
            user = db.execute("SELECT * FROM users WHERE lower(email) = ?", (email,)).fetchone()
            if user:
                session["user_id"] = user["id"]
                return redirect(url_for("annotate"))
            return render_template(
                "annotator_login.html",
                users=db.execute("SELECT email FROM users ORDER BY email").fetchall(),
                error="Selected email was not found.",
            )

        users = db.execute("SELECT email FROM users ORDER BY email").fetchall()
        return render_template("annotator_login.html", users=users)

    @app.route("/annotator/logout")
    def annotator_logout():
        session.pop("user_id", None)
        return redirect(url_for("annotator_login"))

    @app.route("/annotate")
    def annotate():
        user = require_user()
        if not isinstance(user, sqlite3.Row):
            return user
        question = get_pending_question_for_user(user["id"])
        progress = get_user_progress(user["id"])

        if not question:
            return render_template("annotate_done.html", user=user, progress=progress)

        existing = get_feedback(user["id"], question["id"])
        form_data = {}
        if existing:
            for key in [
                "q_translation_rating",
                "q_translation_comment",
                "search_comment",
                "answer_accuracy_rating",
                "answer_translation_rating",
                "answer_comment",
            ]:
                value = existing[key]
                form_data[key] = "" if value is None else str(value)

        return render_template(
            "annotate.html",
            user=user,
            question=question,
            progress=progress,
            search_sections=parse_search_sections(question["search_results"]),
            form_data=form_data,
            error=None,
            notice=request.args.get("notice"),
        )

    @app.route("/annotate/save", methods=["POST"])
    def annotate_save():
        user = require_user()
        if not isinstance(user, sqlite3.Row):
            return user
        db = get_db()

        question_id = get_required_int(request.form.get("question_id"))
        if question_id is None:
            return redirect(url_for("annotate"))
        question = db.execute("SELECT * FROM questions WHERE id = ? AND active = 1", (question_id,)).fetchone()
        assigned = db.execute(
            "SELECT 1 FROM assignments WHERE user_id = ? AND question_id = ?",
            (user["id"], question_id),
        ).fetchone()
        if not question or not assigned:
            return redirect(url_for("annotate"))

        form_data = {
            "q_translation_rating": (request.form.get("q_translation_rating") or "").strip(),
            "q_translation_comment": (request.form.get("q_translation_comment") or "").strip(),
            "search_comment": (request.form.get("search_comment") or "").strip(),
            "answer_accuracy_rating": (request.form.get("answer_accuracy_rating") or "").strip(),
            "answer_translation_rating": (request.form.get("answer_translation_rating") or "").strip(),
            "answer_comment": (request.form.get("answer_comment") or "").strip(),
        }
        save_action = (request.form.get("save_action") or "submitted").strip()
        if save_action not in {"draft", "submitted"}:
            save_action = "submitted"

        if save_action == "submitted":
            required_rating_fields = [
                "q_translation_rating",
                "answer_accuracy_rating",
                "answer_translation_rating",
            ]
            for field in required_rating_fields:
                if form_data[field] not in {"1", "2", "3", "4", "5"}:
                    return render_template(
                        "annotate.html",
                        user=user,
                        question=question,
                        progress=get_user_progress(user["id"]),
                        search_sections=parse_search_sections(question["search_results"]),
                        form_data=form_data,
                        error="All ratings are required and must be between 1 and 5 before submit.",
                        notice=None,
                    )

        if save_action == "submitted":
            if int(form_data["q_translation_rating"]) <= 2 and not form_data["q_translation_comment"]:
                return render_template(
                    "annotate.html",
                    user=user,
                    question=question,
                    progress=get_user_progress(user["id"]),
                    search_sections=parse_search_sections(question["search_results"]),
                    form_data=form_data,
                    error="Add a question translation comment when rating is 1 or 2.",
                    notice=None,
                )
            if (
                int(form_data["answer_accuracy_rating"]) <= 2
                or int(form_data["answer_translation_rating"]) <= 2
            ) and not form_data["answer_comment"]:
                return render_template(
                    "annotate.html",
                    user=user,
                    question=question,
                    progress=get_user_progress(user["id"]),
                    search_sections=parse_search_sections(question["search_results"]),
                    form_data=form_data,
                    error="Add an answer comment when answer accuracy/translation rating is 1 or 2.",
                    notice=None,
                )

        now = datetime.utcnow().isoformat()
        def rating_or_none(value: str):
            return int(value) if value in {"1", "2", "3", "4", "5"} else None

        params = (
            user["id"],
            question_id,
            save_action,
            rating_or_none(form_data["q_translation_rating"]),
            form_data["q_translation_comment"],
            None,
            None,
            form_data["search_comment"],
            rating_or_none(form_data["answer_accuracy_rating"]),
            rating_or_none(form_data["answer_translation_rating"]),
            form_data["answer_comment"],
            now,
            now,
        )

        db.execute(
            """
            INSERT INTO feedback (
                user_id, question_id,
                submission_status,
                q_translation_rating, q_translation_comment,
                search_rating, search_issue_type, search_comment,
                answer_accuracy_rating, answer_translation_rating, answer_comment,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, question_id) DO UPDATE SET
                submission_status=excluded.submission_status,
                q_translation_rating=excluded.q_translation_rating,
                q_translation_comment=excluded.q_translation_comment,
                search_rating=excluded.search_rating,
                search_issue_type=excluded.search_issue_type,
                search_comment=excluded.search_comment,
                answer_accuracy_rating=excluded.answer_accuracy_rating,
                answer_translation_rating=excluded.answer_translation_rating,
                answer_comment=excluded.answer_comment,
                updated_at=excluded.updated_at
            """,
            params,
        )
        db.commit()
        if save_action == "draft":
            return render_template(
                "annotate.html",
                user=user,
                question=question,
                progress=get_user_progress(user["id"]),
                search_sections=parse_search_sections(question["search_results"]),
                form_data=form_data,
                error=None,
                notice="Draft saved. This question remains pending until you submit.",
            )
        return redirect(url_for("annotate", notice="Submitted and moved to next pending question."))

    @app.route("/questions", methods=["GET", "POST"])
    def all_questions():
        user = require_user()
        if not isinstance(user, sqlite3.Row):
            return user
        db = get_db()

        if request.method == "POST":
            gu = (request.form.get("question_text_gu") or "").strip()
            en = (request.form.get("question_text_en") or "").strip()
            if gu:
                db.execute(
                    """
                    INSERT INTO suggested_questions
                    (user_id, question_text_gu, question_text_en, status, created_at)
                    VALUES (?, ?, ?, 'new', ?)
                    """,
                    (user["id"], gu, en, datetime.utcnow().isoformat()),
                )
                db.commit()

        questions = db.execute(
            "SELECT id, category, q_gu FROM questions WHERE active = 1 ORDER BY id"
        ).fetchall()
        return render_template("all_questions.html", user=user, questions=questions)

    @app.route("/admin/login", methods=["GET", "POST"])
    def admin_login():
        if request.method == "POST":
            email = (request.form.get("email") or "").strip().lower()
            password = request.form.get("password") or ""
            if email == app.config["ADMIN_EMAIL"].lower() and password == app.config["ADMIN_PASSWORD"]:
                session["is_admin"] = True
                session["admin_email"] = email
                return redirect(url_for("admin_users"))
            return render_template("admin_login.html", error="Invalid admin credentials.")
        return render_template("admin_login.html")

    @app.route("/admin/logout")
    def admin_logout():
        session.pop("is_admin", None)
        session.pop("admin_email", None)
        return redirect(url_for("admin_login"))

    @app.route("/admin/users", methods=["GET", "POST"])
    def admin_users():
        admin = require_admin()
        if not admin:
            return redirect(url_for("admin_login"))

        db = get_db()
        if request.method == "POST":
            action = request.form.get("action") or "single"
            if action == "single":
                email = (request.form.get("email") or "").strip().lower()
                username = (request.form.get("username") or "").strip() or None
                if email:
                    db.execute(
                        "INSERT OR IGNORE INTO users (email, username, is_admin) VALUES (?, ?, 0)",
                        (email, username),
                    )
                    db.commit()
            elif action == "bulk":
                bulk_emails = request.form.get("bulk_emails") or ""
                raw = bulk_emails.replace(",", "\n").replace(";", "\n").splitlines()
                emails = sorted({x.strip().lower() for x in raw if x.strip()})
                for email in emails:
                    db.execute(
                        "INSERT OR IGNORE INTO users (email, is_admin) VALUES (?, 0)",
                        (email,),
                    )
                db.commit()

        users = db.execute("SELECT * FROM users ORDER BY email").fetchall()
        return render_template("admin_users.html", users=users, admin=admin)

    @app.route("/admin/assignments", methods=["GET", "POST"])
    def admin_assignments():
        admin = require_admin()
        if not admin:
            return redirect(url_for("admin_login"))

        db = get_db()
        action = request.form.get("action")
        if request.method == "POST":
            if action == "manual":
                user_id = get_required_int(request.form.get("user_id"))
                question_id = get_required_int(request.form.get("question_id"))
                if user_id is None or question_id is None:
                    return redirect(url_for("admin_assignments"))
                db.execute(
                    "INSERT OR IGNORE INTO assignments (user_id, question_id) VALUES (?, ?)",
                    (user_id, question_id),
                )
                db.commit()
            elif action == "random":
                user_ids = [
                    parsed for parsed in (get_required_int(v) for v in request.form.getlist("user_ids"))
                    if parsed is not None
                ]
                assign_mode = request.form.get("assign_mode") or "count"
                count_per_user = as_int(request.form.get("count_per_user"), 0)
                if user_ids and (assign_mode == "all" or count_per_user > 0):
                    unassigned = db.execute(
                        """
                        SELECT q.id
                        FROM questions q
                        LEFT JOIN assignments a ON a.question_id = q.id
                        WHERE q.active = 1 AND a.id IS NULL
                        """
                    ).fetchall()
                    pool = [r["id"] for r in unassigned]
                    random.shuffle(pool)
                    if assign_mode == "all":
                        idx = 0
                        for qid in pool:
                            uid = user_ids[idx % len(user_ids)]
                            db.execute(
                                "INSERT OR IGNORE INTO assignments (user_id, question_id) VALUES (?, ?)",
                                (uid, qid),
                            )
                            idx += 1
                    else:
                        for uid in user_ids:
                            selected = pool[:count_per_user]
                            pool = pool[count_per_user:]
                            for qid in selected:
                                db.execute(
                                    "INSERT OR IGNORE INTO assignments (user_id, question_id) VALUES (?, ?)",
                                    (uid, qid),
                                )
                    db.commit()

        status_filter = (request.args.get("status") or "all").strip()
        if status_filter not in {"all", "unassigned", "partial", "full"}:
            status_filter = "all"
        user_filter = (request.args.get("user_id") or "").strip()
        category_filter = (request.args.get("category") or "").strip()
        query_filter = (request.args.get("q") or "").strip()
        page = max(as_int(request.args.get("page"), 1), 1)
        page_size = max(min(as_int(request.args.get("page_size"), 50), 200), 10)

        where_clauses = ["q.active = 1"]
        params = []
        if category_filter:
            where_clauses.append("q.category = ?")
            params.append(category_filter)
        if query_filter:
            where_clauses.append("(q.q_gu LIKE ? OR q.q_en LIKE ?)")
            like = f"%{query_filter}%"
            params.extend([like, like])
        if user_filter:
            where_clauses.append("EXISTS (SELECT 1 FROM assignments a2 WHERE a2.question_id = q.id AND a2.user_id = ?)")
            params.append(as_int(user_filter, 0))

        status_having = ""
        if status_filter == "unassigned":
            status_having = "HAVING assigned_count = 0"
        elif status_filter == "partial":
            status_having = "HAVING assigned_count > 0 AND completed_count < assigned_count"
        elif status_filter == "full":
            status_having = "HAVING assigned_count > 0 AND completed_count >= assigned_count"

        base_summary_sql = f"""
            SELECT
              q.id AS question_id,
              q.category,
              q.q_gu,
              COUNT(DISTINCT a.user_id) AS assigned_count,
              COUNT(DISTINCT CASE WHEN f.user_id IS NOT NULL THEN f.user_id END) AS completed_count
            FROM questions q
            LEFT JOIN assignments a ON a.question_id = q.id
            LEFT JOIN feedback f
              ON f.question_id = q.id
             AND f.user_id = a.user_id
             AND f.submission_status = 'submitted'
            WHERE {' AND '.join(where_clauses)}
            GROUP BY q.id
            {status_having}
        """

        total_items = db.execute(
            f"SELECT COUNT(*) AS c FROM ({base_summary_sql}) t",
            params,
        ).fetchone()["c"]
        total_pages = max((total_items + page_size - 1) // page_size, 1)
        if page > total_pages:
            page = total_pages

        users = db.execute("SELECT id, email FROM users ORDER BY email").fetchall()
        questions = db.execute(
            "SELECT id, q_gu, category FROM questions WHERE active = 1 ORDER BY id LIMIT 1000"
        ).fetchall()
        categories = db.execute(
            "SELECT DISTINCT category FROM questions WHERE category IS NOT NULL AND category != '' ORDER BY category"
        ).fetchall()
        summary = db.execute(
            f"""
            {base_summary_sql}
            ORDER BY question_id
            LIMIT ? OFFSET ?
            """,
            (*params, page_size, (page - 1) * page_size),
        ).fetchall()
        metrics = db.execute(
            """
            SELECT
              COUNT(*) AS total_questions,
              SUM(CASE WHEN assigned_count = 0 THEN 1 ELSE 0 END) AS unassigned,
              SUM(CASE WHEN assigned_count > 0 AND completed_count < assigned_count THEN 1 ELSE 0 END) AS partial,
              SUM(CASE WHEN assigned_count > 0 AND completed_count >= assigned_count THEN 1 ELSE 0 END) AS full
            FROM (
              SELECT
                q.id,
                COUNT(DISTINCT a.user_id) AS assigned_count,
                COUNT(DISTINCT CASE WHEN f.user_id IS NOT NULL THEN f.user_id END) AS completed_count
              FROM questions q
              LEFT JOIN assignments a ON a.question_id = q.id
              LEFT JOIN feedback f
                ON f.question_id = q.id
               AND f.user_id = a.user_id
               AND f.submission_status = 'submitted'
              WHERE q.active = 1
              GROUP BY q.id
            ) t
            """
        ).fetchone()
        user_progress = db.execute(
            """
            SELECT
              u.id,
              u.email,
              COUNT(DISTINCT a.question_id) AS assigned,
              COUNT(DISTINCT CASE WHEN f.submission_status = 'submitted' THEN f.question_id END) AS completed,
              COUNT(DISTINCT CASE WHEN f.submission_status = 'draft' THEN f.question_id END) AS drafts
            FROM users u
            LEFT JOIN assignments a ON a.user_id = u.id
            LEFT JOIN feedback f ON f.user_id = u.id AND f.question_id = a.question_id
            GROUP BY u.id
            ORDER BY u.email
            """
        ).fetchall()

        return render_template(
            "admin_assignments.html",
            admin=admin,
            users=users,
            questions=questions,
            categories=categories,
            summary=summary,
            metrics=metrics,
            user_progress=user_progress,
            filters={
                "status": status_filter,
                "user_id": user_filter,
                "category": category_filter,
                "q": query_filter,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
                "total_items": total_items,
            },
        )

    @app.route("/admin/data", methods=["GET", "POST"])
    def admin_data():
        admin = require_admin()
        if not admin:
            return redirect(url_for("admin_login"))

        db = get_db()
        if request.method == "POST":
            file = request.files.get("questions_csv")
            if file:
                content = file.stream.read().decode("utf-8-sig").splitlines()
                reader = csv.DictReader(content)
                import_mode = (request.form.get("import_mode") or "upsert").strip()
                if import_mode not in {"insert", "upsert", "sync"}:
                    import_mode = "upsert"
                replace_assignments = request.form.get("replace_assignments") == "on"
                seen_question_ids = set()

                def find_col(row, names):
                    for name in names:
                        if name in row:
                            return row.get(name) or ""
                    return ""

                def get_or_create_user_id(email: str) -> Optional[int]:
                    email = (email or "").strip().lower()
                    if not email:
                        return None
                    user = db.execute("SELECT id FROM users WHERE lower(email)=?", (email,)).fetchone()
                    if not user:
                        db.execute("INSERT OR IGNORE INTO users (email, is_admin) VALUES (?, 0)", (email,))
                        user = db.execute("SELECT id FROM users WHERE lower(email)=?", (email,)).fetchone()
                    return user["id"] if user else None

                def apply_assignments(question_id: int, email_blob: str) -> None:
                    raw = (email_blob or "").replace(";", ",").replace("|", ",").split(",")
                    emails = sorted({x.strip().lower() for x in raw if x.strip()})
                    if replace_assignments:
                        db.execute("DELETE FROM assignments WHERE question_id = ?", (question_id,))
                    for email in emails:
                        user_id = get_or_create_user_id(email)
                        if user_id:
                            db.execute(
                                "INSERT OR IGNORE INTO assignments (user_id, question_id) VALUES (?, ?)",
                                (user_id, question_id),
                            )

                def upsert_question(row: dict) -> Optional[int]:
                    category = (row.get("Category") or "").strip()
                    q_gu = (row.get("Q (Gu)") or "").strip()
                    q_en = (row.get("Q (En)") or "").strip()
                    search_results = row.get("Search Results") or ""
                    a_en = row.get("A(En)") or ""
                    a_gu = row.get("A (Gu)") or ""
                    if not q_gu:
                        return None

                    qid_raw = (find_col(row, ["id", "ID", "question_id", "Question ID"]) or "").strip()
                    qid = as_int(qid_raw, 0) if qid_raw else 0

                    if import_mode == "insert":
                        db.execute(
                            """
                            INSERT OR IGNORE INTO questions
                            (category, q_gu, q_en, search_results, a_en, a_gu, active)
                            VALUES (?, ?, ?, ?, ?, ?, 1)
                            """,
                            (category, q_gu, q_en, search_results, a_en, a_gu),
                        )
                        found = db.execute(
                            "SELECT id FROM questions WHERE category=? AND q_gu=? AND q_en=?",
                            (category, q_gu, q_en),
                        ).fetchone()
                        return found["id"] if found else None

                    if qid:
                        existing = db.execute("SELECT id FROM questions WHERE id=?", (qid,)).fetchone()
                        if existing:
                            db.execute(
                                """
                                UPDATE questions
                                SET category=?, q_gu=?, q_en=?, search_results=?, a_en=?, a_gu=?, active=1
                                WHERE id=?
                                """,
                                (category, q_gu, q_en, search_results, a_en, a_gu, qid),
                            )
                            return qid

                    db.execute(
                        """
                        INSERT INTO questions (category, q_gu, q_en, search_results, a_en, a_gu, active)
                        VALUES (?, ?, ?, ?, ?, ?, 1)
                        ON CONFLICT(category, q_gu, q_en) DO UPDATE SET
                          search_results=excluded.search_results,
                          a_en=excluded.a_en,
                          a_gu=excluded.a_gu,
                          active=1
                        """,
                        (category, q_gu, q_en, search_results, a_en, a_gu),
                    )
                    found = db.execute(
                        "SELECT id FROM questions WHERE category=? AND q_gu=? AND q_en=?",
                        (category, q_gu, q_en),
                    ).fetchone()
                    return found["id"] if found else None

                for row in reader:
                    question_id = upsert_question(row)
                    if not question_id:
                        continue
                    seen_question_ids.add(question_id)
                    assignees = find_col(
                        row,
                        [
                            "assigned_emails",
                            "Assigned Emails",
                            "Members",
                            "members",
                            "Assignees",
                            "assignees",
                            "Assigned To",
                            "assigned_to",
                        ],
                    )
                    if assignees:
                        apply_assignments(question_id, assignees)

                if import_mode == "sync":
                    if seen_question_ids:
                        placeholders = ",".join("?" for _ in seen_question_ids)
                        db.execute(
                            f"UPDATE questions SET active=0 WHERE id NOT IN ({placeholders})",
                            tuple(seen_question_ids),
                        )
                    else:
                        db.execute("UPDATE questions SET active=0")
                db.commit()

        suggestions = db.execute(
            """
            SELECT s.*, u.email
            FROM suggested_questions s
            JOIN users u ON u.id = s.user_id
            ORDER BY s.id DESC
            LIMIT 200
            """
        ).fetchall()
        return render_template("admin_data.html", admin=admin, suggestions=suggestions)

    @app.route("/admin/export/questions.csv")
    def export_questions():
        admin = require_admin()
        if not admin:
            return redirect(url_for("admin_login"))
        db = get_db()
        rows = db.execute(
            """
            SELECT category AS "Category",
                   q_gu AS "Q (Gu)",
                   q_en AS "Q (En)",
                   search_results AS "Search Results",
                   a_en AS "A(En)",
                   a_gu AS "A (Gu)"
            FROM questions
            ORDER BY id
            """
        ).fetchall()
        return to_csv_response("questions_export.csv", rows)

    @app.route("/admin/export/feedback.csv")
    def export_feedback():
        admin = require_admin()
        if not admin:
            return redirect(url_for("admin_login"))
        db = get_db()
        rows = db.execute(
            """
            SELECT
              u.email AS user_email,
              q.id AS question_id,
              q.q_gu AS "Q (Gu)",
              q.q_en AS "Q (En)",
              f.submission_status,
              f.q_translation_rating,
              f.q_translation_comment,
              f.search_rating,
              f.search_issue_type,
              f.search_comment,
              f.answer_accuracy_rating,
              f.answer_translation_rating,
              f.answer_comment,
              f.created_at,
              f.updated_at
            FROM feedback f
            JOIN users u ON u.id = f.user_id
            JOIN questions q ON q.id = f.question_id
            ORDER BY f.updated_at DESC
            """
        ).fetchall()
        return to_csv_response("feedback_export.csv", rows)

    def to_csv_response(filename: str, rows) -> Response:
        output = []
        if rows:
            header = rows[0].keys()
        else:
            header = []
        output.append(",".join(header))
        for r in rows:
            values = []
            for key in header:
                v = r[key]
                if v is None:
                    v = ""
                text = str(v).replace('"', '""')
                values.append(f'"{text}"')
            output.append(",".join(values))
        body = "\n".join(output)
        return Response(
            body,
            headers={"Content-Disposition": f"attachment; filename={filename}"},
            mimetype="text/csv",
        )

    return app


app = create_app()


if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    port = int(os.environ.get("PORT", "5001"))
    app.run(host="0.0.0.0", debug=debug, port=port)
