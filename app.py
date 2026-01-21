from flask import Flask, render_template, request, redirect, url_for, flash
from pymongo import MongoClient
from bson.objectid import ObjectId
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_bcrypt import Bcrypt
from datetime import datetime, timedelta
import json

app = Flask(__name__)
app.secret_key = 'ai_super_secret_key'

# --- MONGODB CONNECTION ---
client = MongoClient('mongodb://localhost:27017/')
db = client['ai_todo_flask']

bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, user_id, username, email):
        self.id = str(user_id) # Convert ObjectId to string for Flask-Login
        self.username = username
        self.email = email

@login_manager.user_loader
def load_user(user_id):
    try:
        user_data = db.users.find_one({"_id": ObjectId(user_id)})
        if user_data:
            return User(user_id=user_data['_id'], username=user_data['username'], email=user_data['email'])
    except:
        return None

# --- ROUTES ---
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
        user_data = db.users.find_one({"email": email})
        
        if user_data and bcrypt.check_password_hash(user_data['password'], password):
            user = User(user_id=user_data['_id'], username=user_data['username'], email=user_data['email'])
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid Credentials', 'danger')
    return render_template('login.html')

@app.route('/signup', methods=['POST'])
def signup():
    username = request.form.get('username')
    email = request.form.get('email')
    password = request.form.get('password')
    
    if db.users.find_one({"email": email}):
        flash('Email already exists', 'danger')
        return redirect(url_for('login'))
        
    hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')
    db.users.insert_one({"username": username, "email": email, "password": hashed_pw})
    flash('Account created', 'success')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    filter_type = request.args.get('filter', 'all')
    search_query = request.args.get('search', '')
    date_filter = request.args.get('date', '')
    
    today = datetime.today()
    try:
        current_month = int(request.args.get('month', today.month))
        current_year = int(request.args.get('year', today.year))
    except ValueError:
        current_month = today.month
        current_year = today.year

    # 1. Auto-Expire Tasks (Update status if deadline passed)
    db.tasks.update_many(
        {"status": "pending", "deadline": {"$lt": datetime.now()}},
        {"$set": {"status": "expired"}}
    )

    # 2. Build Query
    query = {"user_id": ObjectId(current_user.id)}
    
    if filter_type == 'completed': query["status"] = 'completed'
    elif filter_type == 'expired': query["status"] = 'expired'
    elif filter_type == 'deleted': query["status"] = 'deleted'
    else: query["status"] = {"$ne": 'deleted'}

    if search_query:
        query["$or"] = [
            {"title": {"$regex": search_query, "$options": "i"}},
            {"description": {"$regex": search_query, "$options": "i"}}
        ]

    # 3. Fetch Tasks
    raw_tasks = list(db.tasks.find(query))

    # 4. Sort (Pending > Expired > Completed > Deleted)
    status_priority = {'pending': 1, 'expired': 2, 'completed': 3, 'deleted': 4}
    raw_tasks.sort(key=lambda x: (status_priority.get(x.get('status'), 5), x.get('deadline')))

    # 5. Process Tasks for Template
    display_tasks = []
    projected_dates = set()
    projection_limit = datetime(current_year + 5, 12, 31)
    
    target_date_obj = None
    if date_filter:
        target_date_obj = datetime.strptime(date_filter, '%Y-%m-%d').date()

    for task in raw_tasks:
        task['id'] = str(task['_id']) # Important: Convert ObjectId to string
        
        # Calculate Overdue for CSS
        task['is_overdue'] = task['deadline'] < datetime.now() and task['status'] != 'completed'

        # Calendar Projection Logic
        deadline_dt = task['deadline']
        projected_dates.add(str(deadline_dt.date()))
        
        freq = task.get('repeat_freq', 'none')
        if freq != 'none':
            curr = deadline_dt
            while curr.date() <= projection_limit.date():
                if freq == 'daily': curr += timedelta(days=1)
                elif freq == 'weekly': curr += timedelta(weeks=1)
                elif freq == 'monthly': 
                    next_month = curr.replace(day=28) + timedelta(days=4)
                    curr = next_month.replace(day=min(deadline_dt.day, 28))
                elif freq == 'yearly': 
                    curr = curr.replace(year=curr.year + 1)
                projected_dates.add(str(curr.date()))

        # Filter Logic
        should_show = True
        if target_date_obj:
            should_show = False
            task_date = deadline_dt.date()
            if task_date == target_date_obj: should_show = True
            # (Simplified recurring check for brevity, exact date match for now)
            elif str(target_date_obj) in projected_dates: should_show = True

        if should_show:
            display_tasks.append(task)

    # Stats
    stats = {
        'total': db.tasks.count_documents({"user_id": ObjectId(current_user.id), "status": {"$ne": "deleted"}}),
        'completed': db.tasks.count_documents({"user_id": ObjectId(current_user.id), "status": "completed"}),
        'expired': db.tasks.count_documents({"user_id": ObjectId(current_user.id), "status": "expired"})
    }

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
    deadline = datetime.strptime(request.form.get('deadline'), '%Y-%m-%dT%H:%M')
    db.tasks.insert_one({
        "user_id": ObjectId(current_user.id),
        "title": request.form.get('title'),
        "description": request.form.get('description'),
        "deadline": deadline,
        "repeat_freq": request.form.get('repeat'),
        "reminder_minutes": int(request.form.get('reminder')),
        "status": "pending"
    })
    return redirect(url_for('dashboard'))

@app.route('/update_task/<task_id>', methods=['POST'])
@login_required
def update_task(task_id):
    action = request.form.get('action')
    task = db.tasks.find_one({"_id": ObjectId(task_id)})
    
    if action == 'toggle':
        new_status = 'completed' if task['status'] != 'completed' else 'pending'
        db.tasks.update_one({"_id": ObjectId(task_id)}, {"$set": {"status": new_status}})
        
        # If completing a repeating task, create next one
        if new_status == 'completed' and task['repeat_freq'] != 'none':
            old = task['deadline']
            nxt = None
            if task['repeat_freq'] == 'daily': nxt = old + timedelta(days=1)
            elif task['repeat_freq'] == 'weekly': nxt = old + timedelta(weeks=1)
            elif task['repeat_freq'] == 'monthly': nxt = (old.replace(day=28) + timedelta(days=4)).replace(day=min(old.day, 28))
            elif task['repeat_freq'] == 'yearly': nxt = old.replace(year=old.year + 1)
            
            if nxt:
                db.tasks.insert_one({
                    "user_id": ObjectId(current_user.id),
                    "title": task['title'],
                    "description": task['description'],
                    "deadline": nxt,
                    "repeat_freq": task['repeat_freq'],
                    "reminder_minutes": task['reminder_minutes'],
                    "status": "pending"
                })

    elif action == 'delete':
        db.tasks.update_one({"_id": ObjectId(task_id)}, {"$set": {"status": "deleted"}})
        
    elif action == 'modify':
        deadline = datetime.strptime(request.form.get('deadline'), '%Y-%m-%dT%H:%M')
        status = 'pending' if task['status'] == 'expired' else task['status']
        db.tasks.update_one({"_id": ObjectId(task_id)}, {"$set": {
            "title": request.form.get('title'),
            "description": request.form.get('description'),
            "deadline": deadline,
            "repeat_freq": request.form.get('repeat'),
            "reminder_minutes": int(request.form.get('reminder')),
            "status": status
        }})

    return redirect(url_for('dashboard'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)