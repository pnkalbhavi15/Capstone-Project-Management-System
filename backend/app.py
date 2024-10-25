from flask import Flask, render_template
from flask_mysqldb import MySQL
import os
from routes import main_routes
from dotenv import PASSWORD
app = Flask(__name__)

app.config['MYSQL_HOST'] = 'localhost'  
app.config['MYSQL_USER'] = 'root'  
app.config['MYSQL_PASSWORD'] = PASSWORD
app.config['MYSQL_DB'] = 'capstone_management' 

mysql = MySQL(app)
app.register_blueprint(main_routes)

app.secret_key = os.urandom(24)

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)