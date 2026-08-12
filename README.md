# 🔨 AuctionHub - Real-Time Auction & Digital Escrow Platform

[![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0+-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![SQLite](https://img.shields.io/badge/SQLite-3-003B57?style=for-the-badge&logo=sqlite&logoColor=white)](https://www.sqlite.org/)
[![Stripe](https://img.shields.io/badge/Stripe-Integration-635BFF?style=for-the-badge&logo=stripe&logoColor=white)](https://stripe.com/)
[![Razorpay](https://img.shields.io/badge/Razorpay-Integration-0C2340?style=for-the-badge&logo=razorpay&logoColor=blue)](https://razorpay.com/)

**AuctionHub** is a feature-rich, full-stack Web Application designed for live online bidding, seamless digital escrow payments, host payout automation, and end-to-end order delivery tracking. 

Built using Python Flask and modern vanilla web technologies, AuctionHub empowers buyers and sellers with instant automated refunds, real-time bid updates, dual payment gateways (Stripe & Razorpay), Google OAuth, and an enterprise-ready administrative management portal.

---

## ✨ Key Features

### 🔨 Live Auction & Bidding System
* **Real-time Bidding**: Instant bid placement with minimum increment checks.
* **Escrow Holding**: Bidding holds funds directly from user wallets in escrow to eliminate unbacked bids.
* **Instant Outbid Refunds**: When a higher bid is placed, the previous top bidder's wallet is credited immediately.
* **Automated Settlement**: Winning bid amounts are finalized at auction expiration, automatically distributing host payouts and deducting platform fees.

### 💳 Digital Wallet & Escrow Ledger
* **Wallet Management**: Track available balance, pending escrow, and full transaction history.
* **Multi-Gateway Top-Ups**: Fund digital wallets using **Stripe Checkout**, **Razorpay**, or direct simulated deposit flows.
* **Automatic Revenue Splitting**: Configurable system fees (Default: **5% Platform Fee + 2% Processing Charge = 7% Total**). The remaining 93% is paid out to the auction host upon completion.

### 📦 Order Tracking & Delivery Management
* **Post-Auction Delivery Setup**: Sellers specify shipping origin and buyers set destination addresses.
* **Live Order Tracking**: Milestone progress bars (Order Placed -> Shipped -> Out for Delivery -> Delivered).
* **Delivery QR Code Scanner**: Scan-to-verify delivery flow (`delivery_scan.html`) for delivery personnel to validate item handoff securely.

### 🔐 Dual Authentication & User Profiles
* **Google OAuth 2.0 Integration**: One-click login and registration via Google.
* **Native Security**: Hashed passwords (`werkzeug.security`) with robust session control.
* **User Dashboards**: Custom profiles, active bids, hosted auctions, watchlist, and personalized notifications.

### 🛡️ Admin Moderation Dashboard
* **User Governance**: View all registered users, toggle active/inactive status, or grant admin permissions.
* **Auction Moderation**: Monitor live listings, force-cancel fraudulent auctions, and inspect winning payouts.
* **Platform Fee Controls**: Dynamically configure platform fee percentage, processing charges, and minimum deposit limits.

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Python 3.9+, Flask |
| **Database** | SQLite3 with raw SQL schema & transaction management |
| **Authentication** | Google OAuth 2.0 (Authlib), Werkzeug Security |
| **Payments** | Stripe API (Webhooks & Sessions), Razorpay API |
| **Frontend** | HTML5, Modern CSS3 (Glassmorphic dark themes, dynamic UI), JavaScript (Vanilla ES6), Jinja2 |
| **Deployment** | Gunicorn (`build.sh`) |

---

## 📁 Repository Structure

```
AuctionHub/
├── app.py                  # Main Flask application (Routes, DB Init, Auth, Payments, Logic)
├── database.db             # SQLite Database (Auto-generated on first run)
├── requirements.txt        # Python package dependencies
├── build.sh                # Production deployment script
├── .env                    # Environment configuration file (Secrets & API Keys)
├── static/                 # Static assets
│   ├── css/                # Custom stylesheets & animations
│   ├── js/                 # Client-side JavaScript helpers
│   └── images/             # Uploaded product images & icons
└── templates/              # HTML Jinja2 Templates
    ├── active_auctions.html
    ├── admin_dashboard.html
    ├── auction_detail.html
    ├── base.html
    ├── create_auction.html
    ├── delivery_address.html
    ├── delivery_dashboard.html
    ├── delivery_scan.html
    ├── edit_auction.html
    ├── index.html
    ├── login.html
    ├── razorpay_checkout.html
    ├── register.html
    ├── track_order.html
    └── wallet.html
```

---

## 🚀 Quick Start Guide

### Prerequisites
* **Python 3.9+** installed on your system.
* **pip** (Python package installer).
* **Git**.

### 1. Clone the Repository
```bash
git clone https://github.com/your-username/AuctionHub.git
cd AuctionHub
```

### 2. Set Up Virtual Environment
```bash
# On Windows
python -m venv venv
venv\Scripts\activate

# On macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Create a `.env` file in the root directory:

```env
SECRET_KEY=your_random_secret_key

# Google OAuth 2.0 Credentials
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret

# Stripe Payment Gateway
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Razorpay Payment Gateway
RAZORPAY_KEY_ID=rzp_test_...
RAZORPAY_KEY_SECRET=your_razorpay_secret
```

### 5. Run the Application
```bash
python app.py
```
The application will automatically initialize the database schema (`database.db`) on startup and run locally on **`http://127.0.0.1:5000`**.

---

## 🔑 Default Credentials & Roles

* **Default Admin Account**:
  * **Username**: `admin`
  * **Password**: `admin123`
  * *(Note: Change password immediately upon first production deployment).*

---

## 🧪 Payment & Test Mode

* **Simulated Deposits**: If external API keys (Stripe/Razorpay) are not set or in test mode, users can top up their digital wallets using the built-in test wallet top-up interface.
* **Stripe Webhooks**: Listens on `/stripe/webhook` for `checkout.session.completed` events to credit user wallets automatically.

---

## 🤝 Contributing

Contributions are welcome! Follow these steps to contribute:
1. Fork the project.
2. Create a feature branch (`git checkout -b feature/AmazingFeature`).
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`).
4. Push to the branch (`git push origin feature/AmazingFeature`).
5. Open a Pull Request.

---

## 🌿 Git Branching Strategy

This project maintains separated environments:
* **`production`**: Production-ready release code. Live auto-deployment services connect to this branch.
* **`development`**: Active feature development and testing branch. All new work is merged here first before promoting to production.
* **`main`**: Primary repository baseline branch.

---

## 📜 License

Distributed under the MIT License. See `LICENSE` for more information.
