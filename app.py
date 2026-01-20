from flask import Flask, render_template, request, redirect, url_for, flash
from mysql.connector import connect, Error
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_bcrypt import Bcrypt
from datetime import datetime, timedelta, date
import json

app = Flask(__name__)
app.secret_key = 'ai_super_secret_key'

# --- CONFIGURATION ---
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'Vardhan@2005', # <--- CHANGE THIS TO YOUR PASSWORD
    'database': 'ai_todo_flask'
}

bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id, username, email):
        self.id = id
        self.username = username
        self.email = email

@login_manager.user_loader
def load_user(user_id):
    try:
        conn = connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        if user:
            return User(id=user['id'], username=user['username'], email=user['email'])
    except Error:
        pass
    return None

# --- AUTH ROUTES ---
@app.route('/')
def home():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        conn = connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user_data = cursor.fetchone()
        cursor.close()
        conn.close()
        if user_data and bcrypt.check_password_hash(user_data['password'], password):
            user = User(id=user_data['id'], username=user_data['username'], email=user_data['email'])
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Access Denied: Invalid Credentials', 'danger')
    return render_template('login.html')

@app.route('/signup', methods=['POST'])
def signup():
    username = request.form.get('username')
    email = request.form.get('email')
    password = request.form.get('password')
    hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')
    try:
        conn = connect(**db_config)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (username, email, password) VALUES (%s, %s, %s)", 
                       (username, email, hashed_pw))
        conn.commit()
        conn.close()
        flash('Identity Created. Initialize Login.', 'success')
    except Error as e:
        flash(f'Database Error: {e}', 'danger')
    return redirect(url_for('login'))

# --- DASHBOARD ---
@app.route('/dashboard')
@login_required
def dashboard():
    filter_type = request.args.get('filter', 'all')
    search_query = request.args.get('search', '')
    date_filter = request.args.get('date', '')
    
    # Calendar Context
    today = datetime.today()
    try:
        current_month = int(request.args.get('month', today.month))
        current_year = int(request.args.get('year', today.year))
    except ValueError:
        current_month = today.month
        current_year = today.year

    conn = connect(**db_config)
    cursor = conn.cursor(dictionary=True)

    # 1. Fetch ALL tasks
    query = "SELECT * FROM tasks WHERE user_id = %s"
    params = [current_user.id]

    if filter_type == 'completed': query += " AND status = 'completed'"
    elif filter_type == 'expired': query += " AND status = 'expired'"
    elif filter_type == 'deleted': query += " AND status = 'deleted'"
    else: query += " AND status != 'deleted'"

    if search_query:
        query += " AND (title LIKE %s OR description LIKE %s)"
        params.extend([f"%{search_query}%", f"%{search_query}%"])

    # --- CUSTOM SORTING LOGIC ---
    # Priority: Pending (1) -> Expired (2) -> Completed (3) -> Deleted (4)
    # Then sort by Deadline (closest first)
    query += """ ORDER BY 
                 CASE status 
                    WHEN 'pending' THEN 1 
                    WHEN 'expired' THEN 2 
                    WHEN 'completed' THEN 3 
                    ELSE 4 
                 END ASC, 
                 deadline ASC"""

    cursor.execute(query, params)
    raw_tasks = cursor.fetchall()
    
    # Stats
    cursor.execute("""
        SELECT COUNT(*) as total,
        SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) as completed,
        SUM(CASE WHEN status='expired' THEN 1 ELSE 0 END) as expired
        FROM tasks WHERE user_id = %s AND status != 'deleted'
    """, (current_user.id,))
    stats = cursor.fetchone()
    conn.close()

    # --- CALENDAR PROJECTION ---
    display_tasks = []
    projected_dates = set()
    projection_limit = date(current_year + 5, 12, 31) 
    
    target_date = None
    if date_filter:
        target_date = datetime.strptime(date_filter, '%Y-%m-%d').date()

    for task in raw_tasks:
        task_date = task['deadline'].date()
        freq = task['repeat_freq']
        
        # Add actual date
        projected_dates.add(str(task_date))
        
        # Add future dates if repeating
        if freq != 'none':
            curr = task_date
            while curr <= projection_limit:
                if freq == 'daily': curr += timedelta(days=1)
                elif freq == 'weekly': curr += timedelta(weeks=1)
                elif freq == 'monthly': 
                    next_month = curr.replace(day=28) + timedelta(days=4)
                    curr = next_month.replace(day=min(task_date.day, 28))
                elif freq == 'yearly': 
                    curr = curr.replace(year=curr.year + 1)
                
                projected_dates.add(str(curr))

        # Filter Logic for Display
        should_show = False
        if not target_date:
            should_show = True
        else:
            if task_date == target_date: should_show = True
            elif freq == 'daily' and target_date > task_date: should_show = True
            elif freq == 'weekly' and target_date > task_date:
                if (target_date - task_date).days % 7 == 0: should_show = True
            elif freq == 'monthly' and target_date > task_date:
                if target_date.day == task_date.day: should_show = True
            elif freq == 'yearly' and target_date > task_date:
                if target_date.month == task_date.month and target_date.day == task_date.day: should_show = True

        if should_show:
            task['is_overdue'] = task['deadline'] < datetime.now() and task['status'] == 'pending'
            display_tasks.append(task)

    return render_template('dashboard.html', 
                           tasks=display_tasks, 
                           stats=stats, 
                           user=current_user,
                           task_dates=json.dumps(list(projected_dates)), 
                           current_filter=filter_type,
                           cal_month=current_month,
                           cal_year=current_year)

