from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_mysqldb import MySQL
from error_logging import log_error
from werkzeug.security import generate_password_hash, check_password_hash

main_routes = Blueprint('main', __name__)
mysql = MySQL()

TEAM_CAPACITY = 4
def get_available_teams():
    query = """
    SELECT t.id, t.name, GROUP_CONCAT(u.username) AS members
    FROM teams t
    LEFT JOIN team_members tm ON t.id = tm.team_id
    LEFT JOIN users u ON tm.user_id = u.id
    GROUP BY t.id;
    """
    with mysql.connection.cursor() as cur:
        cur.execute(query)
        teams = cur.fetchall()

    available_teams = []
    for team in teams:
        team_id = team[0]
        team_name = team[1]
        members = team[2].split(',') if team[2] else []  
        available_teams.append((team_id, team_name, members))

        print(f"Team ID: {team_id}, Team Name: {team_name}, Members: {members}")

    return available_teams


def can_join_team(team_id):
    query = "SELECT COUNT(*) FROM team_members WHERE team_id = %s"
    with mysql.connection.cursor() as cur:
        cur.execute(query, (team_id,))
        member_count = cur.fetchone()[0] 
    return member_count < TEAM_CAPACITY
def add_member_to_team(team_id, user_id):
    try:
        with mysql.connection.cursor() as cur:
            # Check if the user exists
            cur.execute("SELECT COUNT(*) FROM users WHERE id = %s", (user_id,))
            if cur.fetchone()[0] == 0:
                flash('User does not exist.', 'danger')
                return
            
            cur.execute(
                "INSERT INTO team_members (team_id, user_id) VALUES (%s, %s)", 
                (team_id, user_id)
            )
            mysql.connection.commit()
            flash('Member added to team successfully!', 'success')
    except Exception as e:
        mysql.connection.rollback()  
        log_error(f"Add Member Error: {str(e)}")
        flash('An error occurred while adding the member to the team.', 'danger')

@main_routes.route('/')
def index():
    return render_template('index.html')

@main_routes.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role')

        try:
            with mysql.connection.cursor() as cur:
                cur.execute("SELECT * FROM users WHERE username = %s", (username,))
                user = cur.fetchone()

                if user:
                    flash('Username already exists.')
                    return redirect(url_for('main.register'))

                cur.execute(
                    "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)",
                    (username, generate_password_hash(password), role)
                )
                mysql.connection.commit()

            flash('Registration successful! Please log in.')
            return redirect(url_for('main.login'))

        except Exception as e:
            log_error(f"Registration Error: {str(e)}")
            flash("An error occurred during registration.")
            return redirect(url_for('main.register'))

    return render_template('register.html')

@main_routes.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        try:
            with mysql.connection.cursor() as cur:
                cur.execute("SELECT * FROM users WHERE username = %s", (username,))
                user = cur.fetchone()

                if user and check_password_hash(user[2], password): 
                    session['user_id'] = user[0]
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

@main_routes.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    user_id = session.get('user_id')
    available_teams = get_available_teams() 
    print("Available Teams:", available_teams) 
    if not user_id:
        flash('You must be logged in to view the dashboard.')
        return redirect(url_for('main.login'))

    with mysql.connection.cursor() as cur:
        cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user = cur.fetchone()

        cur.execute("""
            SELECT teams.id, teams.name 
            FROM team_members 
            JOIN teams ON team_members.team_id = teams.id 
            WHERE team_members.user_id = %s
        """, (user_id,))
        user_team = cur.fetchone() 

        is_in_team = bool(user_team)

        if not is_in_team:
            cur.execute(f"""
                SELECT teams.id, teams.name, GROUP_CONCAT(users.username) AS members
                FROM teams 
                LEFT JOIN team_members ON teams.id = team_members.team_id
                LEFT JOIN users ON team_members.user_id = users.id
                WHERE teams.id NOT IN (
                    SELECT team_id FROM team_members WHERE user_id = %s
                )
                GROUP BY teams.id
                HAVING COUNT(team_members.user_id) < %s
            """, (user_id, TEAM_CAPACITY))
            available_teams = cur.fetchall()
            available_teams = [(team[0], team[1], team[2].split(',')) for team in available_teams]

        if request.method == 'POST':
            team_name = request.form.get('team_name')

            if is_in_team:
                flash('You are already a member of a team. Cannot create a new one.')
                return redirect(url_for('main.dashboard'))

            try:
                cur.execute("INSERT INTO teams (name, created_by) VALUES (%s, %s)", 
                            (team_name, user_id))
                team_id = cur.lastrowid 

                cur.execute("INSERT INTO team_members (team_id, user_id) VALUES (%s, %s)", 
                            (team_id, user_id))

                mysql.connection.commit()
                flash('Team created successfully!', 'success')
                return redirect(url_for('main.dashboard'))

            except Exception as e:
                mysql.connection.rollback() 
                log_error(f"Team Creation Error: {str(e)}")
                flash('An error occurred while creating the team.', 'danger')

        print(available_teams)

    return render_template(
        'dashboard.html', 
        user=user, 
        user_team=user_team,  
        available_teams=available_teams, 
        is_in_team=is_in_team
    )


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

        try:
            with mysql.connection.cursor() as cur:
                cur.execute("INSERT INTO mentoring_requests (user_id, details) VALUES (%s, %s)", (user_id, details))
                mysql.connection.commit()

            flash('Mentoring request submitted successfully!', 'success')
            return redirect(url_for('main.dashboard'))

        except Exception as e:
            log_error(f"Mentoring Request Error: {str(e)}")
            flash("An error occurred while submitting your mentoring request.")
            return redirect(url_for('main.dashboard'))

    return render_template('request_mentoring.html')

