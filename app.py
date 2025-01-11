import base64
import os
from datetime import datetime

import cv2
import numpy as np
import sqlite3
from flask import Flask, request, jsonify, render_template, redirect, url_for, flash
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    login_required,
    logout_user,
    current_user
)
from flask_wtf import FlaskForm
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import InputRequired, Length, ValidationError

app = Flask(__name__)
app.config['SECRET_KEY'] = 'hihihihihihihihihihihihihi'

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'shubham@gmail.com'
app.config['MAIL_PASSWORD'] = 'hihihihihih'

mail = Mail(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

SAVE_DIRECTORY = "captured_eyes"
os.makedirs(SAVE_DIRECTORY, exist_ok=True)


def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            eye_side TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')

    try:
        c.execute("ALTER TABLE images ADD COLUMN iris_radius REAL")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE images ADD COLUMN pupil_diameter REAL")
    except sqlite3.OperationalError:
        pass 
    conn.commit()
    conn.close()

init_db()

def extract_eye_parameters(image_path):
  
    params = {
        'iris_radius': None,
        'pupil_diameter': None
    }

    image = cv2.imread(image_path)
    if image is None:
        print(f"Error: Unable to read image at {image_path}")
        return params

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    gray = clahe.apply(gray)

    gray = cv2.GaussianBlur(gray, (7, 7), 0)

    thresh = cv2.adaptiveThreshold(gray, 255, 
                                   cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                   cv2.THRESH_BINARY_INV, 
                                   11, 2)

    kernel = np.ones((3,3), np.uint8)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=2)

    edges = cv2.Canny(gray, 100, 200)

    combined = cv2.bitwise_or(thresh, edges)

    combined = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, kernel, iterations=1)

    circles = cv2.HoughCircles(
        combined,
        cv2.HOUGH_GRADIENT,
        dp=1.2,          
        minDist=image.shape[1]//4, 
        param1=50,
        param2=30,          
        minRadius=10,     
        maxRadius=40 
    )

    if circles is not None:
        circles = np.uint16(np.around(circles))
        circles = sorted(circles[0], key=lambda x: x[2])
        pupil = circles[0]
        params['pupil_diameter'] = pupil[2] * 2

        if len(circles) > 1:
            iris = circles[1]
            params['iris_radius'] = iris[2]

        cv2.circle(image, (pupil[0], pupil[1]), pupil[2], (0, 255, 0), 2)  
        cv2.circle(image, (pupil[0], pupil[1]), 2, (0, 0, 255), 3)

        if len(circles) > 1:
            cv2.circle(image, (iris[0], iris[1]), iris[2], (255, 0, 0), 2)  
            cv2.circle(image, (iris[0], iris[1]), 2, (0, 0, 255), 3)

        debug_image_path = os.path.join(SAVE_DIRECTORY, f"debug_{os.path.basename(image_path)}")
        cv2.imwrite(debug_image_path, image)
    else:
        print("No circles detected in the eye region.")

    return params


class User(UserMixin):
    def __init__(self, id, username, password):
        self.id = id
        self.username = username
        self.password = password

@login_manager.user_loader
def load_user(user_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = c.fetchone()
    conn.close()
    if user:
        return User(id=user[0], username=user[1], password=user[2])
    return None

class RegisterForm(FlaskForm):
    username = StringField(validators=[InputRequired(), Length(min=4, max=20)],
                           render_kw={"placeholder": "Username"})
    password = PasswordField(validators=[InputRequired(), Length(min=4, max=20)],
                             render_kw={"placeholder": "Password"})
    submit = SubmitField("Register")

    def validate_username(self, username):
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username = ?", (username.data,))
        user = c.fetchone()
        conn.close()
        if user:
            raise ValidationError("Username already exists.")

class LoginForm(FlaskForm):
    username = StringField(validators=[InputRequired(), Length(min=4, max=20)],
                           render_kw={"placeholder": "Username"})
    password = PasswordField(validators=[InputRequired(), Length(min=4, max=20)],
                             render_kw={"placeholder": "Password"})
    submit = SubmitField("Login")

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        hashed_password = generate_password_hash(form.password.data, method='pbkdf2:sha256')
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        try:
            c.execute("INSERT INTO users (username, password) VALUES (?, ?)", 
                      (form.username.data, hashed_password))
            conn.commit()
            flash("Registration successful. Please login.", "success")
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash("Username already exists. Please choose a different one.", "danger")
        finally:
            conn.close()
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username = ?", (form.username.data,))
        user = c.fetchone()
        conn.close()
        if user and check_password_hash(user[2], form.password.data):
            user_obj = User(id=user[0], username=user[1], password=user[2])
            login_user(user_obj)
            flash("Logged in successfully.", "success")
            return redirect(url_for('home'))
        else:
            flash("Invalid username or password.", "danger")
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for('login'))

