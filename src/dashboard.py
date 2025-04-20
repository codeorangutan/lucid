import os
from flask import Flask, render_template_string, request, redirect, url_for, flash
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import logging
from datetime import datetime
import threading

# --- CONFIGURATION ---
LOG_PATH = os.path.join(os.path.dirname(__file__), '..', 'lucid_orchestrator.log')
ORCHESTRATOR_MODULE = 'orchestrator'
ORCHESTRATOR_FUNC = 'main'
DEFAULT_INTERVAL_MINUTES = 10

# --- FLASK APP SETUP ---
app = Flask(__name__)
app.secret_key = os.urandom(16)

# --- SCHEDULER SETUP ---
scheduler = BackgroundScheduler()
scheduler_lock = threading.Lock()  # Prevent race conditions

# --- ORCHESTRATOR RUNNER ---
def run_orchestrator():
    try:
        import importlib
        orchestrator = importlib.import_module(ORCHESTRATOR_MODULE)
        getattr(orchestrator, ORCHESTRATOR_FUNC)()
    except Exception as e:
        logging.exception(f"Dashboard failed to run orchestrator: {e}")

# --- SCHEDULER JOB MANAGEMENT ---
def start_scheduler_job(interval_minutes):
    with scheduler_lock:
        if scheduler.get_job('orchestrator_job'):
            scheduler.remove_job('orchestrator_job')
        scheduler.add_job(run_orchestrator, IntervalTrigger(minutes=interval_minutes), id='orchestrator_job', replace_existing=True, next_run_time=datetime.now())
        if not scheduler.running:
            scheduler.start()

def pause_scheduler_job():
    with scheduler_lock:
        job = scheduler.get_job('orchestrator_job')
        if job:
            job.pause()

def resume_scheduler_job():
    with scheduler_lock:
        job = scheduler.get_job('orchestrator_job')
        if job:
            job.resume()

def remove_scheduler_job():
    with scheduler_lock:
        if scheduler.get_job('orchestrator_job'):
            scheduler.remove_job('orchestrator_job')

def get_job_status():
    job = scheduler.get_job('orchestrator_job')
    if not job:
        return 'Not scheduled'
    if job.next_run_time is None:
        return 'Paused'
    return f"Scheduled: Next run at {job.next_run_time.strftime('%Y-%m-%d %H:%M:%S')}"

def get_last_log_lines(n=100):
    if not os.path.exists(LOG_PATH):
        return ["No logs found."]
    with open(LOG_PATH, 'r', encoding='utf-8', errors='replace') as f:
        lines = f.readlines()
    return lines[-n:]

# --- FLASK ROUTES ---
@app.route('/', methods=['GET', 'POST'])
def dashboard():
    status = get_job_status()
    logs = get_last_log_lines(100)
    interval = request.form.get('interval', DEFAULT_INTERVAL_MINUTES)
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'run_now':
            threading.Thread(target=run_orchestrator).start()
            flash('Orchestrator started manually.', 'info')
        elif action == 'pause':
            pause_scheduler_job()
            flash('Scheduler paused.', 'warning')
        elif action == 'resume':
            resume_scheduler_job()
            flash('Scheduler resumed.', 'success')
        elif action == 'remove':
            remove_scheduler_job()
            flash('Scheduler job removed.', 'warning')
        elif action == 'set_interval':
            try:
                minutes = int(request.form.get('interval', DEFAULT_INTERVAL_MINUTES))
                start_scheduler_job(minutes)
                flash(f'Scheduler interval set to {minutes} minutes.', 'success')
            except Exception as e:
                flash(f'Failed to set interval: {e}', 'danger')
        return redirect(url_for('dashboard'))
    return render_template_string('''
    <html>
    <head>
        <title>LUCID Orchestrator Dashboard</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            pre { background: #222; color: #eee; padding: 10px; border-radius: 5px; max-height: 400px; overflow-y: scroll; }
            .controls { margin-bottom: 20px; }
            .controls form { display: inline-block; margin-right: 10px; }
            .status { margin-bottom: 10px; font-weight: bold; }
            .flash { margin: 10px 0; padding: 8px; border-radius: 4px; }
            .flash-info { background: #d9edf7; color: #31708f; }
            .flash-success { background: #dff0d8; color: #3c763d; }
            .flash-warning { background: #fcf8e3; color: #8a6d3b; }
            .flash-danger { background: #f2dede; color: #a94442; }
        </style>
    </head>
    <body>
        <h2>LUCID Orchestrator Dashboard</h2>
        <div class="status">Status: {{ status }}</div>
        {% with messages = get_flashed_messages(with_categories=true) %}
          {% if messages %}
            {% for category, message in messages %}
              <div class="flash flash-{{ category }}">{{ message }}</div>
            {% endfor %}
          {% endif %}
        {% endwith %}
        <div class="controls">
            <form method="post"><button name="action" value="run_now">Run Now</button></form>
            <form method="post"><button name="action" value="pause">Pause</button></form>
            <form method="post"><button name="action" value="resume">Resume</button></form>
            <form method="post"><button name="action" value="remove">Remove Job</button></form>
            <form method="post" style="display:inline-block;">
                <input type="number" name="interval" min="1" value="{{ interval }}" style="width:60px;" />
                <button name="action" value="set_interval">Set Interval (min)</button>
            </form>
        </div>
        <h3>Recent Logs</h3>
        <pre>{{ logs|join('') }}</pre>
    </body>
    </html>
    ''', status=status, logs=logs, interval=interval)

if __name__ == '__main__':
    start_scheduler_job(DEFAULT_INTERVAL_MINUTES)
    app.run(host='0.0.0.0', port=5000, debug=False)