@main_routes.route('/faculty_slots', methods=['GET', 'POST'])
def faculty_slots():
    if request.method == 'POST':
        faculty_id = request.form['faculty_id']
        time_slot = request.form['time_slot']
        subject = request.form['subject']

        try:
            with mysql.connection.cursor() as cur:
                cur.execute("INSERT INTO faculty_slots (faculty_id, time_slot, subject) VALUES (%s, %s, %s)", 
                            (faculty_id, time_slot, subject))
                mysql.connection.commit()

            flash('Time slot added successfully!', 'success')
            return redirect(url_for('main.faculty_slots'))

        except Exception as e:
            log_error(f"Faculty Slots Error: {str(e)}")
            flash("An error occurred while adding the time slot.")
            return redirect(url_for('main.faculty_slots'))

    with mysql.connection.cursor() as cur:
        cur.execute("SELECT * FROM faculty_slots")
        slots = cur.fetchall()
    
    return render_template('faculty_slots.html', slots=slots)

@main_routes.route('/create_team', methods=['POST'])
def create_team():
    user_id = session.get('user_id')
    team_name = request.form.get('team_name')
    member_ids = request.form['members'].split(',')

    if not user_id or not team_name:
        flash('You must be logged in and provide a team name.')
        return redirect(url_for('main.dashboard'))

    try:
        with mysql.connection.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM team_members WHERE user_id = %s", (user_id,))
            if cur.fetchone()[0] > 0:
                flash('You are already a member of a team. Cannot create a new team.')
                return redirect(url_for('main.dashboard'))

            cur.execute("INSERT INTO teams (name, created_by) VALUES (%s, %s)", 
                        (team_name, user_id))
            team_id = cur.lastrowid 
            for member_id in member_ids:
                add_member_to_team(team_id, member_id.strip())


            cur.execute("INSERT INTO team_members (team_id, user_id) VALUES (%s, %s)", 
                        (team_id, user_id))
            mysql.connection.commit()
        
        flash('Team created successfully!', 'success')
    except Exception as e:
        log_error(f"Create Team Error: {str(e)}")
        mysql.connection.rollback() 
        flash("An error occurred while trying to create the team.")
    
    return redirect(url_for('main.dashboard'))
@main_routes.route('/join_team', methods=['POST'])
def join_team():
    user_id = session.get('user_id')
    team_id = request.form.get('team_id')

    if not user_id or not team_id:
        flash('You must be logged in and select a team to join.')
        return redirect(url_for('main.dashboard'))

    if not can_join_team(team_id):
        flash('This team is already at full capacity.')
        return redirect(url_for('main.dashboard'))

    try:
        with mysql.connection.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM team_members WHERE user_id = %s", (user_id,))
            if cur.fetchone()[0] > 0:
                flash('You are already a member of a team. Cannot join another team.')
                return redirect(url_for('main.dashboard'))

            add_member_to_team(team_id, user_id)  # This should work now since capacity is checked.
            flash('You have successfully joined the team!', 'success')

    except Exception as e:
        log_error(f"Join Team Error: {str(e)}")
        flash("An error occurred while trying to join the team.")

    return redirect(url_for('main.dashboard'))

@main_routes.route('/leave_team', methods=['POST'])
def leave_team():
    user_id = session.get('user_id')

    if not user_id:
        flash('You must be logged in to leave a team.')
        return redirect(url_for('main.dashboard'))

    try:
        with mysql.connection.cursor() as cur:
            cur.execute("SELECT team_id FROM team_members WHERE user_id = %s", (user_id,))
            team_id = cur.fetchone()

            if not team_id:
                flash('You are not part of any team.')
                return redirect(url_for('main.dashboard'))

            team_id = team_id[0]  # Get the actual team_id value
            cur.execute("DELETE FROM team_members WHERE user_id = %s", (user_id,))

            # Check if the team has any members left
            cur.execute("SELECT COUNT(*) FROM team_members WHERE team_id = %s", (team_id,))
            member_count = cur.fetchone()[0]

            if member_count == 0:
                cur.execute("DELETE FROM teams WHERE id = %s", (team_id,))

            mysql.connection.commit()

        flash('You have left the team successfully!', 'success')
    except Exception as e:
        log_error(f"Leave Team Error: {str(e)}")
        mysql.connection.rollback()  
        flash('An error occurred while trying to leave the team.')

    return redirect(url_for('main.dashboard'))