@app.route('/add_task', methods=['POST'])
@login_required
def add_task():
    title = request.form.get('title')
    desc = request.form.get('description')
    deadline = request.form.get('deadline')
    repeat = request.form.get('repeat')
    reminder = request.form.get('reminder')
    
    conn = connect(**db_config)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO tasks (user_id, title, description, deadline, repeat_freq, reminder_minutes) 
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (current_user.id, title, desc, deadline, repeat, reminder))
    conn.commit()
    conn.close()
    return redirect(url_for('dashboard'))

@app.route('/update_task/<int:id>', methods=['POST'])
@login_required
def update_task(id):
    action = request.form.get('action')
    conn = connect(**db_config)
    cursor = conn.cursor(dictionary=True)

    if action == 'toggle':
        cursor.execute("SELECT * FROM tasks WHERE id=%s", (id,))
        task = cursor.fetchone()
        
        if task['status'] == 'pending':
            cursor.execute("UPDATE tasks SET status='completed' WHERE id=%s", (id,))
            
            # Auto-create next task if repeating
            if task['repeat_freq'] != 'none':
                old_date = task['deadline']
                new_date = None
                
                if task['repeat_freq'] == 'daily': new_date = old_date + timedelta(days=1)
                elif task['repeat_freq'] == 'weekly': new_date = old_date + timedelta(weeks=1)
                elif task['repeat_freq'] == 'monthly': new_date = old_date + timedelta(days=30)
                elif task['repeat_freq'] == 'yearly': new_date = old_date + timedelta(days=365)
                
                if new_date:
                    cursor.execute("""
                        INSERT INTO tasks (user_id, title, description, deadline, repeat_freq, reminder_minutes) 
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (current_user.id, task['title'], task['description'], new_date, task['repeat_freq'], task['reminder_minutes']))
        else:
            cursor.execute("UPDATE tasks SET status='pending' WHERE id=%s", (id,))

    elif action == 'delete':
        cursor.execute("UPDATE tasks SET status='deleted' WHERE id=%s", (id,))
    
    elif action == 'modify':
        title = request.form.get('title')
        desc = request.form.get('description')
        deadline = request.form.get('deadline')
        repeat = request.form.get('repeat')
        reminder = request.form.get('reminder')

        cursor.execute("""
            UPDATE tasks 
            SET title=%s, description=%s, deadline=%s, repeat_freq=%s, reminder_minutes=%s 
            WHERE id=%s
        """, (title, desc, deadline, repeat, reminder, id))

    conn.commit()
    conn.close()
    return redirect(url_for('dashboard'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)