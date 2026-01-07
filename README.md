
# UPI Wallet Project (Mock UPI Simulation)

---

## 🚀 Project Overview

This is a **simulated UPI (Unified Payments Interface) wallet-to-wallet payment system** built with Flask. It aims to replicate core functionalities of popular digital payment applications like PhonePe or Google Pay, focusing on secure peer-to-peer fund transfers and QR code-based payment initiation using **mock UPI IDs**.

It serves as a strong demonstration of full-stack web development principles, secure user authentication, database management for financial transactions, and API simulation in a Python environment.

---

## ✨ Key Features

* **User Authentication:** Secure registration and login functionalities with `Werkzeug` for password hashing.
* **Unique UPI IDs:** Each registered user receives a unique `[username]@mockupi` ID for simulated transactions.
* **Personal Wallets:** Every user has an associated digital wallet to manage their balance.
* **Peer-to-Peer Transfers:** Users can send money to other registered `mockupi` IDs with real-time balance updates.
* **Dynamic QR Code Generation:** Generate personalized QR codes for receiving payments, streamlining the payment initiation process.
* **Transaction History:** Comprehensive logging and viewing of all sent and received transactions.
* **Session Management:** Secure handling of user sessions.

---

## 🛠️ Technologies Used

* **Backend:**
    * **Python:** The core programming language.
    * **Flask:** Lightweight web framework for building the application.
    * **Flask-SQLAlchemy:** ORM (Object-Relational Mapper) for database interactions.
    * **Werkzeug:** For secure password hashing.
* **Database:**
    * **SQLite:** Used for local development and can be used with Render Disks for deployment (for production, PostgreSQL is recommended).
* **Frontend:**
    * **HTML5:** Structure of the web pages.
    * **Bootstrap 5:** Responsive CSS framework for styling and components.
* **Payment Simulation:**
    * **`qrcode` library:** For generating dynamic QR codes.

---

## ⚡ Getting Started

Follow these steps to set up and run the project locally.

### Prerequisites

* Python 3.8+
* pip (Python package installer)

### Installation

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/](https://github.com/)[YOUR_USERNAME]/upi-wallet-project.git
    cd upi-wallet-project
    ```
    (Replace `[YOUR_USERNAME]` with your GitHub username)

2.  **Create a virtual environment:**
    ```bash
    python -m venv venv
    ```

3.  **Activate the virtual environment:**
    * **Windows:**
        ```bash
        .\venv\Scripts\activate
        ```
    * **macOS/Linux:**
        ```bash
        source venv/bin/activate
        ```

4.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

5.  **Set Environment Variables:**
    Create a `.env` file in the root of your project and add your `SECRET_KEY`:
    ```
    SECRET_KEY='your_very_secret_and_random_key_here'
    ```
    (Replace with a strong, random key.)

6.  **Initialize the Database:**
    The database (`db.sqlite3`) will be created automatically when you run the application for the first time or when `db.create_all()` is executed. Ensure your `app.py` has `db.create_all()` within an `app.app_context()` block.

### Running the Application

```bash
python app.py
The application will be accessible at http://127.0.0.1:5000
# UPI-WALLET-SIMULATION
