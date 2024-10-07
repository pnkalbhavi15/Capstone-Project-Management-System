from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from models import db
from routes import main_routes

app = Flask(__name__)

import os
app.secret_key = os.urandom(24)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'

db.init_app(app)

with app.app_context():
    db.create_all()

app.register_blueprint(main_routes)

if __name__ == '__main__':
    app.run(debug=True)
