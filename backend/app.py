from flask import Flask, render_template, session, redirect, url_for, flash
from flask_mysqldb import MySQL
import os
from routes import main_routes
from dotenv import load_dotenv
from functools import wraps
import logging

logging.basicConfig(level=logging.DEBUG)

load_dotenv()
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'uploads') 
try:
    app.config['MYSQL_HOST'] = os.getenv('MYSQL_HOST')
    app.config['MYSQL_USER'] = os.getenv('MYSQL_USER')
    app.config['MYSQL_PASSWORD'] = os.getenv('MYSQL_PASSWORD')
    app.config['MYSQL_DB'] = os.getenv('MYSQL_DB')
    if not all([app.config['MYSQL_HOST'], app.config['MYSQL_USER'], app.config['MYSQL_PASSWORD'], app.config['MYSQL_DB']]):
        raise ValueError("Some MySQL environment variables are missing.")
except ValueError as e:
    print(f"Error in MySQL configuration: {e}")

mysql = MySQL(app)
app.register_blueprint(main_routes)

app.secret_key = os.getenv('SECRET_KEY', os.urandom(24))

@app.route('/')
def login():
    return render_template('login.html')
def role_required(role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if session.get("role") != role:
                flash("You do not have permission to access this page.")
                return redirect(url_for("main.home"))
            return f(*args, **kwargs)
        return decorated_function
    return decorator
@app.route('/faculty_dashboard')
@role_required('Faculty')
def faculty_dashboard():
    return render_template('faculty_dashboard.html')

@app.route('/admin_dashboard')
@role_required('Admin')
def admin_dashboard():
    return render_template('admin_dashboard.html')


@app.errorhandler(Exception)
def handle_exception(e):
    logging.error(f"An error occurred: {e}")
    return "An error occurred", 500

@app.route('/favicon.ico')
def favicon():
    return '', 204  # Returns a 204 No Content response

if __name__ == '__main__':
    app.run(debug=True)
