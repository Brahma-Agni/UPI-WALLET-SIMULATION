from flask import Flask, render_template, request, redirect, session, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate # New: For managing database schema changes
from werkzeug.security import generate_password_hash, check_password_hash
import qrcode, os
from datetime import datetime

# Initialize Flask App
app = Flask(__name__)

# --- Configuration ---
# 1. Secret Key: Must be set in the cloud (Vercel/Render) environment variables.
app.secret_key = os.environ.get('SECRET_KEY', 'your_super_secret_key_change_me_in_prod')

# 2. Database URI: Uses the remote DATABASE_URL (PostgreSQL from Neon) in production,
#    and falls back to SQLite for local development.
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL', 
    'sqlite:///db.sqlite3'
).replace("postgres://", "postgresql://", 1) # Vercel sometimes uses 'postgres://', SQLAlchemy requires 'postgresql://'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize SQLAlchemy
db = SQLAlchemy(app)

# Initialize Flask-Migrate
migrate = Migrate(app, db)


# -------------------- MODELS --------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    upi_id = db.Column(db.String(100), unique=True, nullable=False)

    # Relationships
    wallet = db.relationship('Wallet', backref='user', uselist=False, cascade='all, delete-orphan')

    def __repr__(self):
        return f"<User {self.email}>"


class Wallet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True, nullable=False)
    balance = db.Column(db.Float, default=1000.0, nullable=False)

    def __repr__(self):
        return f"<Wallet UserID:{self.user_id} Balance:{self.balance}>"


class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_upi = db.Column(db.String(100), nullable=False)
    receiver_upi = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(255), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<Transaction {self.sender_upi} -> {self.receiver_upi} Amt:{self.amount}>"


# -------------------- QR GENERATION --------------------
def generate_qr(upi_id):
    """Generates a QR code for the given UPI ID and saves it to static/qrcodes/."""
    upi_url = f"upi://pay?pa={upi_id}&pn=WalletUser&cu=INR"
    qr_dir = os.path.join(app.root_path, 'static', 'qrcodes')
    
    # NOTE: In Vercel/Render, the 'static' folder is READ-ONLY in the deployed function.
    # This code will only run successfully during the initial build phase, or locally.
    # If the file does not exist, the app will need to handle a missing QR image URL.
    os.makedirs(qr_dir, exist_ok=True)

    qr_filename = f'{upi_id}.png'
    path = os.path.join(qr_dir, qr_filename)

    if not os.path.exists(path):
        try:
            img = qrcode.make(upi_url)
            img.save(path)
        except Exception as e:
            # Important for deployment: If file creation fails (due to read-only FS), 
            # log the error and return a placeholder path.
            print(f"QR Code generation failed for {upi_id}: {e}")
            return 'qrcodes/placeholder.png' # You might want a default placeholder image

    return f'qrcodes/{qr_filename}'


# -------------------- ROUTES --------------------

