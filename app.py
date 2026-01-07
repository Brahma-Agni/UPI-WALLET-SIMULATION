import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
import qrcode
from io import BytesIO
import base64

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'upi-sim-fallback-2026')

# --- DATABASE CONFIG ---
database_url = os.environ.get('DATABASE_URL')
if database_url:
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    if "+psycopg" not in database_url:
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite3'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# --- MODELS ---
class User(db.Model):
    __tablename__ = 'users' # Renamed to avoid Postgres 'user' keyword conflict
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    upi_id = db.Column(db.String(100), unique=True, nullable=False)
    wallet = db.relationship('Wallet', backref='owner', uselist=False)

class Wallet(db.Model):
    __tablename__ = 'wallets'
    id = db.Column(db.Integer, primary_key=True)
    balance = db.Column(db.Numeric(10, 2), default=1000.00)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

class Transaction(db.Model):
    __tablename__ = 'transactions'
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    receiver_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())

# --- INIT DB ---
with app.app_context():
    try:
        db.create_all()
    except Exception as e:
        print(f"Database init error: {e}")

# --- ROUTES ---
@app.route('/')
def index():
    if 'user_id' in session:
        user = db.session.get(User, session['user_id'])
        if not user:
            session.clear()
            return redirect(url_for('login'))
        
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(f"upi://pay?pa={user.upi_id}&pn={user.username}")
        qr.make(fit=True)
        img = qr.make_image(fill='black', back_color='white')
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        qr_base64 = base64.b64encode(buffered.getvalue()).decode()
        
        return render_template('dashboard.html', user=user, qr_code=qr_base64)
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username').strip()
        password = generate_password_hash(request.form.get('password'))
        upi_id = f"{username.lower()}@fastpay"
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists!')
            return redirect(url_for('register'))
            
        new_user = User(username=username, password=password, upi_id=upi_id)
        db.session.add(new_user)
        db.session.commit()
        
        db.session.add(Wallet(user_id=new_user.id))
        db.session.commit()
        
        flash('Registration successful!')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username')).first()
        if user and check_password_hash(user.password, request.form.get('password')):
            session['user_id'] = user.id
            return redirect(url_for('index'))
        flash('Invalid login credentials')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

app = app
