from flask import Blueprint, render_template, request, redirect, url_for, flash, session 
from models import db, User, MentoringRequest, FacultySlot
from error_logging import log_error

main_routes = Blueprint('main', __name__)

@main_routes.route('/')
def index():
    return render_template('index.html')
@main_routes.route('/register', methods=['GET', 'POST'])
def register():
    try:
        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')
            role = request.form.get('role')  
            
            if User.query.filter_by(username=username).first():
                flash('Username already exists.')
                return redirect(url_for('main.register'))

            new_user = User(username=username, role=role)
            new_user.set_password(password) 

            db.session.add(new_user)
            db.session.commit()
            
            flash('Registration successful! Please log in.')
            return redirect(url_for('main.login'))
    except Exception as e:
        log_error(f"Registration Error: {str(e)}")
        flash("An error occurred during registration.")
        return redirect(url_for('main.register'))

    return render_template('register.html')

@main_routes.route('/login', methods=['GET', 'POST'])
def login():
    try:
        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')
            
            user = User.query.filter_by(username=username).first()
            if user and user.check_password(password):
                session['user_id'] = user.id  
                flash('Login successful!')
                return redirect(url_for('main.dashboard'))  
            else:
                flash('Invalid username or password.')
                return redirect(url_for('main.login'))
    except Exception as e:
        log_error(f"Login Error: {str(e)}")
        flash("An error occurred during login.")
        return redirect(url_for('main.login'))

    return render_template('login.html')

@main_routes.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        flash('You must be logged in to view the dashboard.')
        return redirect(url_for('main.login'))  
    return render_template('dashboard.html') 

@main_routes.route('/logout')
def logout():
    session.pop('user_id', None) 
    flash('You have been logged out.')
    return redirect(url_for('main.login')) 

@main_routes.route('/request_mentoring', methods=['GET', 'POST'])
def request_mentoring():
    if request.method == 'POST':
        details = request.form['mentoringDetails']
        user_id = session.get('user_id')
        new_request = MentoringRequest(user_id=user_id, details=details)
        db.session.add(new_request)
        db.session.commit()
        flash('Mentoring request submitted successfully!', 'success')
        return redirect(url_for('main.dashboard'))
    return render_template('request_mentoring.html')

@main_routes.route('/faculty_slots', methods=['GET', 'POST'])
def faculty_slots():
    if request.method == 'POST':
        faculty_id = request.form['faculty_id']
        time_slot = request.form['time_slot']
        subject = request.form['subject']
        new_slot = FacultySlot(faculty_id=faculty_id, time_slot=time_slot, subject=subject)
        db.session.add(new_slot)
        db.session.commit()
        flash('Time slot added successfully!', 'success')
        return redirect(url_for('main.faculty_slots'))

    slots = FacultySlot.query.all()
    return render_template('faculty_slots.html', slots=slots)