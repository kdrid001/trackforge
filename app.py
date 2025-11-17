from __future__ import annotations
from datetime import date, datetime
from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

# --- Database configuration ---
# Use a SQLite file in the project root. SQLAlchemy needs an absolute path on Windows too,
# so we resolve it with Path().resolve().
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + str(Path('trackforge.db').resolve())
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'dev'  # ok for local dev

db = SQLAlchemy(app)

# --- Data model ---
class Task(db.Model):
    """A single learning task item.

    Fields
    ------
    title: short label shown in lists
    source: where to study (e.g., "Grokking ch4" or a URL)
    tags: semicolon-separated taxonomy (e.g., "DSA;Python")
    estimate_pomos: planned effort (1–8 pomodoros)
    actual_pomos: incremented by timer later
    due_date: calendar date we plan to do it
    status: lifecycle flag: scheduled | today | done
    created_at/completed_at: bookkeeping for review stats
    """
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    source = db.Column(db.String(255))
    tags = db.Column(db.String(255), default='')  # semicolon-separated
    estimate_pomos = db.Column(db.Integer, default=1)
    actual_pomos = db.Column(db.Integer, default=0)
    due_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default='scheduled')  # scheduled | today | done
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.Date)

    def tag_list(self) -> list[str]:
        """Helper for templates: split the semicolon string into a list."""
        return [t for t in (self.tags or '').split(';') if t]

# Create tables on first run. Needs an application context so SQLAlchemy
# knows which app the metadata belongs to.
with app.app_context():
    db.create_all()

# ------------------------------
# Routes (URL -> view functions)
# ------------------------------

@app.get('/')
def today_view():
    """Homepage: show up to 3 tasks due today (or overdue), prioritizing ones
    already marked as "today". The 3-item cap is a WIP limit to encourage focus."""
    today = date.today()
    items = (
        Task.query
            # Pull in anything that is due today or earlier
            .filter(Task.due_date <= today)
            # and that is either explicitly "today" or still "scheduled"
            .filter(Task.status.in_(['today', 'scheduled']))
            # Order so that "today" items come before "scheduled" ones
            .order_by(Task.status.desc(), Task.id.desc())
            # Don't overwhelm the day; keep it to 3 visible tasks
            .limit(3)
            .all()
    )
    return render_template('today.html', today=today, items=items)

@app.post('/add')
def add_task():
    """Create a new task from the form submission.
    Notes
    -----
    - Missing/blank fields are normalized (title default, pomos clamped).
    - If the selected due date is today, status becomes "today"; otherwise "scheduled".
    - We redirect (PRG pattern) so reloading the page won't resubmit the form.
    """
    title = request.form.get('title', '').strip() or 'Untitled Task'
    source = request.form.get('source', '').strip() or None
    tags = request.form.get('tags', '').strip()
    pomos_raw = request.form.get('pomos', '1') or '1'
    pomos = int(pomos_raw) if pomos_raw.isdigit() else 1
    due_raw = request.form.get('due') or date.today().isoformat()
    due = date.fromisoformat(due_raw)  # raises if invalid; form gives YYYY-MM-DD

    status = 'today' if due == date.today() else 'scheduled'

    t = Task(
        title=title,
        source=source,
        tags=tags,
        estimate_pomos=max(1, min(pomos, 8)),  # guardrails: 1..8
        due_date=due,
        status=status,
    )
    db.session.add(t)
    db.session.commit()
    return redirect(url_for('today_view'))  # Post/Redirect/Get

@app.post('/done/<int:task_id>')
def mark_done(task_id: int):
    # Mark a task done and stamp completed_at.
    # Using POST keeps state-changing actions off of simple link clicks and
    # plays well with CSRF protection if you add it later.
    t = Task.query.get_or_404(task_id)
    t.status = 'done'
    t.completed_at = date.today()
    db.session.commit()
    return redirect(url_for('today_view'))

@app.post('/delete/<int:task_id>')
def delete_task(task_id: int):
    # Delete a task permanently.
    # In a shared app you might prefer a soft-delete (flag) — for a solo tool,
    # a hard delete is fine and keeps the DB clean.
    t = Task.query.get_or_404(task_id)
    db.session.delete(t)
    db.session.commit()
    return redirect(url_for('today_view'))

if __name__ == '__main__':
    # debug=True enables hot reload and nicer tracebacks during development
    app.run(debug=True)
