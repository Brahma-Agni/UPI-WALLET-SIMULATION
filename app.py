import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
import qrcode
from io import BytesIO
import base64

app = Flask(__name__)

# --- CONFIGURATION ---
# Use a strong secret key for sessions (logging in)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'upi-sim-fallback-key-2026')

database_url = os.environ.get('DATABASE_URL')

if database_url:
    # Fix for Dialect naming
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    
    # Fix for Psycopg3 driver compatibility
    if "postgresql://" in database_url and "+psycopg" not in database_url:
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite3'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# --- MODELS ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    upi_id = db.Column(db.String(100), unique=True, nullable=False)
    wallet = db.relationship('Wallet', backref='owner', uselist=False)

class Wallet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    balance = db.Column(db.Numeric(10, 2), default=1000.00)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())

# --- AUTO-TABLE CREATION ---
@app.before_request
def init_db():
    # This creates tables in Neon if they don't exist yet
    db.create_all()

# --- ROUTES ---

@app.route('/')
def index():
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if not user:
            session.clear()
            return redirect(url_for('login'))
            
        # QR code generation (In-memory for Vercel)
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
        username = request.form.get('username')
        password_raw = request.form.get('password')
        
        if User.query.filter_by(username=username).first():
            flash('User already exists!')
            return redirect(url_for('register'))
            
        hashed_pw = generate_password_hash(password_raw)
        upi = f"{username.lower()}@fastpay"
        
        new_user = User(username=username, password=hashed_pw, upi_id=upi)
        db.session.add(new_user)
        db.session.commit()
        
        new_wallet = Wallet(user_id=new_user.id)
        db.session.add(new_wallet)
        db.session.commit()
        
        flash('Registration successful! Please login.')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username')).first()
        if user and check_password_hash(user.password, request.form.get('password')):
            session['user_id'] = user.id
            session.permanent = True # Keep logged in across sessions
            return redirect(url_for('index'))
        flash('Invalid Username or Password')
    return render_template('login.html')

@app.route('/transfer', methods=['POST'])
def transfer():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        amount = float(request.form.get('amount'))
        receiver_upi = request.form.get('upi_id').strip()
        sender = User.query.get(session['user_id'])
        receiver = User.query.filter_by(upi_id=receiver_upi).first()
        
        if not receiver:
            flash('Receiver UPI ID not found.')
        elif sender.upi_id == receiver_upi:
            flash('Cannot transfer to yourself.')
        elif sender.wallet.balance < amount:
            flash('Insufficient balance.')
        else:
            sender.wallet.balance -= amount
            receiver.wallet.balance += amount
            new_tx = Transaction(sender_id=sender.id, receiver_id=receiver.id, amount=amount)
            db.session.add(new_tx)
            db.session.commit()
            flash(f'Successfully sent ₹{amount} to {receiver.username}!')
    except Exception as e:
        flash('Transaction Error. Please try again.')
        
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# Error handler to help debug in Vercel Logs
@app.errorhandler(500)
def handle_500(e):
    return "Internal Server Error. Check Vercel Logs.", 500

# Required for Vercel
app = app

if __name__ == '__main__':
    app.run(debug=True)
