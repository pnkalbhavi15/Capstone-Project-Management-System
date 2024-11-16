from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from flask_mysqldb import MySQL
from error_logging import log_error
from flask import send_file, abort
from werkzeug.utils import secure_filename
from flask import send_from_directory, current_app
from werkzeug.security import generate_password_hash, check_password_hash
import os
import io

main_routes = Blueprint('main', __name__)
mysql = MySQL()
TEAM_CAPACITY = 4

UPLOAD_FOLDER = os.path.join('uploads', 'resumes')  # Ensure this directory exists and is writable  # Set this to your desired upload folder
ALLOWED_EXTENSIONS = {'pdf'}

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

#MAIN ROUTES
@main_routes.route('/home')
def home():
    return render_template('home.html')
@main_routes.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role')
        
        try:
            with mysql.connection.cursor() as cur:
                # Check if the username already exists
                cur.execute("SELECT * FROM users WHERE username = %s", (username,))
                user = cur.fetchone()
                if user:
                    flash('Username already exists.')
                    return redirect(url_for('main.register'))
                
                # Call the stored procedure to add the user
                cur.callproc('add_user', (username, generate_password_hash(password), role))
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
                    session['username'] = username
                    session['user_id'] = user[0]
                    session['role'] = user[3]  # Assuming role is in the 4th column
                    flash('Login successful!')

                    # Redirect based on role
                    if user[3] == 'admin':
                        return redirect(url_for('main.admin_dashboard'))
                    elif user[3] == 'faculty':
                        return redirect(url_for('main.faculty_dashboard'))
                    elif user[3] == 'student':
                        return redirect(url_for('main.dashboard'))  # Adjust as necessary
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
    if not user_id:
        flash('You must be logged in to view the dashboard.')
        return redirect(url_for('main.login'))

    with mysql.connection.cursor() as cur:
        cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user = cur.fetchone()
        
        # Check the user role
        if user[3] == 'faculty':  # Assuming role is in the 4th column
            return redirect(url_for('main.faculty_dashboard'))  # Redirect to faculty dashboard
        elif user[3] == 'student':
            # Logic for student dashboard
            cur.execute("""
                SELECT teams.id, teams.name 
                FROM team_members 
                JOIN teams ON team_members.team_id = teams.id 
                WHERE team_members.user_id = %s
            """, (user_id,))
            user_team = cur.fetchone()
            is_in_team = bool(user_team)
            available_teams = []

            if not is_in_team:
                cur.execute("""
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
                available_teams_raw = cur.fetchall()
                available_teams = [
                    (team[0], team[1], team[2].split(',') if team[2] else [])
                    for team in available_teams_raw
                ]

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

            return render_template(
                'dashboard.html',  # Render a specific template for students
                user=user, 
                user_team=user_team,  
                available_teams=available_teams, 
                is_in_team=is_in_team
            )
        else:
            flash('Invalid user role.')
            return redirect(url_for('main.login'))   
        
@main_routes.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('You have been logged out.')
    return redirect(url_for('main.login'))
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

@main_routes.route('/create_team', methods=['POST'])
def create_team():
    # Get the form data
    team_name = request.form.get('team_name')
    members = request.form.get('members', '').split(',')

    # Check if user is logged in
    user_id = session.get('user_id')
    if not user_id:
        flash('You must be logged in to create a team.')
        return redirect(url_for('main.dashboard'))

    if not team_name:
        flash('You must provide a team name.')
        return redirect(url_for('main.dashboard'))

    # Proceed with team creation logic
    try:
        with mysql.connection.cursor() as cur:
            # Check if the user is already part of a team
            cur.execute("SELECT COUNT(*) FROM team_members WHERE user_id = %s", (user_id,))
            if cur.fetchone()[0] > 0:
                flash('You are already a member of a team. Cannot create a new team.')
                return redirect(url_for('main.dashboard'))

            # Create the team in the database
            cur.execute("INSERT INTO teams (name, created_by) VALUES (%s, %s)", (team_name, user_id))
            team_id = cur.lastrowid

            # Add the user as the first member of the team
            cur.execute("INSERT INTO team_members (team_id, user_id) VALUES (%s, %s)", (team_id, user_id))

            # Add additional members to the team
            for member_id in members:
                member_id = member_id.strip()  # Remove any whitespace
                if member_id:  # Ensure member_id is not empty
                    cur.execute("INSERT INTO team_members (team_id, user_id) VALUES (%s, %s)", (team_id, member_id))

            mysql.connection.commit()
            flash('Team created successfully!', 'success')
            return redirect(url_for('main.dashboard'))

    except Exception as e:
        mysql.connection.rollback()
        log_error(f"Team Creation Error: {str(e)}")
        flash('An error occurred while trying to create the team.', 'danger')

    return redirect(url_for('main.dashboard'))
@main_routes.route('/request_mentoring', methods=['POST'])
def request_mentoring():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'success': False, 'message': 'You must be logged in to send a request.'}), 403

    details = request.form.get('request_details')
    faculty_id = request.form.get('faculty_id')
    team_id = request.form.get('team_id')

    # Handle file upload
    if 'resume' not in request.files:
        return jsonify({'success': False, 'message': 'No file part.'}), 400

    file = request.files['resume']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No selected file.'}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)

        file_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(file_path)

        try:
            # Validate that all necessary data is present
            if not faculty_id or not details or not team_id:
                raise ValueError("Missing data: faculty_id, details, or team_id.")

            # Insert mentoring request into the database
            with mysql.connection.cursor() as cur:
                cur.execute(
                    "INSERT INTO mentoring_requests (team_id, faculty_id, user_id, details, resume_file) VALUES (%s, %s, %s, %s, %s)",
                    (team_id, faculty_id, user_id, details, filename)  # Include filename for the resume
                )
                mysql.connection.commit()  # Commit the transaction

            return jsonify({'success': True})  # Return success response
        except Exception as e:
            mysql.connection.rollback()
            print(f"Error occurred: {str(e)}")  # Debugging line
            return jsonify({'success': False, 'message': "An error occurred while submitting your mentoring request."}), 500
    else:
        return jsonify({'success': False, 'message': 'Invalid file type. Only PDF files are allowed.'}), 400
@main_routes.route('/faculty_dashboard', methods=['GET'])
def faculty_dashboard():
    faculty_id = session.get('user_id')
    if not faculty_id:
        flash('You must be logged in to view the dashboard.')
        return redirect(url_for('main.login'))

    with mysql.connection.cursor() as cur:
        # Get the mentoring requests
        cur.execute("""
            SELECT requests.id, users.username AS requester_username, requests.details, 
                teams.name AS team_name, requests.resume_file, requests.request_status,
                GROUP_CONCAT(members.username SEPARATOR ', ') AS team_members
            FROM mentoring_requests requests
            JOIN users ON requests.user_id = users.id
            JOIN teams ON requests.team_id = teams.id
            LEFT JOIN team_members ON teams.id = team_members.team_id
            LEFT JOIN users AS members ON team_members.user_id = members.id  -- Join to get member usernames
            WHERE requests.faculty_id = %s
            GROUP BY requests.id
        """, (faculty_id,))
        requests = cur.fetchall()

        # Get the number of accepted requests
        cur.execute("""
            SELECT COUNT(*) FROM mentoring_requests
            WHERE faculty_id = %s AND request_status = 'accepted'
        """, (faculty_id,))
        accepted_count = cur.fetchone()[0]

    print("Mentoring Requests:", requests) 
    print("Accepted Requests:", accepted_count)  # Debugging output

    return render_template('faculty_dashboard.html', requests=requests, accepted_count=accepted_count) 

@main_routes.route('/respond_to_request', methods=['POST'])
def respond_to_request():
    user_id = session.get('user_id')
    if not user_id:
        flash('You must be logged in to respond to requests.')
        return redirect(url_for('main.login'))

    request_id = request.form.get('request_id')
    response = request.form.get('response')  # 'accept' or 'reject'
    print(f"Request ID: {request_id}, Response: {response}") 
    
    try:
        with mysql.connection.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM mentoring_requests WHERE id = %s", (request_id,))
            exists = cur.fetchone()[0]
            if exists == 0:
                print("Request ID does not exist in the database.")
                flash('Invalid request ID.', 'danger')
                return redirect(url_for('main.faculty_dashboard'))
            
            if response == 'accept':
                # Check how many requests the faculty member has already accepted
                cur.execute("""
                    SELECT COUNT(*) FROM mentoring_requests
                    WHERE faculty_id = %s AND request_status = 'accepted'
                """, (user_id,))
                accepted_count = cur.fetchone()[0]
                print(f"Accepted Count: {accepted_count}") 

                if accepted_count >= 5:
                    flash('You have already accepted the maximum number of requests (5).', 'danger')
                    return redirect(url_for('main.faculty_dashboard'))

                # Update the request status to accepted
                cur.execute("UPDATE mentoring_requests SET request_status = 'accepted' WHERE id = %s", (request_id,))
                mysql.connection.commit()
                affected_rows = cur.rowcount
                if affected_rows > 0:
                    print(f"Updated request ID {request_id} to 'accepted'.")
                    flash('Mentoring request accepted!', 'success')
                else:
                    print("No rows updated for accepted request. The status might already be 'accepted'.")
                    flash('The request status is already accepted.', 'info')
                    
            elif response == 'reject':
                # Update the request status to rejected
                cur.execute("UPDATE mentoring_requests SET request_status = 'rejected' WHERE id = %s", (request_id,))
                mysql.connection.commit()  # Commit the transaction
                affected_rows = cur.rowcount
                if affected_rows > 0:
                    print(f"Updated request ID {request_id} to 'rejected'.")
                    flash('Mentoring request rejected.', 'info')
                else:
                    print("No rows updated for rejected request. The status might already be 'rejected'.")
                    flash('The request status is already rejected.', 'info')


            else:
                flash('Invalid action.', 'danger')

    except Exception as e:
        log_error(f"Respond to Request Error: {str(e)}")
        mysql.connection.rollback()  # Rollback in case of error
        flash('An error occurred while responding to the request.', 'danger')

    return redirect(url_for('main.faculty_dashboard'))

@main_routes.route('/download_pdf/<int:request_id>', methods=['GET'])
def download_pdf(request_id):
    try:
        with mysql.connection.cursor() as cur:
            # Query to get the resume filename from the database
            cur.execute("SELECT resume_file FROM mentoring_requests WHERE id = %s", (request_id,))
            result = cur.fetchone()

            if result is None or result[0] is None:
                return jsonify({'success': False, 'message': 'File not found.'}), 404

            # Get the filename and ensure it is a string
            filename = result[0]
            if isinstance(filename, bytes):
                filename = filename.decode('utf-8')

            # Construct the full file path
            file_path = os.path.join(UPLOAD_FOLDER, filename)

            # Check if the file exists on the filesystem
            if not os.path.exists(file_path):
                return jsonify({'success': False, 'message': 'File not found on server.'}), 404

            # Send the file as a response
            return send_file(file_path, as_attachment=True, download_name=filename, mimetype='application/pdf')

    except Exception as e:
        print(f"Error occurred: {str(e)}")  # Debugging line
        return jsonify({'success': False, 'message': 'An error occurred while downloading the file.'}), 500    

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
def can_join_team(team_id):
    query = "SELECT COUNT(*) FROM team_members WHERE team_id = %s"
    with mysql.connection.cursor() as cur:
        cur.execute(query, (team_id,))
        member_count = cur.fetchone()[0]
    return member_count < TEAM_CAPACITY
def add_member_to_team(team_id, user_id):
    try:
        with mysql.connection.cursor() as cur:
            cur.execute("SELECT name FROM teams WHERE id = %s", (team_id,))
            team = cur.fetchone()
            if not team:
                flash('Team does not exist.', 'danger')
                return False
            cur.execute("SELECT COUNT(*) FROM users WHERE id = %s", (user_id,))
            if cur.fetchone()[0] == 0:
                flash('User does not exist.', 'danger')
                return False
            cur.execute(
                "INSERT INTO team_members (team_id, user_id) VALUES (%s, %s)", 
                (team_id, user_id)
            )
            mysql.connection.commit()
            flash('Member added to team successfully!', 'success')
            return True
    except Exception as e:
        mysql.connection.rollback()
        log_error(f"Add Member Error: {str(e)}")
        flash('An error occurred while adding the member to the team.', 'danger')
        return False
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
            # Check if user is already part of a team
            cur.execute("SELECT COUNT(*) FROM team_members WHERE user_id = %s", (user_id,))
            if cur.fetchone()[0] > 0:
                flash('You are already a member of a team. Cannot join another team.')
                return redirect(url_for('main.dashboard'))

            # Add member to the team
            if add_member_to_team(team_id, user_id):
                cur.execute("SELECT name FROM teams WHERE id = %s", (team_id,))
                team_name = cur.fetchone()[0]
                create_notification(user_id, f'You have successfully joined team "{team_name}".')
                flash('You have successfully joined the team!', 'success')
                return redirect(url_for('main.dashboard', team_id=team_id))
            else:
                flash('An error occurred while trying to join the team.', 'danger')
    except Exception as e:
        log_error(f"Join Team Error: {str(e)}")
        flash("An error occurred while trying to join the team.", 'danger')

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
            result = cur.fetchone()
            if not result:
                flash('You are not part of any team.')
                return redirect(url_for('main.dashboard'))
            team_id = result[0]
            cur.execute("DELETE FROM team_members WHERE user_id = %s", (user_id,))
            mysql.connection.commit()
            flash('You have left the team.', 'success')
            cur.execute("SELECT COUNT(*) FROM team_members WHERE team_id = %s", (team_id,))
            member_count = cur.fetchone()[0]
            if member_count == 0:
                cur.execute("DELETE FROM teams WHERE id = %s", (team_id,))
                mysql.connection.commit()
                flash('Since you were the last member, the team has been deleted.', 'info')
            create_notification(user_id, f'You have left team "{team_id}".')
    except Exception as e:
        mysql.connection.rollback()
        log_error(f"Leave Team Error: {str(e)}")
        flash("An error occurred while trying to leave the team.", 'danger')
    return redirect(url_for('main.dashboard'))
@main_routes.route('/edit_team/<int:team_id>', methods=['GET', 'POST'])
def edit_team(team_id):
    user_id = session.get('user_id')
    if not user_id:
        flash('You must be logged in to edit a team.')
        return redirect(url_for('main.login'))
    if request.method == 'POST':
        new_team_name = request.form.get('team_name')
        try:
            with mysql.connection.cursor() as cur:
                cur.execute("UPDATE teams SET name = %s WHERE id = %s AND created_by = %s", 
                            (new_team_name, team_id, user_id))
                mysql.connection.commit()
            flash('Team name updated successfully!', 'success')
            return redirect(url_for('main.dashboard'))
        except Exception as e:
            log_error(f"Edit Team Error: {str(e)}")
            mysql.connection.rollback()
            flash('An error occurred while updating the team name.', 'danger')
    return render_template('edit_team.html', team_id=team_id)
@main_routes.route('/delete_team/<int:team_id>', methods=['POST'])
def delete_team(team_id):
    user_id = session.get('user_id')
    if not user_id:
        flash('You must be logged in to delete a team.')
        return redirect(url_for('main.login'))
    try:
        with mysql.connection.cursor() as cur:
            cur.execute("DELETE FROM teams WHERE id = %s AND created_by = %s", (team_id, user_id))
            mysql.connection.commit()
        flash('Team deleted successfully!', 'success')
    except Exception as e:
        log_error(f"Delete Team Error: {str(e)}")
        mysql.connection.rollback()
        flash('An error occurred while trying to delete the team.', 'danger')
    return redirect(url_for('main.dashboard'))
@main_routes.route('/view_team_members/<int:team_id>', methods=['GET'])
def view_team_members(team_id):
    user_id = session.get('user_id')
    if not user_id:
        flash('You must be logged in to view team members.')
        return redirect(url_for('main.login'))
    try:
        with mysql.connection.cursor() as cur:
            cur.execute("""
                SELECT u.username 
                FROM team_members tm 
                JOIN users u ON tm.user_id = u.id 
                WHERE tm.team_id = %s
            """, (team_id,))
            members = cur.fetchall()
        return render_template('view_team_members.html', team_id=team_id, members=members)
    except Exception as e:
        log_error(f"View Team Members Error: {str(e)}")
        flash('An error occurred while trying to retrieve team members.', 'danger')
        return redirect(url_for('main.dashboard'))
@main_routes.route('/confirm_leave_team/<int:team_id>', methods=['GET', 'POST'])
def confirm_leave_team(team_id):
    user_id = session.get('user_id')
    if not user_id:
        flash('You must be logged in to leave a team.')
        return redirect(url_for('main.login'))
    if request.method == 'POST':
        return leave_team() 
    return render_template('confirm_leave_team.html', team_id=team_id)
@main_routes.route('/all_teams', methods=['GET'])
def all_teams():
    user_id = session.get('user_id')
    if not user_id:
        flash('You must be logged in to view all teams.')
        return redirect(url_for('main.login'))
    teams = get_available_teams()
    return render_template('all_teams.html', teams=teams)
@main_routes.route('/send_message/<int:team_id>', methods=['GET', 'POST'])
def send_message(team_id):
    user_id = session.get('user_id')
    if not user_id:
        flash('You must be logged in to send messages.')
        return redirect(url_for('main.login'))
    if request.method == 'POST':
        message = request.form.get('message')
        return redirect(url_for('main.dashboard'))
    return render_template('send_message.html', team_id=team_id)
@main_routes.route('/profile', methods=['GET', 'POST'])
def profile():
    user_id = session.get('user_id')
    if not user_id:
        flash('You must be logged in to view your profile.')
        return redirect(url_for('main.login'))
    if request.method == 'POST':
        new_username = request.form.get('username')
        new_password = request.form.get('password')
        try:
            with mysql.connection.cursor() as cur:
                if new_password:
                    cur.execute(
                        "UPDATE users SET username = %s, password_hash = %s WHERE id = %s",
                        (new_username, generate_password_hash(new_password), user_id)
                    )
                else:
                    cur.execute(
                        "UPDATE users SET username = %s WHERE id = %s",
                        (new_username, user_id)
                    )
                mysql.connection.commit()
            flash('Profile updated successfully!', 'success')
            return redirect(url_for('main.profile'))
        except Exception as e:
            log_error(f"Profile Update Error: {str(e)}")
            flash('An error occurred while updating your profile.', 'danger')
    with mysql.connection.cursor() as cur:
        cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user = cur.fetchone()
    return render_template('profile.html', user=user)
@main_routes.route('/team/<int:team_id>', methods=['GET'])
def view_team(team_id):
    with mysql.connection.cursor() as cur:
        cur.execute("SELECT * FROM teams WHERE id = %s", (team_id,))
        team = cur.fetchone()
        cur.execute("""
            SELECT u.username 
            FROM team_members tm 
            JOIN users u ON tm.user_id = u.id 
            WHERE tm.team_id = %s
        """, (team_id,))
        members = cur.fetchall()
    return render_template('team_detail.html', team=team, members=members)
def get_user_notifications(user_id):
    query = "SELECT * FROM notifications WHERE user_id = %s ORDER BY created_at DESC"
    with mysql.connection.cursor() as cur:
        cur.execute(query, (user_id,))
        notifications = cur.fetchall()
    return notifications
def create_notification(user_id, message):
    try:
        with mysql.connection.cursor() as cur:
            cur.execute("INSERT INTO notifications (user_id, message) VALUES (%s, %s)", (user_id, message))
            mysql.connection.commit()
    except Exception as e:
        mysql.connection.rollback()  
        log_error(f"Notification Creation Error: {str(e)}")
@main_routes.route('/notifications', methods=['GET'])
def notifications():
    user_id = session.get('user_id')
    if not user_id:
        flash('You must be logged in to view notifications.')
        return redirect(url_for('main.login'))
    notifications = get_user_notifications(user_id)
    return render_template('notifications.html', notifications=notifications)
@main_routes.route('/mark_notification_read/<int:notification_id>', methods=['POST'])
def mark_notification_read(notification_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Unauthorized access'}), 403
    try:
        with mysql.connection.cursor() as cur:
            cur.execute("UPDATE notifications SET is_read = TRUE WHERE id = %s AND user_id = %s", (notification_id, user_id))
            mysql.connection.commit()
        return jsonify({'success': 'Notification marked as read'})
    except Exception as e:
        log_error(f"Mark Notification Read Error: {str(e)}")
        return jsonify({'error': 'An error occurred while marking the notification as read'}), 500

@main_routes.route('/get_faculty', methods=['GET'])
def get_faculty():
    with mysql.connection.cursor() as cur:
        cur.execute("SELECT id, username FROM users WHERE role = 'faculty'")
        faculty_members = cur.fetchall()
    return jsonify([{'id': faculty[0], 'username': faculty[1]} for faculty in faculty_members])

#Admin Routes
def view_user_details(user_id):
    with mysql.connection.cursor() as cur:
    # Use parameterized queries to prevent SQL injection
        cur.execute("SELECT id, username, role FROM users WHERE id = %s", (user_id,))
        user = cur.fetchone()
        
        cur.close()
    
    # Return user data if found, else return None
    if user:
        return {"id": user[0], "username": user[1], "role": user[2]}
    else:
        return None  # User not found
from werkzeug.security import generate_password_hash

# Updated add user details
def add_user_details(username, password, role):
    with mysql.connection.cursor() as cur:
        try:
            # Hash the password
            hashed_password = generate_password_hash(password)
            cur.execute("""
                INSERT INTO users (username, password_hash, role)
                VALUES (%s, %s, %s)
            """, (username, hashed_password, role))
            
            mysql.connection.commit()  # Commit the transaction
            return {"message": "User added successfully"}  # Success message
        except Exception as e:
            return {"message": f"Error adding user: {str(e)}"}, 500  # Return error message

# Updated edit user details
def edit_user_details(user_id, username, password, role):
    with mysql.connection.cursor() as cur:
        # Hash the password
        hashed_password = generate_password_hash(password)
        cur.execute("""
            UPDATE users 
            SET username = %s, password_hash = %s, role = %s 
            WHERE id = %s
        """, (username, hashed_password, role, user_id))
        
        mysql.connection.commit()  # Commit the transaction
        return {"message": "User details updated"}  # Update success message

    
@main_routes.route('/admin_dashboard', methods=['GET'])
def admin_dashboard():
    search_query = request.args.get('search', '', type=str)
    current_page = request.args.get('page', 1, type=int)
    users_per_page = 10
    with mysql.connection.cursor() as cur:
        # SQL for pagination and search
        search_sql = """
            SELECT id, username, role FROM users 
            WHERE username LIKE %s OR role LIKE %s 
            LIMIT %s OFFSET %s
        """
        search_pattern = f"%{search_query}%"
        offset = (current_page - 1) * users_per_page
        
        cur.execute(search_sql, (search_pattern, search_pattern, users_per_page, offset))
        users = cur.fetchall()
        
        cur.execute("SELECT COUNT(*) FROM users WHERE username LIKE %s OR role LIKE %s", (search_pattern, search_pattern))
        total_users = cur.fetchone()[0]
        
        cur.close()

        return render_template(
            'admin_dashboard.html',
            users=users,
            total_users=total_users,
            current_page=current_page,
            users_per_page=users_per_page,
            search_query=search_query
        )

# Route to view user details
@main_routes.route('/admin/view_user/<int:user_id>', methods=['GET'])
def view_user_route(user_id):
    user = view_user_details(user_id)
    if user:
        return jsonify({"message": "User details", "user": user})
    else:
        return jsonify({"message": "User not found"}), 404

# Route to edit user details
@main_routes.route('/admin/edit_user/<int:user_id>', methods=['GET', 'POST'])
def edit_user_route(user_id):
    if request.method == 'GET':
        user = view_user_details(user_id)
        if user:
            return render_template('edit_user.html', user=user)
        else:
            return jsonify({"message": "User not found"}), 404
    
    if request.method == 'POST':
        username = request.json.get('username')
        password = request.json.get('password')
        role = request.json.get('role')
        
        updated_user = edit_user_details(user_id, username, password, role)
        if updated_user:
            return jsonify({"message": "User details updated", "user": updated_user})
        else:
            return jsonify({"message": "Error updating user"}), 500

# Route to add a new user
@main_routes.route('/admin/add_user', methods=['GET', 'POST'])
def add_user_route():
    if request.method == 'GET':
        return render_template('add_user.html')
    
    if request.method == 'POST':
        username = request.json.get('username')
        password = request.json.get('password')
        role = request.json.get('role')
        
        result = add_user_details(username, password, role)
        return jsonify(result)