@app.route('/')
@login_required
def home():
    """Serve the homepage."""
    return render_template('index.html', username=current_user.username)

@app.route('/upload', methods=['POST'])
@login_required
def upload():
    """Process the uploaded base64 image, extract parameters, and save the cropped eye region."""
    try:
        data = request.json
        base64_image = data.get('image', '').split(',')[1]  # Remove data prefix
        image_bytes = base64.b64decode(base64_image)

        # Decode to OpenCV image
        np_arr = np.frombuffer(image_bytes, np.uint8)
        frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        if frame is None:
            return jsonify({'success': False, 'message': 'Invalid image data.'}), 400

        # Retrieve which eye was captured
        eye = data.get('eye', 'left').lower()
        if eye not in ['left', 'right']:
            return jsonify({'success': False, 'message': 'Invalid eye selection.'}), 400

        # Generate a unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{current_user.username}_{eye}_eye_{timestamp}.png"
        filepath = os.path.join(SAVE_DIRECTORY, filename)

        # Save the cropped eye image
        cv2.imwrite(filepath, frame)

        # Extract iris and pupil parameters
        params = extract_eye_parameters(filepath)

        # Store image metadata and parameters in the database
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("""
            INSERT INTO images (user_id, filename, eye_side, iris_radius, pupil_diameter)
            VALUES (?, ?, ?, ?, ?)
        """, (current_user.id, filename, eye, params.get('iris_radius'), params.get('pupil_diameter')))
        conn.commit()
        conn.close()

        return jsonify({
            'success': True,
            'message': 'Eye image saved and parameters extracted successfully.',
            'filename': filename,
            'iris_radius': params.get('iris_radius'),
            'pupil_diameter': params.get('pupil_diameter')
        }), 200

    except Exception as e:
        print(f"Error processing image: {e}")
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500


@app.route('/images')
@login_required
def images():
    """Display all captured images for the logged-in user."""
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT filename, eye_side, timestamp FROM images WHERE user_id = ? ORDER BY timestamp DESC", 
              (current_user.id,))
    images = c.fetchall()
    conn.close()
    return render_template('images.html', images=images)

@app.route('/share/<filename>', methods=['POST'])
@login_required
def share(filename):
    """Share the captured eye image via email."""
    try:
        recipient = request.form.get('email')
        if not recipient:
            return jsonify({'success': False, 'message': 'No recipient email provided.'}), 400

        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("SELECT * FROM images WHERE filename = ? AND user_id = ?", (filename, current_user.id))
        image = c.fetchone()
        conn.close()
        if not image:
            return jsonify({'success': False, 'message': 'Image not found or access denied.'}), 404

        msg = Message('Your Captured Eye Image',
                      sender=app.config['MAIL_USERNAME'],
                      recipients=[recipient])
        msg.body = 'Please find attached your captured eye image.'
        with app.open_resource(os.path.join(SAVE_DIRECTORY, filename)) as fp:
            msg.attach(filename, "image/png", fp.read())
        mail.send(msg)

        return jsonify({'success': True, 'message': 'Email sent successfully.'}), 200

    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500

@app.route('/analytics')
@login_required
def analytics():
    """Display analytics dashboard for the logged-in user."""
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT eye_side, COUNT(*) FROM images WHERE user_id = ? GROUP BY eye_side", (current_user.id,))
    eye_counts = c.fetchall()
    c.execute("SELECT DATE(timestamp) as date, COUNT(*) FROM images WHERE user_id = ? GROUP BY date ORDER BY date", 
              (current_user.id,))
    daily_counts = c.fetchall()
    conn.close()

    eye_labels = [row[0].capitalize() + " Eye" for row in eye_counts]
    eye_data = [row[1] for row in eye_counts]

    daily_labels = [row[0] for row in daily_counts]
    daily_data = [row[1] for row in daily_counts]

    return render_template('analytics.html', eye_labels=eye_labels, eye_data=eye_data,
                           daily_labels=daily_labels, daily_data=daily_data)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
