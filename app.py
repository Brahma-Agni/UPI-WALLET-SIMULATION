import os
import qrcode
from datetime import datetime
from flask import Flask, render_template, request, redirect, session, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash

# Initialize Flask App
app = Flask(__name__)

# --- CONFIGURATION ---
# Security: Use environment variable in production
app.secret_key = os.environ.get('SECRET_KEY', 'dev_key_for_local_testing')

# Database: Handle the switch from SQLite to PostgreSQL
# 1. Get the URL from environment (provided by Render/Neon/Vercel)
database_url = os.environ.get('DATABASE_URL', 'sqlite:///db.sqlite3')

# 2. Fix for Cloud Providers: SQLAlchemy requires 'postgresql://', but some providers return 'postgres://'
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize Extensions
db = SQLAlchemy(app)
migrate = Migrate(app, db)  # This enables 'flask db' commands in terminal


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
    # UPDATED: Use Numeric for money, not Float. (10 digits total, 2 decimal places)
    balance = db.Column(db.Numeric(10, 2), default=1000.00, nullable=False)

    def __repr__(self):
        return f"<Wallet UserID:{self.user_id} Balance:{self.balance}>"


class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_upi = db.Column(db.String(100), nullable=False)
    receiver_upi = db.Column(db.String(100), nullable=False)
    # UPDATED: Use Numeric for money
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<Transaction {self.sender_upi} -> {self.receiver_upi} Amt:{self.amount}>"


# -------------------- QR GENERATION --------------------
def generate_qr(upi_id):
    """Generates a QR code for the given UPI ID and saves it to static/qrcodes/."""
    upi_url = f"upi://pay?pa={upi_id}&pn=WalletUser&cu=INR"
    qr_dir = os.path.join(app.root_path, 'static', 'qrcodes')
    os.makedirs(qr_dir, exist_ok=True)

    qr_filename = f'{upi_id}.png'
    path = os.path.join(qr_dir, qr_filename)

    if not os.path.exists(path):
        img = qrcode.make(upi_url)
        img.save(path)

    return f'qrcodes/{qr_filename}'


# -------------------- ROUTES --------------------

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
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
            flash('Email already registered.', 'error')
            return redirect(url_for('register'))

        # Generate UPI ID
        upi_id_base = email.split('@')[0]
        unique_upi_id = f"{upi_id_base}@mockupi"
        counter = 1
        while User.query.filter_by(upi_id=unique_upi_id).first():
            unique_upi_id = f"{upi_id_base}{counter}@mockupi"
            counter += 1

        hashed_password = generate_password_hash(password)

        user = User(name=name, email=email, password=hashed_password, upi_id=unique_upi_id)
        db.session.add(user)
        db.session.commit()

        wallet = Wallet(user_id=user.id, balance=1000.00)
        db.session.add(wallet)
        db.session.commit()

        generate_qr(unique_upi_id)

        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
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
            flash('Invalid email or password.', 'error')

    return render_template('login.html')


@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    if not user:
        session.clear()
        return redirect(url_for('login'))

    wallet = Wallet.query.filter_by(user_id=user.id).first()
    qr_static_path = generate_qr(user.upi_id)

    return render_template('dashboard.html', user=user, wallet=wallet, qr_path=qr_static_path)


@app.route('/transfer', methods=['POST'])
def transfer():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    sender_user = User.query.get(session['user_id'])
    sender_wallet = Wallet.query.filter_by(user_id=sender_user.id).first()

    receiver_upi = request.form.get('recipient_upi_id', '').strip().lower()
    amount_str = request.form.get('amount', '').strip()
    description = request.form.get('description', '').strip()

    if not receiver_upi or not amount_str:
        flash('Recipient and Amount are required.', 'error')
        return redirect(url_for('dashboard'))

    try:
        amount = float(amount_str) # Conversion for check
        if amount <= 0:
            flash('Amount must be positive.', 'error')
            return redirect(url_for('dashboard'))
    except ValueError:
        flash('Invalid amount.', 'error')
        return redirect(url_for('dashboard'))

    if receiver_upi == sender_user.upi_id:
        flash("Cannot send money to yourself.", "error")
        return redirect(url_for('dashboard'))

    receiver_user = User.query.filter_by(upi_id=receiver_upi).first()
    if not receiver_user:
        flash(f'Recipient {receiver_upi} not found.', 'error')
        return redirect(url_for('dashboard'))

    receiver_wallet = Wallet.query.filter_by(user_id=receiver_user.id).first()

    # Note: Use float conversion for comparison, but DB handles Numeric
    if float(sender_wallet.balance) < amount:
        flash('Insufficient balance.', 'error')
        return redirect(url_for('dashboard'))

    try:
        # Perform Transaction
        # SQLAlchemy + Numeric handles the math precision here
        from decimal import Decimal
        amount_decimal = Decimal(amount_str)

        sender_wallet.balance -= amount_decimal
        receiver_wallet.balance += amount_decimal

        txn = Transaction(
            sender_upi=sender_user.upi_id,
            receiver_upi=receiver_upi,
            amount=amount_decimal,
            description=description if description else "UPI Transfer"
        )
        db.session.add(txn)
        db.session.commit()
        flash(f'Successfully sent ₹{amount:.2f} to {receiver_upi}.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Transaction failed: {str(e)}', 'error')

    return redirect(url_for('dashboard'))


@app.route('/history')
def history():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    transactions = Transaction.query.filter(
        (Transaction.sender_upi == user.upi_id) |
        (Transaction.receiver_upi == user.upi_id)
    ).order_by(Transaction.timestamp.desc()).all()

    return render_template('history.html', transactions=transactions, user=user)


@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)