@app.route('/')
def index():
    """Renders the home page."""
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    """Handles user registration."""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        name = request.form['name'].strip()
        email = request.form['email'].strip().lower()
        password = request.form['password']

        if not name or not email or not password:
            flash('All fields are required.', 'error')
            return redirect(url_for('register'))

        if User.query.filter_by(email=email).first():
            flash('Email already registered. Please use a different email or log in.', 'error')
            return redirect(url_for('register'))

        # Generate UPI ID logic
        upi_id_base = email.split('@')[0]
        unique_upi_id = f"{upi_id_base}@mockupi"
        counter = 1
        while User.query.filter_by(upi_id=unique_upi_id).first():
            unique_upi_id = f"{upi_id_base}{counter}@mockupi"
            counter += 1

        hashed_password = generate_password_hash(password)

        # Create user and wallet
        user = User(name=name, email=email, password=hashed_password, upi_id=unique_upi_id)
        db.session.add(user)
        db.session.commit()

        wallet = Wallet(user_id=user.id, balance=1000.0)
        db.session.add(wallet)
        db.session.commit()

        # Generate QR code for the new user
        # NOTE: This only works locally or during Vercel build phase. 
        # For production, you might need an S3 bucket or similar service for user-generated content.
        generate_qr(unique_upi_id)

        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handles user login."""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        password = request.form['password']

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            flash(f'Welcome back, {user.name}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password. Please try again.', 'error')

    return render_template('login.html')


@app.route('/dashboard')
def dashboard():
    """Displays user dashboard with wallet balance and QR code."""
    if 'user_id' not in session:
        flash('Please log in to view your dashboard.', 'error')
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    if not user:
        session.clear()
        flash('User not found. Please log in again.', 'error')
        return redirect(url_for('login'))

    wallet = Wallet.query.filter_by(user_id=user.id).first()
    if not wallet:
        flash('Wallet not found for your account. Please contact support.', 'error')
        return redirect(url_for('logout'))

    qr_static_path = generate_qr(user.upi_id)

    return render_template('dashboard.html', user=user, wallet=wallet, qr_path=qr_static_path)


@app.route('/transfer', methods=['POST'])
def transfer():
    """Handles peer-to-peer fund transfer."""
    if 'user_id' not in session:
        flash('Please log in to make a transfer.', 'error')
        return redirect(url_for('login'))

    sender_user = User.query.get(session['user_id'])
    sender_wallet = Wallet.query.filter_by(user_id=sender_user.id).first()

    receiver_upi = request.form.get('recipient_upi_id', '').strip().lower()
    amount_str = request.form.get('amount', '').strip()
    description = request.form.get('description', '').strip()

    # Input validation
    if not receiver_upi or not amount_str:
        flash('Recipient UPI ID and Amount are required.', 'error')
        return redirect(url_for('dashboard'))

    try:
        amount = float(amount_str)
        if amount <= 0:
            flash('Amount must be positive.', 'error')
            return redirect(url_for('dashboard'))
    except ValueError:
        flash('Invalid amount. Please enter a numerical value.', 'error')
        return redirect(url_for('dashboard'))

    if receiver_upi == sender_user.upi_id:
        flash("You cannot send money to yourself.", "error")
        return redirect(url_for('dashboard'))

    receiver_user = User.query.filter_by(upi_id=receiver_upi).first()

    if not receiver_user:
        flash(f'Recipient UPI ID "{receiver_upi}" not found.', 'error')
        return redirect(url_for('dashboard'))

    receiver_wallet = Wallet.query.filter_by(user_id=receiver_user.id).first()
    if not receiver_wallet:
        flash('Recipient wallet not found. Please contact support.', 'error')
        return redirect(url_for('dashboard'))

    if sender_wallet.balance < amount:
        flash('Insufficient balance to complete the transaction.', 'error')
        return redirect(url_for('dashboard'))

    # Perform the transaction within a database session
    try:
        sender_wallet.balance -= amount
        receiver_wallet.balance += amount

        # Create transaction record
        txn = Transaction(
            sender_upi=sender_user.upi_id,
            receiver_upi=receiver_upi,
            amount=amount,
            description=description if description else "UPI Transfer"
        )
        db.session.add(txn)
        db.session.commit()
        flash(f'Successfully sent ₹{amount:.2f} to {receiver_upi}.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'An error occurred during transfer: {e}', 'error')

    return redirect(url_for('dashboard'))


@app.route('/history')
def history():
    """Displays the user's transaction history."""
    if 'user_id' not in session:
        flash('Please log in to view your transaction history.', 'error')
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    if not user:
        session.clear()
        flash('User not found. Please log in again.', 'error')
        return redirect(url_for('login'))

    # Fetch transactions where the current user is either sender or receiver
    transactions = Transaction.query.filter(
        (Transaction.sender_upi == user.upi_id) |
        (Transaction.receiver_upi == user.upi_id)
    ).order_by(Transaction.timestamp.desc()).all()

    return render_template('history.html', transactions=transactions, user=user)


@app.route('/logout')
def logout():
    """Logs the user out."""
    session.clear()
    flash('You have been successfully logged out.', 'success')
    return redirect(url_for('index'))


# --- Deployment Readiness ---
# IMPORTANT: Removed the 'if __name__ == "__main__":' block.
# Vercel/Render will automatically discover the 'app' variable and run it.
# Local execution now requires running 'flask run' in the terminal.
