from flask import Flask, render_template, request, redirect, session, flash, jsonify, url_for
import sqlite3, os, hashlib, uuid, json
from datetime import datetime, timedelta
from functools import wraps
from werkzeug.utils import secure_filename
from authlib.integrations.flask_client import OAuth
import stripe
from dotenv import load_dotenv

load_dotenv()
os.environ['AUTHLIB_INSECURE_TRANSPORT'] = 'true'

app = Flask(__name__)
app.secret_key = 'auctionvault_secret_2024'

DATABASE = 'database.db'
UPLOAD_FOLDER = 'static/images/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ── Stripe Setup ──────────────────────────────
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
STRIPE_PUBLISHABLE_KEY = os.getenv('STRIPE_PUBLISHABLE_KEY')
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET')

# ── Razorpay Setup ────────────────────────────
import razorpay
RAZORPAY_KEY_ID = os.getenv('RAZORPAY_KEY_ID', '')
RAZORPAY_KEY_SECRET = os.getenv('RAZORPAY_KEY_SECRET', '')
is_rzp_configured = (
    RAZORPAY_KEY_ID 
    and 'REPLACE' not in RAZORPAY_KEY_ID 
    and RAZORPAY_KEY_SECRET 
    and 'REPLACE' not in RAZORPAY_KEY_SECRET
)

# ── Google OAuth Setup ────────────────────────
oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'},
)

# ── Platform fee defaults ─────────────────────
DEFAULT_PLATFORM_FEE = 5.0   # percent
DEFAULT_PROCESSING_FEE = 2.0 # percent
DEFAULT_MIN_DEPOSIT = 1.0    # rupees


# ══════════════════════════════════════════════
#  DB helpers
# ══════════════════════════════════════════════
def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT UNIQUE NOT NULL,
            email         TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            profile_pic   TEXT,
            role          TEXT DEFAULT 'user',
            wallet_balance REAL DEFAULT 0.0,
            is_active     INTEGER DEFAULT 1,
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS auctions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            item_name       TEXT NOT NULL,
            description     TEXT,
            starting_price  REAL NOT NULL,
            current_price   REAL NOT NULL,
            host_id         INTEGER NOT NULL,
            start_time      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            end_time        TIMESTAMP NOT NULL,
            status          TEXT DEFAULT 'active',
            image_path      TEXT,
            winner_id       INTEGER,
            final_price     REAL,
            platform_fee    REAL,
            processing_fee  REAL,
            host_payout     REAL,
            settled         INTEGER DEFAULT 0,
            location_name   TEXT DEFAULT 'Guntur, Andhra Pradesh',
            latitude        REAL DEFAULT 16.3067,
            longitude       REAL DEFAULT 80.4365,
            FOREIGN KEY (host_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS bids (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            auction_id      INTEGER NOT NULL,
            bidder_id       INTEGER NOT NULL,
            bid_amount      REAL NOT NULL,
            escrowed_amount REAL DEFAULT 0.0,
            refunded        INTEGER DEFAULT 0,
            timestamp       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (auction_id) REFERENCES auctions(id),
            FOREIGN KEY (bidder_id)  REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS item_history (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            item_name  TEXT NOT NULL,
            sold_price REAL NOT NULL,
            sold_date  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            winner_id  INTEGER,
            FOREIGN KEY (winner_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS transactions (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id           INTEGER NOT NULL,
            amount            REAL NOT NULL,
            type              TEXT NOT NULL,
            category          TEXT NOT NULL,
            description       TEXT,
            reference_id      INTEGER,
            stripe_session_id TEXT,
            created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS platform_settings (
            id              INTEGER PRIMARY KEY,
            platform_fee    REAL DEFAULT 5.0,
            processing_fee  REAL DEFAULT 2.0,
            min_deposit     REAL DEFAULT 100.0,
            updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS withdrawals (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL,
            amount          REAL NOT NULL,
            method          TEXT NOT NULL DEFAULT 'upi',
            upi_id          TEXT,
            account_holder  TEXT,
            account_number  TEXT,
            ifsc_code       TEXT,
            bank_name       TEXT,
            status          TEXT DEFAULT 'pending',
            admin_note      TEXT,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            processed_at    TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS deposits (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL,
            amount          REAL NOT NULL,
            method          TEXT NOT NULL DEFAULT 'upi',
            reference_num   TEXT NOT NULL,
            status          TEXT DEFAULT 'pending',
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            processed_at    TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS deliveries (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            auction_id       INTEGER NOT NULL,
            winner_id        INTEGER NOT NULL,
            house_number     TEXT,
            area             TEXT,
            city             TEXT,
            state            TEXT,
            pincode          TEXT,
            latitude         REAL,
            longitude        REAL,
            status           TEXT DEFAULT 'address_pending',
            delivery_boy_id  INTEGER,
            updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (auction_id) REFERENCES auctions(id),
            FOREIGN KEY (winner_id) REFERENCES users(id),
            FOREIGN KEY (delivery_boy_id) REFERENCES users(id)
        );
    ''')
    conn.commit()

    # ── Upgrade existing DBs: add missing columns safely ──
    upgrades = [
        ('users', 'profile_pic', 'TEXT'),
        ('users', 'role', "TEXT DEFAULT 'user'"),
        ('users', 'wallet_balance', 'REAL DEFAULT 0.0'),
        ('users', 'is_active', 'INTEGER DEFAULT 1'),
        ('auctions', 'winner_id', 'INTEGER'),
        ('auctions', 'final_price', 'REAL'),
        ('auctions', 'platform_fee', 'REAL'),
        ('auctions', 'processing_fee', 'REAL'),
        ('auctions', 'host_payout', 'REAL'),
        ('auctions', 'settled', 'INTEGER DEFAULT 0'),
        ('auctions', 'location_name', "TEXT DEFAULT 'Guntur, Andhra Pradesh'"),
        ('auctions', 'latitude', 'REAL DEFAULT 16.3067'),
        ('auctions', 'longitude', 'REAL DEFAULT 80.4365'),
        ('bids', 'escrowed_amount', 'REAL DEFAULT 0.0'),
        ('bids', 'refunded', 'INTEGER DEFAULT 0'),
    ]
    for table, col, coltype in upgrades:
        try:
            c.execute(f'ALTER TABLE {table} ADD COLUMN {col} {coltype}')
            conn.commit()
        except Exception:
            pass

    # ── Insert default platform settings if not present ──
    c.execute('SELECT COUNT(*) FROM platform_settings')
    if c.fetchone()[0] == 0:
        c.execute('INSERT INTO platform_settings (id, platform_fee, processing_fee, min_deposit) VALUES (1, ?, ?, ?)',
                  (DEFAULT_PLATFORM_FEE, DEFAULT_PROCESSING_FEE, DEFAULT_MIN_DEPOSIT))
        conn.commit()

    # ── Create default admin account if none exists ──
    c.execute("SELECT id FROM users WHERE role='admin'")
    if not c.fetchone():
        admin_hash = hash_password('admin123')
        try:
            c.execute("INSERT INTO users (username, email, password_hash, role, wallet_balance) VALUES (?, ?, ?, 'admin', 0.0)",
                      ('admin', 'admin@auctionhub.com', admin_hash))
            conn.commit()
        except Exception:
            pass

    # ── Create default delivery agent account if none exists ──
    c.execute("SELECT id FROM users WHERE role='delivery_boy'")
    if not c.fetchone():
        delivery_hash = hash_password('delivery123')
        try:
            c.execute("INSERT INTO users (username, email, password_hash, role, wallet_balance) VALUES (?, ?, ?, 'delivery_boy', 0.0)",
                      ('delivery', 'delivery@auctionhub.com', delivery_hash))
            conn.commit()
        except Exception:
            pass

    conn.close()


def hash_password(p):
    return hashlib.sha256(p.encode()).hexdigest()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_platform_fees():
    """Return (platform_fee_pct, processing_fee_pct, min_deposit)"""
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT platform_fee, processing_fee, min_deposit FROM platform_settings WHERE id=1')
    row = c.fetchone()
    conn.close()
    if row:
        return row['platform_fee'], row['processing_fee'], row['min_deposit']
    return DEFAULT_PLATFORM_FEE, DEFAULT_PROCESSING_FEE, DEFAULT_MIN_DEPOSIT


# ══════════════════════════════════════════════
#  Auto-complete expired auctions + settlement
# ══════════════════════════════════════════════
def complete_expired():
    conn = get_db()
    c = conn.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    c.execute("SELECT * FROM auctions WHERE status='active' AND end_time <= ?", (now,))
    expired = c.fetchall()

    platform_fee_pct, processing_fee_pct, _ = get_platform_fees()

    for a in expired:
        row_a = dict(a)
        auction_id = row_a['id']

        # Get highest bid (winner)
        c.execute("SELECT * FROM bids WHERE auction_id=? ORDER BY bid_amount DESC LIMIT 1", (auction_id,))
        top = c.fetchone()

        if top:
            row_top = dict(top)
            winner_id = row_top['bidder_id']
            winning_amount = row_top['bid_amount']

            # Calculate fees
            p_fee = round(winning_amount * platform_fee_pct / 100, 2)
            pr_fee = round(winning_amount * processing_fee_pct / 100, 2)
            host_pay = round(winning_amount - p_fee - pr_fee, 2)

            # ── Transfer winner's escrow to admin ──
            # Get admin user
            c.execute("SELECT id FROM users WHERE role='admin' LIMIT 1")
            admin_row = c.fetchone()
            admin_id = admin_row['id'] if admin_row else None

            if admin_id:
                # Credit admin with full winning amount
                c.execute("UPDATE users SET wallet_balance = wallet_balance + ? WHERE id=?",
                          (winning_amount, admin_id))
                c.execute("INSERT INTO transactions (user_id, amount, type, category, description, reference_id) VALUES (?,?,?,?,?,?)",
                          (admin_id, winning_amount, 'credit', 'auction_win',
                           f'Winning bid received for "{row_a["item_name"]}"', auction_id))

                # Debit admin for platform fee (stays with admin, but tracked)
                c.execute("INSERT INTO transactions (user_id, amount, type, category, description, reference_id) VALUES (?,?,?,?,?,?)",
                          (admin_id, p_fee, 'credit', 'platform_fee',
                           f'Platform fee (5%) on "{row_a["item_name"]}"', auction_id))
                c.execute("INSERT INTO transactions (user_id, amount, type, category, description, reference_id) VALUES (?,?,?,?,?,?)",
                          (admin_id, pr_fee, 'credit', 'processing_fee',
                           f'Processing fee (2%) on "{row_a["item_name"]}"', auction_id))

                # Pay out to host
                c.execute("UPDATE users SET wallet_balance = wallet_balance - ? WHERE id=?",
                          (host_pay, admin_id))
                c.execute("UPDATE users SET wallet_balance = wallet_balance + ? WHERE id=?",
                          (host_pay, row_a['host_id']))
                c.execute("INSERT INTO transactions (user_id, amount, type, category, description, reference_id) VALUES (?,?,?,?,?,?)",
                          (admin_id, host_pay, 'debit', 'host_payout',
                           f'Payout to host for "{row_a["item_name"]}"', auction_id))
                c.execute("INSERT INTO transactions (user_id, amount, type, category, description, reference_id) VALUES (?,?,?,?,?,?)",
                          (row_a['host_id'], host_pay, 'credit', 'host_payout',
                           f'Auction payout for "{row_a["item_name"]}"', auction_id))

            # ── Refund ALL losing bidders ──
            # Get all unique bidders except winner
            c.execute("""SELECT bidder_id, SUM(escrowed_amount) as total_escrowed
                         FROM bids WHERE auction_id=? AND bidder_id != ? AND refunded=0
                         GROUP BY bidder_id""", (auction_id, winner_id))
            losers = c.fetchall()
            for loser in losers:
                loser_d = dict(loser)
                refund_amt = loser_d['total_escrowed']
                if refund_amt > 0:
                    c.execute("UPDATE users SET wallet_balance = wallet_balance + ? WHERE id=?",
                              (refund_amt, loser_d['bidder_id']))
                    c.execute("INSERT INTO transactions (user_id, amount, type, category, description, reference_id) VALUES (?,?,?,?,?,?)",
                              (loser_d['bidder_id'], refund_amt, 'credit', 'bid_refund',
                               f'Bid refund for "{row_a["item_name"]}"', auction_id))
            # Mark all losing bids as refunded
            c.execute("UPDATE bids SET refunded=1 WHERE auction_id=? AND bidder_id != ?",
                      (auction_id, winner_id))

            # Update auction record
            c.execute("""UPDATE auctions SET status='completed', winner_id=?, final_price=?,
                         platform_fee=?, processing_fee=?, host_payout=?, settled=1
                         WHERE id=?""",
                      (winner_id, winning_amount, p_fee, pr_fee, host_pay, auction_id))

            # Item history
            c.execute("INSERT INTO item_history (item_name, sold_price, sold_date, winner_id) VALUES (?,?,?,?)",
                      (row_a['item_name'], winning_amount, now, winner_id))

            # Create delivery record
            c.execute("INSERT INTO deliveries (auction_id, winner_id, status) VALUES (?, ?, 'address_pending')",
                      (auction_id, winner_id))
        else:
            # No bids — just mark completed
            c.execute("UPDATE auctions SET status='completed' WHERE id=?", (auction_id,))

    conn.commit()
    conn.close()


# ══════════════════════════════════════════════
#  Context processor & Auth decorators
# ══════════════════════════════════════════════
@app.context_processor
def inject_profile():
    pic = session.get('profile_pic')
    return dict(user_profile_pic=pic)

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in first.', 'warning')
            return redirect('/login.html')
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in first.', 'warning')
            return redirect('/login.html')
        if session.get('role') != 'admin':
            flash('Admin access required.', 'error')
            return redirect('/index.html')
        return f(*args, **kwargs)
    return decorated

def delivery_boy_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in first.', 'warning')
            return redirect('/login.html')
        if session.get('role') not in ('delivery_boy', 'admin'):
            flash('Delivery agent access required.', 'error')
            return redirect('/index.html')
        return f(*args, **kwargs)
    return decorated


# ══════════════════════════════════════════════
#  API Endpoints
# ══════════════════════════════════════════════
@app.route('/api/user/status')
def api_user_status():
    if 'user_id' in session:
        conn = get_db()
        c = conn.cursor()
        c.execute('SELECT wallet_balance FROM users WHERE id=?', (session['user_id'],))
        row = c.fetchone()
        conn.close()
        balance = row['wallet_balance'] if row else 0.0
        return jsonify({
            'logged_in': True,
            'user_id': session['user_id'],
            'username': session['username'],
            'profile_pic': session.get('profile_pic'),
            'role': session.get('role', 'user'),
            'wallet_balance': balance
        })
    return jsonify({'logged_in': False})


def _get_active_auctions(search='', sort='end_time'):
    complete_expired()
    conn = get_db()
    conn.row_factory = dict_factory
    c = conn.cursor()

    q = '''SELECT a.*, u.username AS host_name,
                  (SELECT COUNT(*) FROM bids b WHERE b.auction_id=a.id) AS bid_count
           FROM auctions a JOIN users u ON a.host_id=u.id
           WHERE a.status='active' '''
    params = []
    if search:
        q += ' AND (a.item_name LIKE ? OR a.description LIKE ?)'
        params += [f'%{search}%', f'%{search}%']

    q += {'price_asc':' ORDER BY a.current_price ASC',
          'price_desc':' ORDER BY a.current_price DESC',
          'newest':' ORDER BY a.start_time DESC'}.get(sort, ' ORDER BY a.end_time ASC')

    c.execute(q, params)
    auctions = c.fetchall()
    conn.close()
    return auctions


@app.route('/api/auctions')
def api_auctions():
    search = request.args.get('search', '')
    sort   = request.args.get('sort', 'end_time')
    auctions = _get_active_auctions(search, sort)
    return jsonify(auctions)


# ══════════════════════════════════════════════
#  Page Routes
# ══════════════════════════════════════════════
@app.route('/')
@app.route('/index.html')
def index():
    return home()

@app.route('/home')
def home():
    complete_expired()
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM auctions WHERE status='active'")
    count = c.fetchone()[0]
    conn.close()
    return render_template('index.html', auction_count=count)

@app.route('/active_auctions.html')
@app.route('/active-auctions')
def active_auctions():
    search = request.args.get('search', '')
    sort   = request.args.get('sort', 'end_time')
    auctions = _get_active_auctions(search, sort)
    return render_template('active_auctions.html', auctions=auctions, search=search, sort=sort)


# ══════════════════════════════════════════════
#  Auth Routes
# ══════════════════════════════════════════════
@app.route('/register.html', methods=['GET','POST'])
@app.route('/register', methods=['GET','POST'])
def register():
    if 'user_id' in session:
        return redirect('/index.html')
    if request.method == 'POST':
        username = request.form.get('username','').strip()
        email    = request.form.get('email','').strip()
        password = request.form.get('password','')
        confirm  = request.form.get('confirm_password','')
        if not username or not email or not password:
            flash('All fields are required.', 'error')
            return render_template('register.html')
        if password != confirm:
            flash('Passwords do not match.', 'error')
            return render_template('register.html')
        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'error')
            return render_template('register.html')
        conn = get_db(); c = conn.cursor()
        c.execute('SELECT id FROM users WHERE username=? OR email=?', (username, email))
        if c.fetchone():
            flash('Username or email already exists.', 'error')
            conn.close()
            return render_template('register.html')
        c.execute('INSERT INTO users (username,email,password_hash,role,wallet_balance) VALUES (?,?,?,?,?)',
                  (username, email, hash_password(password), 'user', 0.0))
        conn.commit()
        uid = c.lastrowid
        conn.close()
        session['user_id'] = uid
        session['username'] = username
        session['profile_pic'] = None
        session['role'] = 'user'
        flash(f'Welcome, {username}!', 'success')
        return redirect('/index.html')
    return render_template('register.html')


@app.route('/login.html', methods=['GET','POST'])
@app.route('/login', methods=['GET','POST'])
def login():
    if 'user_id' in session:
        return redirect('/index.html')
    if request.method == 'POST':
        username = request.form.get('username','').strip()
        password = request.form.get('password','')
        conn = get_db(); c = conn.cursor()
        c.execute('SELECT * FROM users WHERE username=?', (username,))
        user = c.fetchone()
        conn.close()
        if user:
            u_dict = dict(user)
            if u_dict.get('is_active', 1) == 0:
                flash('Your account has been deactivated. Contact admin.', 'error')
                return render_template('login.html')
            if u_dict['password_hash'] == hash_password(password):
                session['user_id'] = u_dict['id']
                session['username'] = u_dict['username']
                session['profile_pic'] = u_dict.get('profile_pic')
                session['role'] = u_dict.get('role', 'user')
                flash(f'Welcome back, {u_dict["username"]}!', 'success')
                if u_dict.get('role') == 'admin':
                    return redirect('/admin')
                return redirect('/index.html')
        flash('Invalid username or password.', 'error')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect('/login.html')


@app.route('/login/google')
def google_login():
    # Force the redirect URI to match what's registered in Google Cloud Console
    redirect_uri = 'http://localhost:5001/auth/google/callback'
    return google.authorize_redirect(redirect_uri)


@app.route('/auth/google/callback')
def google_callback():
    try:
        token = google.authorize_access_token()
    except Exception:
        flash('Google sign-in failed. Please try again.', 'error')
        return redirect('/login.html')

    user_info = token.get('userinfo')
    if not user_info:
        flash('Could not retrieve your Google account info.', 'error')
        return redirect('/login.html')

    email = user_info.get('email', '')
    name  = user_info.get('name', email.split('@')[0])
    if not email:
        flash('No email found in Google account.', 'error')
        return redirect('/login.html')

    conn = get_db(); c = conn.cursor()
    c.execute('SELECT * FROM users WHERE email=?', (email,))
    user = c.fetchone()

    if user:
        u_dict = dict(user)
        if u_dict.get('is_active', 1) == 0:
            flash('Your account has been deactivated. Contact admin.', 'error')
            conn.close()
            return redirect('/login.html')
        session['user_id']  = u_dict['id']
        session['username'] = u_dict['username']
        session['profile_pic'] = u_dict.get('profile_pic')
        session['role'] = u_dict.get('role', 'user')
        flash(f'Welcome back, {u_dict["username"]}!', 'success')
    else:
        username = name.replace(' ', '_').lower()
        c.execute('SELECT id FROM users WHERE username=?', (username,))
        if c.fetchone():
            username = username + '_' + uuid.uuid4().hex[:4]
        random_hash = hashlib.sha256(uuid.uuid4().hex.encode()).hexdigest()
        c.execute('INSERT INTO users (username, email, password_hash, role, wallet_balance) VALUES (?,?,?,?,?)',
                  (username, email, random_hash, 'user', 0.0))
        conn.commit()
        session['user_id']  = c.lastrowid
        session['username'] = username
        session['profile_pic'] = None
        session['role'] = 'user'
        flash(f'Welcome, {username}! Your account has been created with Google.', 'success')

    conn.close()
    return redirect('/index.html')


# ══════════════════════════════════════════════
#  Auction CRUD
# ══════════════════════════════════════════════
@app.route('/create_auction.html', methods=['GET','POST'])
@app.route('/create-auction', methods=['GET','POST'])
@login_required
def create_auction():
    if request.method == 'POST':
        item_name     = request.form.get('item_name','').strip()
        description   = request.form.get('description','').strip()
        starting_price = request.form.get('starting_price','')
        end_time      = request.form.get('end_time','')
        location_name = request.form.get('location_name', 'Guntur, Andhra Pradesh').strip()
        try:
            latitude = float(request.form.get('latitude', 16.3067))
            longitude = float(request.form.get('longitude', 80.4365))
        except (TypeError, ValueError):
            latitude = 16.3067
            longitude = 80.4365

        if not item_name or not starting_price or not end_time:
            flash('Please fill all required fields.', 'error')
            return render_template('create_auction.html')
        try:
            starting_price = float(starting_price)
            if starting_price <= 0: raise ValueError
        except ValueError:
            flash('Starting price must be a positive number.', 'error')
            return render_template('create_auction.html')
        try:
            end_dt = datetime.strptime(end_time, '%Y-%m-%dT%H:%M')
            if end_dt <= datetime.now():
                flash('End time must be in the future.', 'error')
                return render_template('create_auction.html')
        except ValueError:
            flash('Invalid end time.', 'error')
            return render_template('create_auction.html')

        # 6-month restriction check
        conn = get_db(); c = conn.cursor()
        six_months_ago = (datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d %H:%M:%S')
        c.execute("SELECT * FROM item_history WHERE LOWER(item_name)=LOWER(?) AND sold_date>?",
                  (item_name, six_months_ago))
        hist = c.fetchone()
        if hist:
            sold = datetime.strptime(hist['sold_date'], '%Y-%m-%d %H:%M:%S')
            avail = sold + timedelta(days=180)
            flash(f'"{item_name}" was sold on {sold.strftime("%d %b %Y")} and cannot be re-auctioned until {avail.strftime("%d %b %Y")} (6-month rule).', 'error')
            conn.close()
            return render_template('create_auction.html')

        image_path = None
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename and allowed_file(file.filename):
                fname = str(uuid.uuid4()) + '_' + secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
                image_path = 'images/uploads/' + fname

        c.execute('''INSERT INTO auctions
                     (item_name,description,starting_price,current_price,host_id,end_time,image_path,location_name,latitude,longitude)
                     VALUES (?,?,?,?,?,?,?,?,?,?)''',
                  (item_name, description, starting_price, starting_price,
                   session['user_id'], end_dt.strftime('%Y-%m-%d %H:%M:%S'), image_path, location_name, latitude, longitude))
        conn.commit()
        aid = c.lastrowid
        conn.close()
        flash('Auction created successfully!', 'success')
        return redirect(f'/auction_detail.html?id={aid}')
    return render_template('create_auction.html')


@app.route('/auction_detail.html')
@app.route('/auction/<int:auction_id>')
def auction_detail(auction_id=None):
    if auction_id is None:
        return render_template('auction_detail.html', auction=None, bids=[], winner=None)

    complete_expired()
    conn = get_db(); c = conn.cursor()
    c.execute('''SELECT a.*, u.username AS host_name
                 FROM auctions a JOIN users u ON a.host_id=u.id WHERE a.id=?''', (auction_id,))
    auction = c.fetchone()
    if not auction:
        return redirect('/index.html')

    c.execute('''SELECT b.*, u.username AS bidder_name FROM bids b
                 JOIN users u ON b.bidder_id=u.id WHERE b.auction_id=?
                 ORDER BY b.bid_amount DESC''', (auction_id,))
    bids = c.fetchall()
    winner = bids[0] if auction['status'] == 'completed' and bids else None
    conn.close()
    return render_template('auction_detail.html', auction=auction, bids=bids, winner=winner)


# ══════════════════════════════════════════════
#  Place Bid (with escrow)
# ══════════════════════════════════════════════
@app.route('/place-bid', methods=['POST'])
@login_required
def place_bid():
    auction_id = request.form.get('auction_id')
    bid_amount = request.form.get('bid_amount')
    try:
        bid_amount = float(bid_amount)
    except (TypeError, ValueError):
        flash('Invalid bid amount.', 'error')
        return redirect('/index.html')

    conn = get_db(); c = conn.cursor()
    c.execute('SELECT * FROM auctions WHERE id=?', (auction_id,))
    auction = c.fetchone()
    if not auction:
        flash('Auction not found.', 'error'); conn.close(); return redirect('/index.html')
    if auction['status'] != 'active':
        flash('This auction has ended.', 'warning')
        conn.close()
        return redirect(f'/auction_detail.html?id={auction_id}')
    if datetime.now() > datetime.strptime(auction['end_time'], '%Y-%m-%d %H:%M:%S'):
        flash('This auction has ended.', 'warning')
        conn.close()
        return redirect(f'/auction_detail.html?id={auction_id}')
    if auction['host_id'] == session['user_id']:
        flash('You cannot bid on your own auction.', 'warning')
        conn.close()
        return redirect(f'/auction_detail.html?id={auction_id}')
    if bid_amount <= auction['current_price']:
        flash(f'Bid must be higher than current bid of ₹{auction["current_price"]:.2f}.', 'error')
        conn.close()
        return redirect(f'/auction_detail.html?id={auction_id}')

    # ── Escrow logic ──
    # Check how much this bidder already has escrowed on this auction
    c.execute("SELECT SUM(escrowed_amount) as total_escrowed FROM bids WHERE auction_id=? AND bidder_id=? AND refunded=0",
              (auction_id, session['user_id']))
    row = c.fetchone()
    already_escrowed = row['total_escrowed'] if row and row['total_escrowed'] else 0.0

    # Only deduct the difference
    additional_needed = bid_amount - already_escrowed

    # Check wallet balance
    c.execute('SELECT wallet_balance FROM users WHERE id=?', (session['user_id'],))
    user = c.fetchone()
    wallet_balance = user['wallet_balance'] if user else 0.0

    if additional_needed > wallet_balance:
        flash(f'Insufficient wallet balance. You need ₹{additional_needed:.2f} more (already escrowed: ₹{already_escrowed:.2f}). Current balance: ₹{wallet_balance:.2f}.', 'error')
        conn.close()
        return redirect(f'/auction_detail.html?id={auction_id}')

    # Deduct from wallet
    if additional_needed > 0:
        c.execute("UPDATE users SET wallet_balance = wallet_balance - ? WHERE id=?",
                  (additional_needed, session['user_id']))
        # Record escrow transaction
        c.execute("INSERT INTO transactions (user_id, amount, type, category, description, reference_id) VALUES (?,?,?,?,?,?)",
                  (session['user_id'], additional_needed, 'debit', 'bid_escrow',
                   f'Bid escrow for "{auction["item_name"]}" (₹{bid_amount:.2f})', int(auction_id)))

    # Record the bid
    c.execute('INSERT INTO bids (auction_id, bidder_id, bid_amount, escrowed_amount) VALUES (?,?,?,?)',
              (auction_id, session['user_id'], bid_amount, additional_needed))
    c.execute('UPDATE auctions SET current_price=? WHERE id=?', (bid_amount, auction_id))
    conn.commit()
    conn.close()
    flash(f'Bid of ₹{bid_amount:.2f} placed! ₹{additional_needed:.2f} escrowed from wallet.', 'success')
    return redirect(f'/auction_detail.html?id={auction_id}')


# ══════════════════════════════════════════════
#  My Auctions / My Bids
# ══════════════════════════════════════════════
@app.route('/my_auctions.html')
@app.route('/my-auctions')
@login_required
def my_auctions():
    complete_expired()
    conn = get_db(); c = conn.cursor()
    c.execute('''SELECT a.*,
                   (SELECT COUNT(*) FROM bids b WHERE b.auction_id=a.id) AS bid_count,
                   (SELECT u.username FROM bids b JOIN users u ON b.bidder_id=u.id
                    WHERE b.auction_id=a.id ORDER BY b.bid_amount DESC LIMIT 1) AS top_bidder
                 FROM auctions a WHERE a.host_id=? ORDER BY a.start_time DESC''',
              (session['user_id'],))
    auctions = c.fetchall()
    conn.close()
    return render_template('my_auctions.html', auctions=auctions)


@app.route('/my_bids.html')
@app.route('/my-bids')
@login_required
def my_bids():
    complete_expired()
    conn = get_db(); c = conn.cursor()
    c.execute('''SELECT a.*,
                   MAX(b.bid_amount) AS my_highest_bid,
                   (SELECT COUNT(*) FROM bids b2 WHERE b2.auction_id=a.id) AS total_bids,
                   (SELECT b3.bidder_id FROM bids b3 WHERE b3.auction_id=a.id
                    ORDER BY b3.bid_amount DESC LIMIT 1) AS winner_id
                 FROM bids b JOIN auctions a ON b.auction_id=a.id
                 WHERE b.bidder_id=? GROUP BY a.id ORDER BY b.timestamp DESC''',
              (session['user_id'],))
    participated = c.fetchall()
    conn.close()
    return render_template('my_bids.html', participated=participated, user_id=session['user_id'])


# ══════════════════════════════════════════════
#  Profile
# ══════════════════════════════════════════════
@app.route('/profile.html', methods=['GET','POST'])
@app.route('/profile', methods=['GET','POST'])
@login_required
def profile():
    conn = get_db(); c = conn.cursor()
    c.execute('SELECT * FROM users WHERE id=?', (session['user_id'],))
    user = c.fetchone()
    if not user:
        flash('User not found.', 'error')
        conn.close()
        return redirect('/index.html')

    if request.method == 'POST':
        if 'profile_pic' in request.files:
            file = request.files['profile_pic']
            if file and file.filename and allowed_file(file.filename):
                fname = 'profile_' + str(session['user_id']) + '_' + str(uuid.uuid4())[:8] + '_' + secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
                pic_path = 'images/uploads/' + fname
                c.execute('UPDATE users SET profile_pic=? WHERE id=?', (pic_path, session['user_id']))
                conn.commit()
                session['profile_pic'] = pic_path
                flash('Profile picture updated!', 'success')
            else:
                flash('Invalid file type. Use PNG, JPG, GIF, or WEBP.', 'error')
        conn.close()
        return redirect('/profile.html')

    c.execute('SELECT COUNT(*) FROM auctions WHERE host_id=?', (session['user_id'],))
    auction_count = c.fetchone()[0]
    c.execute('SELECT COUNT(DISTINCT auction_id) FROM bids WHERE bidder_id=?', (session['user_id'],))
    bid_count = c.fetchone()[0]
    conn.close()
    return render_template('profile.html', user=user, auction_count=auction_count, bid_count=bid_count)


# ══════════════════════════════════════════════
#  Edit / Delete Auction
# ══════════════════════════════════════════════
@app.route('/auction/<int:auction_id>/edit', methods=['GET','POST'])
@login_required
def edit_auction(auction_id):
    conn = get_db(); c = conn.cursor()
    c.execute('SELECT * FROM auctions WHERE id=?', (auction_id,))
    auction = c.fetchone()
    if not auction:
        flash('Auction not found.', 'error'); conn.close(); return redirect('/my_auctions.html')
    if auction['host_id'] != session['user_id'] and session.get('role') != 'admin':
        flash('You can only edit your own auctions.', 'error'); conn.close(); return redirect('/index.html')
    if auction['status'] != 'active':
        flash('Cannot edit a completed auction.', 'warning'); conn.close(); return redirect(f'/auction_detail.html?id={auction_id}')

    if request.method == 'POST':
        item_name   = request.form.get('item_name','').strip()
        description = request.form.get('description','').strip()
        end_time    = request.form.get('end_time','')
        location_name = request.form.get('location_name', 'Guntur, Andhra Pradesh').strip()
        try:
            latitude = float(request.form.get('latitude', 16.3067))
            longitude = float(request.form.get('longitude', 80.4365))
        except (TypeError, ValueError):
            latitude = 16.3067
            longitude = 80.4365

        if not item_name:
            flash('Item name is required.', 'error')
            conn.close()
            return render_template('edit_auction.html', auction=auction)
        try:
            end_dt = datetime.strptime(end_time, '%Y-%m-%dT%H:%M')
            if end_dt <= datetime.now():
                flash('End time must be in the future.', 'error')
                conn.close()
                return render_template('edit_auction.html', auction=auction)
        except ValueError:
            flash('Invalid end time.', 'error')
            conn.close()
            return render_template('edit_auction.html', auction=auction)

        image_path = auction['image_path']
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename and allowed_file(file.filename):
                fname = str(uuid.uuid4()) + '_' + secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
                image_path = 'images/uploads/' + fname

        c.execute('''UPDATE auctions SET item_name=?, description=?, end_time=?, image_path=?,
                     location_name=?, latitude=?, longitude=?
                     WHERE id=?''',
                  (item_name, description, end_dt.strftime('%Y-%m-%d %H:%M:%S'), image_path,
                   location_name, latitude, longitude, auction_id))
        conn.commit(); conn.close()
        flash('Auction updated successfully!', 'success')
        return redirect(f'/auction_detail.html?id={auction_id}')

    conn.close()
    return render_template('edit_auction.html', auction=auction)


@app.route('/auction/<int:auction_id>/delete', methods=['POST'])
@login_required
def delete_auction(auction_id):
    conn = get_db(); c = conn.cursor()
    c.execute('SELECT * FROM auctions WHERE id=?', (auction_id,))
    auction = c.fetchone()
    if not auction:
        flash('Auction not found.', 'error'); conn.close(); return redirect('/my_auctions.html')
    if auction['host_id'] != session['user_id'] and session.get('role') != 'admin':
        flash('You can only delete your own auctions.', 'error'); conn.close(); return redirect('/index.html')
    c.execute('SELECT COUNT(*) FROM bids WHERE auction_id=?', (auction_id,))
    bid_count = c.fetchone()[0]
    if bid_count > 0:
        flash('Cannot delete an auction that already has bids.', 'error')
        conn.close()
        return redirect(f'/auction_detail.html?id={auction_id}')
    c.execute('DELETE FROM auctions WHERE id=?', (auction_id,))
    conn.commit(); conn.close()
    flash('Auction deleted successfully.', 'success')
    return redirect('/my_auctions.html')


# ══════════════════════════════════════════════
#  Wallet Routes (Stripe/Razorpay)
# ══════════════════════════════════════════════
@app.route('/wallet')
@app.route('/wallet.html')
@login_required
def wallet_page():
    return render_template('wallet.html', stripe_key=STRIPE_PUBLISHABLE_KEY)


@app.route('/wallet/add-funds', methods=['POST'])
@login_required
def wallet_add_funds():
    amount = request.form.get('amount', '')
    payment_method = request.form.get('payment_method', 'card')
    try:
        amount = float(amount)
        _, _, min_dep = get_platform_fees()
        if amount < min_dep:
            flash(f'Minimum deposit is ₹{min_dep:.0f}.', 'error')
            return redirect('/wallet')
    except (TypeError, ValueError):
        flash('Invalid amount.', 'error')
        return redirect('/wallet')

    # ── UPI payments → Razorpay Gateway (with Sandbox fallback) ──
    if payment_method == 'upi':
        load_dotenv()
        rzp_key_id = os.getenv('RAZORPAY_KEY_ID', '').strip()
        rzp_key_secret = os.getenv('RAZORPAY_KEY_SECRET', '').strip()
        
        is_configured = (
            rzp_key_id 
            and 'REPLACE' not in rzp_key_id 
            and rzp_key_secret 
            and 'REPLACE' not in rzp_key_secret
        )

        if not is_configured:
            # Fallback to Sandbox dynamic QR simulator (auto-redirects)
            mock_id = 'mock_' + str(uuid.uuid4())
            session['pending_mock_payment'] = {
                'amount': amount,
                'user_id': session['user_id'],
                'session_id': mock_id,
                'payment_method': 'upi'
            }
            flash('Razorpay API Key is not configured. Redirecting to Sandbox payment simulator.', 'info')
            return redirect(url_for('wallet_mock_checkout'))

        try:
            client = razorpay.Client(auth=(rzp_key_id, rzp_key_secret))
            
            # Store pending deposit details in DB so we can credit it on success callback
            conn = get_db(); c = conn.cursor()
            c.execute("SELECT email, username FROM users WHERE id=?", (session['user_id'],))
            user = c.fetchone()
            email = user['email'] if user else 'user@example.com'
            username = user['username'] if user else 'User'

            # Create Razorpay Payment Link restricting payment options strictly to UPI
            link_data = {
                'amount': int(amount * 100),
                'currency': 'INR',
                'accept_partial': False,
                'description': f'AuctionHub Wallet Deposit (User: {username})',
                'customer': {
                    'name': username,
                    'email': email,
                    'contact': '9398396286'
                },
                'notify': {
                    'sms': False,
                    'email': False
                },
                'reminder_enable': False,
                'callback_url': request.host_url.rstrip('/') + '/wallet/razorpay/callback',
                'callback_method': 'get',
                'options': {
                    'checkout': {
                        'method': {
                            'card': False,
                            'netbanking': False,
                            'wallet': False,
                            'upi': True
                        }
                    }
                }
            }
            
            link = client.payment_link.create(data=link_data)
            payment_link_id = link['id']
            payment_url = link['short_url']
            
            c.execute("""INSERT INTO deposits (user_id, amount, method, reference_num, status)
                         VALUES (?,?,?,?,?)""",
                      (session['user_id'], amount, 'upi', payment_link_id, 'pending'))
            conn.commit(); conn.close()
            
            return redirect(payment_url)
        except Exception as e:
            mock_id = 'mock_' + str(uuid.uuid4())
            session['pending_mock_payment'] = {
                'amount': amount,
                'user_id': session['user_id'],
                'session_id': mock_id,
                'payment_method': 'upi'
            }
            flash(f'Razorpay error: {str(e)}. Redirecting to Sandbox simulator.', 'warning')
            return redirect(url_for('wallet_mock_checkout'))

    # ── Card payments → Stripe Gateway (with Sandbox fallback) ──
    stripe_key = os.getenv('STRIPE_SECRET_KEY', '')
    is_placeholder = not stripe_key or 'REPLACE' in stripe_key or stripe_key.endswith('_KEY')

    if is_placeholder:
        mock_id = 'mock_' + str(uuid.uuid4())
        session['pending_mock_payment'] = {
            'amount': amount,
            'user_id': session['user_id'],
            'session_id': mock_id,
            'payment_method': 'card'
        }
        flash('Stripe not configured. Using Sandbox simulator.', 'info')
        return redirect(url_for('wallet_mock_checkout'))

    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'inr',
                    'product_data': {
                        'name': 'AuctionHub Wallet Top-Up',
                        'description': f'Add ₹{amount:.2f} to your AuctionHub wallet',
                    },
                    'unit_amount': int(amount * 100),
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=request.host_url.rstrip('/') + '/wallet/success?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=request.host_url.rstrip('/') + '/wallet/cancel',
            metadata={
                'user_id': str(session['user_id']),
                'amount': str(amount),
            }
        )
        return redirect(checkout_session.url, code=303)
    except Exception as e:
        mock_id = 'mock_' + str(uuid.uuid4())
        session['pending_mock_payment'] = {
            'amount': amount,
            'user_id': session['user_id'],
            'session_id': mock_id,
            'payment_method': 'card'
        }
        flash(f'Stripe error: {str(e)}. Using Sandbox simulator.', 'warning')
        return redirect(url_for('wallet_mock_checkout'))


@app.route('/wallet/razorpay/callback', methods=['GET'])
@login_required
def wallet_razorpay_callback():
    payment_id = request.args.get('razorpay_payment_id')
    payment_link_id = request.args.get('razorpay_payment_link_id')
    status = request.args.get('razorpay_payment_link_status')
    signature = request.args.get('razorpay_signature')
    
    if not payment_id or not payment_link_id or not signature:
        flash('Invalid checkout response.', 'error')
        return redirect('/wallet')
        
    load_dotenv()
    rzp_key_secret = os.getenv('RAZORPAY_KEY_SECRET', '').strip()
    
    try:
        # Secure signature verification for Payment Links
        import hmac, hashlib
        msg = f"{payment_link_id}|{payment_id}".encode('utf-8')
        expected_sig = hmac.new(rzp_key_secret.encode('utf-8'), msg, hashlib.sha256).hexdigest()
        
        if expected_sig != signature:
            flash('Security signature verification failed.', 'error')
            return redirect('/wallet')
            
        # Credit user's wallet
        conn = get_db(); c = conn.cursor()
        c.execute("SELECT * FROM deposits WHERE reference_num=? AND status='pending'", (payment_link_id,))
        dep = c.fetchone()
        
        if dep:
            amount = dep['amount']
            user_id = dep['user_id']
            
            c.execute("UPDATE users SET wallet_balance = wallet_balance + ? WHERE id=?", (amount, user_id))
            c.execute("UPDATE deposits SET status='approved', processed_at=CURRENT_TIMESTAMP WHERE id=?", (dep['id'],))
            c.execute("""INSERT INTO transactions (user_id, amount, type, category, description)
                         VALUES (?,?,?,?,?)""",
                      (user_id, amount, 'credit', 'deposit', f'UPI Deposit via Razorpay (Link: {payment_link_id})'))
            conn.commit()
            flash(f'₹{amount:.2f} successfully added to your wallet!', 'success')
        else:
            c.execute("SELECT * FROM deposits WHERE reference_num=? AND status='approved'", (payment_link_id,))
            if c.fetchone():
                flash('This deposit was already credited.', 'info')
            else:
                flash('Pending deposit record not found.', 'warning')
            
        conn.close()
    except Exception as e:
        flash(f'Verification failed: {str(e)}', 'error')
        
    return redirect('/wallet')


@app.route('/wallet/mock-checkout')
@login_required
def wallet_mock_checkout():
    pending = session.get('pending_mock_payment')
    if not pending or pending.get('user_id') != session['user_id']:
        flash('No pending payment session found.', 'error')
        return redirect('/wallet')
    
    import urllib.parse
    amount = pending['amount']
    amount_str = f"{amount:.2f}"
    
    # Construct standard UPI deep link
    # pa = payee address, pn = payee name, am = amount, cu = currency, tn = transaction note
    upi_payload = f"upi://pay?pa=9398396286@slc&pn=Mr Bhargav Venkata Siva Ganesh&am={amount_str}&cu=INR&tn=AuctionHub Deposit"
    encoded_upi = urllib.parse.quote(upi_payload)
    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=220x220&data={encoded_upi}"

    return render_template('mock_checkout.html', 
                           amount=amount, 
                           session_id=pending['session_id'],
                           payment_method=pending.get('payment_method', 'card'),
                           qr_url=qr_url)


@app.route('/wallet/success')
@login_required
def wallet_success():
    session_id = request.args.get('session_id')
    if not session_id:
        flash('Invalid payment session.', 'error')
        return redirect('/wallet')

    if session_id.startswith('mock_'):
        pending = session.get('pending_mock_payment')
        if not pending or pending.get('session_id') != session_id or pending.get('user_id') != session['user_id']:
            flash('Mock payment session mismatch or expired.', 'error')
            return redirect('/wallet')
        
        amount = pending['amount']
        user_id = pending['user_id']
        
        conn = get_db(); c = conn.cursor()
        c.execute("SELECT id FROM transactions WHERE stripe_session_id=?", (session_id,))
        if c.fetchone():
            flash('This payment was already processed.', 'info')
            conn.close()
            return redirect('/wallet')

        # Credit wallet
        c.execute("UPDATE users SET wallet_balance = wallet_balance + ? WHERE id=?",
                  (amount, user_id))
        c.execute("""INSERT INTO transactions (user_id, amount, type, category, description, stripe_session_id)
                     VALUES (?,?,?,?,?,?)""",
                  (user_id, amount, 'credit', 'deposit',
                   f'Wallet top-up via Sandbox Simulator (₹{amount:.2f})', session_id))
        conn.commit()
        conn.close()
        
        session.pop('pending_mock_payment', None)
        flash(f'₹{amount:.2f} added to your wallet via Sandbox Simulator!', 'success')
        return redirect('/wallet')

    try:
        checkout = stripe.checkout.Session.retrieve(session_id)
        if checkout.payment_status == 'paid':
            amount = float(checkout.metadata.get('amount', 0))
            user_id = int(checkout.metadata.get('user_id', 0))

            if user_id != session['user_id']:
                flash('Payment session mismatch.', 'error')
                return redirect('/wallet')

            conn = get_db(); c = conn.cursor()
            c.execute("SELECT id FROM transactions WHERE stripe_session_id=?", (session_id,))
            if c.fetchone():
                flash('This payment was already processed.', 'info')
                conn.close()
                return redirect('/wallet')

            # Credit wallet
            c.execute("UPDATE users SET wallet_balance = wallet_balance + ? WHERE id=?",
                      (amount, user_id))
            c.execute("""INSERT INTO transactions (user_id, amount, type, category, description, stripe_session_id)
                         VALUES (?,?,?,?,?,?)""",
                      (user_id, amount, 'credit', 'deposit',
                       f'Wallet top-up via Stripe (₹{amount:.2f})', session_id))
            conn.commit()
            conn.close()
            flash(f'₹{amount:.2f} added to your wallet successfully!', 'success')
        else:
            flash('Payment not completed.', 'warning')
    except Exception as e:
        flash(f'Error verifying payment: {str(e)}', 'error')

    return redirect('/wallet')


@app.route('/wallet/cancel')
@login_required
def wallet_cancel():
    session.pop('pending_mock_payment', None)
    flash('Payment was cancelled.', 'info')
    return redirect('/wallet')



@app.route('/webhook/stripe', methods=['POST'])
def stripe_webhook():
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get('Stripe-Signature')

    try:
        if STRIPE_WEBHOOK_SECRET:
            event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
        else:
            event = json.loads(payload)
    except Exception:
        return jsonify({'error': 'Invalid webhook'}), 400

    if event.get('type') == 'checkout.session.completed':
        sess = event['data']['object']
        if sess.get('payment_status') == 'paid':
            amount = float(sess['metadata'].get('amount', 0))
            user_id = int(sess['metadata'].get('user_id', 0))
            session_id = sess.get('id', '')

            conn = get_db(); c = conn.cursor()
            c.execute("SELECT id FROM transactions WHERE stripe_session_id=?", (session_id,))
            if not c.fetchone():
                c.execute("UPDATE users SET wallet_balance = wallet_balance + ? WHERE id=?",
                          (amount, user_id))
                c.execute("""INSERT INTO transactions (user_id, amount, type, category, description, stripe_session_id)
                             VALUES (?,?,?,?,?,?)""",
                          (user_id, amount, 'credit', 'deposit',
                           f'Wallet top-up via Stripe (₹{amount:.2f})', session_id))
                conn.commit()
            conn.close()

    return jsonify({'status': 'ok'}), 200


@app.route('/api/wallet')
@login_required
def api_wallet():
    conn = get_db(); c = conn.cursor()
    c.execute('SELECT wallet_balance FROM users WHERE id=?', (session['user_id'],))
    user = c.fetchone()
    balance = user['wallet_balance'] if user else 0.0

    conn.row_factory = dict_factory
    c = conn.cursor()
    c.execute("""SELECT * FROM transactions WHERE user_id=?
                 ORDER BY created_at DESC LIMIT 50""", (session['user_id'],))
    txns = c.fetchall()

    c.execute("""SELECT * FROM withdrawals WHERE user_id=?
                 ORDER BY created_at DESC LIMIT 20""", (session['user_id'],))
    withdrawals = c.fetchall()
    conn.close()
    return jsonify({'balance': balance, 'transactions': txns, 'withdrawals': withdrawals})


# ══════════════════════════════════════════════
#  Withdrawal Routes
# ══════════════════════════════════════════════
@app.route('/wallet/withdraw', methods=['POST'])
@login_required
def wallet_withdraw():
    amount = request.form.get('amount', '')
    method = request.form.get('withdraw_method', 'upi')
    upi_id = request.form.get('upi_id', '').strip()
    account_holder = request.form.get('account_holder', '').strip()
    account_number = request.form.get('account_number', '').strip()
    ifsc_code = request.form.get('ifsc_code', '').strip()
    bank_name = request.form.get('bank_name', '').strip()

    try:
        amount = float(amount)
        if amount <= 0:
            flash('Withdrawal amount must be positive.', 'error')
            return redirect('/wallet')
    except (TypeError, ValueError):
        flash('Invalid amount.', 'error')
        return redirect('/wallet')

    # Validate method-specific fields
    if method == 'upi':
        if not upi_id or '@' not in upi_id:
            flash('Please enter a valid UPI ID (e.g. name@upi).', 'error')
            return redirect('/wallet')
    elif method == 'bank':
        if not account_number or not ifsc_code or not account_holder:
            flash('Please fill all bank account details.', 'error')
            return redirect('/wallet')

    conn = get_db(); c = conn.cursor()
    c.execute('SELECT wallet_balance FROM users WHERE id=?', (session['user_id'],))
    user = c.fetchone()
    balance = user['wallet_balance'] if user else 0.0

    if amount > balance:
        flash(f'Insufficient balance. You have ₹{balance:.2f}.', 'error')
        conn.close()
        return redirect('/wallet')

    # Check for pending withdrawals
    c.execute("SELECT COUNT(*) FROM withdrawals WHERE user_id=? AND status='pending'", (session['user_id'],))
    pending_count = c.fetchone()[0]
    if pending_count >= 3:
        flash('You already have 3 pending withdrawal requests. Please wait for them to be processed.', 'warning')
        conn.close()
        return redirect('/wallet')

    # Deduct from wallet and create withdrawal request
    c.execute("UPDATE users SET wallet_balance = wallet_balance - ? WHERE id=?",
              (amount, session['user_id']))
    c.execute("""INSERT INTO withdrawals (user_id, amount, method, upi_id, account_holder, account_number, ifsc_code, bank_name)
                 VALUES (?,?,?,?,?,?,?,?)""",
              (session['user_id'], amount, method, upi_id, account_holder, account_number, ifsc_code, bank_name))
    c.execute("""INSERT INTO transactions (user_id, amount, type, category, description)
                 VALUES (?,?,?,?,?)""",
              (session['user_id'], amount, 'debit', 'withdrawal',
               f'Withdrawal request of ₹{amount:.2f} via {method.upper()}'))
    conn.commit()
    conn.close()
    flash(f'Withdrawal request of ₹{amount:.2f} submitted successfully! It will be processed within 24-48 hours.', 'success')
    return redirect('/wallet')


@app.route('/api/admin/withdrawals')
@admin_required
def api_admin_withdrawals():
    conn = get_db()
    conn.row_factory = dict_factory
    c = conn.cursor()
    c.execute('''SELECT w.*, u.username, u.email
                 FROM withdrawals w JOIN users u ON w.user_id=u.id
                 ORDER BY w.created_at DESC''')
    withdrawals = c.fetchall()
    conn.close()
    return jsonify(withdrawals)


@app.route('/admin/withdrawal/<int:withdrawal_id>/approve', methods=['POST'])
@admin_required
def admin_approve_withdrawal(withdrawal_id):
    conn = get_db(); c = conn.cursor()
    c.execute('SELECT * FROM withdrawals WHERE id=?', (withdrawal_id,))
    w = c.fetchone()
    if not w:
        conn.close()
        return jsonify({'error': 'Withdrawal not found'}), 404
    if w['status'] != 'pending':
        conn.close()
        return jsonify({'error': 'Withdrawal already processed'}), 400
    c.execute("UPDATE withdrawals SET status='approved', processed_at=CURRENT_TIMESTAMP WHERE id=?",
              (withdrawal_id,))
    conn.commit(); conn.close()
    return jsonify({'success': True, 'status': 'approved'})


@app.route('/admin/withdrawal/<int:withdrawal_id>/reject', methods=['POST'])
@admin_required
def admin_reject_withdrawal(withdrawal_id):
    conn = get_db(); c = conn.cursor()
    c.execute('SELECT * FROM withdrawals WHERE id=?', (withdrawal_id,))
    w = c.fetchone()
    if not w:
        conn.close()
        return jsonify({'error': 'Withdrawal not found'}), 404
    if w['status'] != 'pending':
        conn.close()
        return jsonify({'error': 'Withdrawal already processed'}), 400
    # Refund back to wallet
    c.execute("UPDATE users SET wallet_balance = wallet_balance + ? WHERE id=?",
              (w['amount'], w['user_id']))
    c.execute("UPDATE withdrawals SET status='rejected', processed_at=CURRENT_TIMESTAMP WHERE id=?",
              (withdrawal_id,))
    c.execute("""INSERT INTO transactions (user_id, amount, type, category, description)
                 VALUES (?,?,?,?,?)""",
              (w['user_id'], w['amount'], 'credit', 'withdrawal_refund',
               f'Withdrawal rejected — ₹{w["amount"]:.2f} refunded to wallet'))
    conn.commit(); conn.close()
    return jsonify({'success': True, 'status': 'rejected'})


# ══════════════════════════════════════════════
#  Manual Deposit Routes
# ══════════════════════════════════════════════
@app.route('/wallet/submit-deposit', methods=['POST'])
@login_required
def wallet_submit_deposit():
    pending = session.get('pending_mock_payment')
    if not pending or pending.get('user_id') != session['user_id']:
        flash('No pending payment session found.', 'error')
        return redirect('/wallet')

    # UTR no longer required, default to Scan & Pay
    reference_num = request.form.get('reference_num', 'Scan & Pay').strip() or 'Scan & Pay'

    amount = pending['amount']
    method = pending.get('payment_method', 'upi')

    conn = get_db(); c = conn.cursor()
    c.execute("""INSERT INTO deposits (user_id, amount, method, reference_num, status)
                 VALUES (?,?,?,?,?)""",
              (session['user_id'], amount, method, reference_num, 'pending'))
    deposit_id = c.lastrowid
    conn.commit()
    conn.close()

    # Clear pending mock payment from session since it is now persistent
    session.pop('pending_mock_payment', None)

    return redirect(url_for('wallet_waiting_deposit', deposit_id=deposit_id))


@app.route('/wallet/deposit-waiting/<int:deposit_id>')
@login_required
def wallet_waiting_deposit(deposit_id):
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT * FROM deposits WHERE id=? AND user_id=?", (deposit_id, session['user_id']))
    dep = c.fetchone()
    conn.close()

    if not dep:
        flash('Deposit request not found.', 'error')
        return redirect('/wallet')

    if dep['status'] == 'approved':
        flash('Payment verified successfully!', 'success')
        return redirect('/wallet')
    elif dep['status'] == 'rejected':
        flash('Admin rejected the deposit request. Please try again.', 'error')
        return redirect('/wallet')

    return render_template('deposit_waiting.html', deposit=dep)


@app.route('/api/deposit/status/<int:deposit_id>')
@login_required
def api_deposit_status(deposit_id):
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT status FROM deposits WHERE id=? AND user_id=?", (deposit_id, session['user_id']))
    dep = c.fetchone()
    conn.close()
    if not dep:
        return jsonify({'status': 'not_found'}), 404
    return jsonify({'status': dep['status']})


@app.route('/api/admin/deposits')
@admin_required
def api_admin_deposits():
    conn = get_db()
    conn.row_factory = dict_factory
    c = conn.cursor()
    c.execute('''SELECT d.*, u.username, u.email
                 FROM deposits d JOIN users u ON d.user_id=u.id
                 ORDER BY d.created_at DESC''')
    deps = c.fetchall()
    conn.close()
    return jsonify(deps)


@app.route('/admin/deposit/<int:deposit_id>/approve', methods=['POST'])
@admin_required
def admin_approve_deposit(deposit_id):
    conn = get_db(); c = conn.cursor()
    c.execute('SELECT * FROM deposits WHERE id=?', (deposit_id,))
    d = c.fetchone()
    if not d:
        conn.close()
        return jsonify({'error': 'Deposit not found'}), 404
    if d['status'] != 'pending':
        conn.close()
        return jsonify({'error': 'Deposit already processed'}), 400

    # Approve and add to user wallet
    c.execute("UPDATE users SET wallet_balance = wallet_balance + ? WHERE id=?",
              (d['amount'], d['user_id']))
    c.execute("UPDATE deposits SET status='approved', processed_at=CURRENT_TIMESTAMP WHERE id=?",
              (deposit_id,))
    c.execute("""INSERT INTO transactions (user_id, amount, type, category, description)
                 VALUES (?,?,?,?,?)""",
              (d['user_id'], d['amount'], 'credit', 'deposit',
               f'Manual UPI Deposit Approved — UTR: {d["reference_num"]}'))
    conn.commit(); conn.close()
    return jsonify({'success': True, 'status': 'approved'})


@app.route('/admin/deposit/<int:deposit_id>/reject', methods=['POST'])
@admin_required
def admin_reject_deposit(deposit_id):
    conn = get_db(); c = conn.cursor()
    c.execute('SELECT * FROM deposits WHERE id=?', (deposit_id,))
    d = c.fetchone()
    if not d:
        conn.close()
        return jsonify({'error': 'Deposit not found'}), 404
    if d['status'] != 'pending':
        conn.close()
        return jsonify({'error': 'Deposit already processed'}), 400

    c.execute("UPDATE deposits SET status='rejected', processed_at=CURRENT_TIMESTAMP WHERE id=?",
              (deposit_id,))
    conn.commit(); conn.close()
    return jsonify({'success': True, 'status': 'rejected'})


# ══════════════════════════════════════════════
#  Admin Routes
# ══════════════════════════════════════════════
@app.route('/admin')
@app.route('/admin/')
@admin_required
def admin_dashboard():
    return render_template('admin_dashboard.html')


@app.route('/api/admin/stats')
@admin_required
def api_admin_stats():
    conn = get_db(); c = conn.cursor()

    c.execute('SELECT COUNT(*) FROM users')
    total_users = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM users WHERE role='admin'")
    total_admins = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM auctions")
    total_auctions = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM auctions WHERE status='active'")
    active_auctions = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM auctions WHERE status='completed' AND settled=1")
    settled_auctions = c.fetchone()[0]

    c.execute("SELECT COALESCE(SUM(final_price), 0) FROM auctions WHERE settled=1")
    total_revenue = c.fetchone()[0]

    c.execute("SELECT COALESCE(SUM(platform_fee), 0) + COALESCE(SUM(processing_fee), 0) FROM auctions WHERE settled=1")
    platform_earnings = c.fetchone()[0]

    c.execute("SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE category='deposit'")
    total_deposits = c.fetchone()[0]

    c.execute("SELECT wallet_balance FROM users WHERE role='admin' LIMIT 1")
    row = c.fetchone()
    admin_balance = row['wallet_balance'] if row else 0.0

    conn.close()
    return jsonify({
        'total_users': total_users,
        'total_admins': total_admins,
        'total_auctions': total_auctions,
        'active_auctions': active_auctions,
        'settled_auctions': settled_auctions,
        'total_revenue': total_revenue,
        'platform_earnings': platform_earnings,
        'total_deposits': total_deposits,
        'admin_balance': admin_balance,
    })


@app.route('/api/admin/users')
@admin_required
def api_admin_users():
    conn = get_db()
    conn.row_factory = dict_factory
    c = conn.cursor()
    c.execute('''SELECT id, username, email, role, wallet_balance, is_active, created_at
                 FROM users ORDER BY created_at DESC''')
    users = c.fetchall()
    conn.close()
    return jsonify(users)


@app.route('/api/admin/auctions')
@admin_required
def api_admin_auctions():
    conn = get_db()
    conn.row_factory = dict_factory
    c = conn.cursor()
    c.execute('''SELECT a.*, u.username AS host_name,
                    (SELECT COUNT(*) FROM bids WHERE auction_id=a.id) AS bid_count,
                    (SELECT u2.username FROM users u2 WHERE u2.id=a.winner_id) AS winner_name
                 FROM auctions a JOIN users u ON a.host_id=u.id
                 ORDER BY a.start_time DESC''')
    auctions = c.fetchall()
    conn.close()
    return jsonify(auctions)


@app.route('/api/admin/transactions')
@admin_required
def api_admin_transactions():
    conn = get_db()
    conn.row_factory = dict_factory
    c = conn.cursor()
    c.execute('''SELECT t.*, u.username
                 FROM transactions t JOIN users u ON t.user_id=u.id
                 ORDER BY t.created_at DESC LIMIT 200''')
    txns = c.fetchall()
    conn.close()
    return jsonify(txns)


@app.route('/admin/user/<int:user_id>/toggle-status', methods=['POST'])
@admin_required
def admin_toggle_user(user_id):
    if user_id == session['user_id']:
        return jsonify({'error': 'Cannot deactivate yourself'}), 400
    conn = get_db(); c = conn.cursor()
    c.execute('SELECT is_active FROM users WHERE id=?', (user_id,))
    user = c.fetchone()
    if not user:
        conn.close()
        return jsonify({'error': 'User not found'}), 404
    new_status = 0 if user['is_active'] else 1
    c.execute('UPDATE users SET is_active=? WHERE id=?', (new_status, user_id))
    conn.commit(); conn.close()
    return jsonify({'success': True, 'is_active': new_status})


@app.route('/admin/user/<int:user_id>/make-admin', methods=['POST'])
@admin_required
def admin_make_admin(user_id):
    conn = get_db(); c = conn.cursor()
    c.execute('SELECT role FROM users WHERE id=?', (user_id,))
    user = c.fetchone()
    if not user:
        conn.close()
        return jsonify({'error': 'User not found'}), 404
    new_role = 'user' if user['role'] == 'admin' else 'admin'
    if user_id == session['user_id'] and new_role == 'user':
        conn.close()
        return jsonify({'error': 'Cannot demote yourself'}), 400
    c.execute('UPDATE users SET role=? WHERE id=?', (new_role, user_id))
    conn.commit(); conn.close()
    return jsonify({'success': True, 'role': new_role})


@app.route('/admin/auction/<int:auction_id>/cancel', methods=['POST'])
@admin_required
def admin_cancel_auction(auction_id):
    conn = get_db(); c = conn.cursor()
    c.execute('SELECT * FROM auctions WHERE id=?', (auction_id,))
    auction = c.fetchone()
    if not auction:
        conn.close()
        return jsonify({'error': 'Auction not found'}), 404
    if auction['status'] != 'active':
        conn.close()
        return jsonify({'error': 'Auction is not active'}), 400

    a = dict(auction)

    # Refund ALL bidders
    c.execute("""SELECT bidder_id, SUM(escrowed_amount) as total_escrowed
                 FROM bids WHERE auction_id=? AND refunded=0
                 GROUP BY bidder_id""", (auction_id,))
    bidders = c.fetchall()
    for bidder in bidders:
        bd = dict(bidder)
        if bd['total_escrowed'] > 0:
            c.execute("UPDATE users SET wallet_balance = wallet_balance + ? WHERE id=?",
                      (bd['total_escrowed'], bd['bidder_id']))
            c.execute("INSERT INTO transactions (user_id, amount, type, category, description, reference_id) VALUES (?,?,?,?,?,?)",
                      (bd['bidder_id'], bd['total_escrowed'], 'credit', 'bid_refund',
                       f'Auction cancelled by admin: "{a["item_name"]}"', auction_id))

    c.execute("UPDATE bids SET refunded=1 WHERE auction_id=?", (auction_id,))
    c.execute("UPDATE auctions SET status='cancelled' WHERE id=?", (auction_id,))
    conn.commit(); conn.close()
    return jsonify({'success': True})


@app.route('/admin/settings', methods=['POST'])
@admin_required
def admin_update_settings():
    data = request.get_json() or request.form
    platform_fee = float(data.get('platform_fee', DEFAULT_PLATFORM_FEE))
    processing_fee = float(data.get('processing_fee', DEFAULT_PROCESSING_FEE))
    min_deposit = float(data.get('min_deposit', DEFAULT_MIN_DEPOSIT))

    conn = get_db(); c = conn.cursor()
    c.execute("""UPDATE platform_settings SET platform_fee=?, processing_fee=?, min_deposit=?,
                 updated_at=CURRENT_TIMESTAMP WHERE id=1""",
              (platform_fee, processing_fee, min_deposit))
    conn.commit(); conn.close()
    return jsonify({'success': True})


@app.route('/api/admin/settings')
@admin_required
def api_admin_settings():
    p, pr, md = get_platform_fees()
    return jsonify({'platform_fee': p, 'processing_fee': pr, 'min_deposit': md})


# ══════════════════════════════════════════════
#  Static Pages
# ══════════════════════════════════════════════
@app.route('/faq.html')
@app.route('/faq')
def faq():
    return render_template('faq.html')

@app.route('/terms.html')
@app.route('/terms')
def terms():
    return render_template('terms.html')

@app.route('/privacy.html')
@app.route('/privacy')
def privacy():
    return render_template('privacy.html')


# ══════════════════════════════════════════════
#  API Detail Endpoints
# ══════════════════════════════════════════════
@app.route('/api/auction/<int:auction_id>')
def api_auction_detail(auction_id):
    db = get_db()
    auction_row = db.execute('''
        SELECT a.*, u.username as host_name
        FROM auctions a
        JOIN users u ON a.host_id = u.id
        WHERE a.id = ?
    ''', (auction_id,)).fetchone()

    if not auction_row:
        return jsonify({'error': 'Auction not found'}), 404

    auction = dict(auction_row)

    bid_rows = db.execute('''
        SELECT b.*, u.username as bidder_name
        FROM bids b
        JOIN users u ON b.bidder_id = u.id
        WHERE b.auction_id = ?
        ORDER BY b.bid_amount DESC, b.timestamp DESC
    ''', (auction_id,)).fetchall()

    bids = [dict(b) for b in bid_rows]

    winner = None
    if auction['status'] == 'completed' and bids:
        winner = bids[0]

    return jsonify({
        'auction': auction,
        'bids': bids,
        'winner': winner,
        'current_user_id': session.get('user_id')
    })

@app.route('/api/profile')
@login_required
def api_profile():
    db = get_db()
    user_id = session['user_id']

    user = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    if not user:
        return jsonify({'error': 'User not found'}), 404

    auction_count = db.execute('SELECT COUNT(*) FROM auctions WHERE host_id = ?', (user_id,)).fetchone()[0]
    bid_count = db.execute('SELECT COUNT(*) FROM bids WHERE bidder_id = ?', (user_id,)).fetchone()[0]

    user_dict = dict(user)
    # Don't leak password hash
    user_dict.pop('password_hash', None)

    return jsonify({
        'user': user_dict,
        'auction_count': auction_count,
        'bid_count': bid_count
    })

@app.route('/api/my-auctions')
@login_required
def api_my_auctions():
    db = get_db()
    user_id = session['user_id']
    rows = db.execute('''
        SELECT a.*, (SELECT COUNT(*) FROM bids WHERE auction_id = a.id) as bid_count
        FROM auctions a
        WHERE a.host_id = ?
        ORDER BY a.start_time DESC
    ''', (user_id,)).fetchall()
    return jsonify([dict(r) for r in rows])

@app.route('/api/my-bids')
@login_required
def api_my_bids():
    db = get_db()
    user_id = session['user_id']
    rows = db.execute('''
        SELECT DISTINCT a.id, a.item_name, a.current_price, a.status,
               (SELECT MAX(bid_amount) FROM bids WHERE auction_id = a.id AND bidder_id = ?) as my_highest_bid,
               d.id AS delivery_id, d.status AS delivery_status
        FROM auctions a
        JOIN bids b ON a.id = b.auction_id
        LEFT JOIN deliveries d ON a.id = d.auction_id
        WHERE b.bidder_id = ?
        ORDER BY b.timestamp DESC
    ''', (user_id, user_id)).fetchall()
    return jsonify([dict(r) for r in rows])


# ══════════════════════════════════════════════
#  Delivery Routes & APIs
# ══════════════════════════════════════════════

@app.route('/delivery/<int:delivery_id>/address')
@login_required
def delivery_address_page(delivery_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('''SELECT d.*, a.item_name, a.latitude as item_lat, a.longitude as item_lng 
                 FROM deliveries d 
                 JOIN auctions a ON d.auction_id = a.id 
                 WHERE d.id = ?''', (delivery_id,))
    d = c.fetchone()
    conn.close()
    if not d:
        flash('Delivery record not found.', 'error')
        return redirect('/my_bids.html')
    if d['winner_id'] != session['user_id']:
        flash('Unauthorized access.', 'error')
        return redirect('/index.html')
    return render_template('delivery_address.html', delivery=d)


@app.route('/delivery/<int:delivery_id>/track')
@login_required
def delivery_track_page(delivery_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('''SELECT d.*, a.item_name, a.image_path, a.current_price,
                        a.latitude as origin_lat, a.longitude as origin_lng,
                        u.username as host_name
                 FROM deliveries d 
                 JOIN auctions a ON d.auction_id = a.id 
                 JOIN users u ON a.host_id = u.id
                 WHERE d.id = ?''', (delivery_id,))
    d = c.fetchone()
    conn.close()
    if not d:
        flash('Delivery record not found.', 'error')
        return redirect('/my_bids.html')
    if d['winner_id'] != session['user_id'] and session.get('role') != 'admin':
        flash('Unauthorized access.', 'error')
        return redirect('/index.html')
    return render_template('track_order.html', delivery=d)


@app.route('/delivery-dashboard')
@delivery_boy_required
def delivery_dashboard_page():
    return render_template('delivery_dashboard.html')


@app.route('/delivery/scan')
@delivery_boy_required
def delivery_scan_page():
    return render_template('delivery_scan.html')


@app.route('/api/delivery/<int:delivery_id>', methods=['GET'])
@login_required
def api_delivery_detail(delivery_id):
    conn = get_db()
    conn.row_factory = dict_factory
    c = conn.cursor()
    c.execute('''SELECT d.*, a.item_name, a.image_path, a.current_price,
                        a.latitude as origin_lat, a.longitude as origin_lng,
                        u.username as host_name,
                        u2.username as delivery_boy_name
                 FROM deliveries d 
                 JOIN auctions a ON d.auction_id = a.id 
                 JOIN users u ON a.host_id = u.id
                 LEFT JOIN users u2 ON d.delivery_boy_id = u2.id
                 WHERE d.id = ?''', (delivery_id,))
    d = c.fetchone()
    conn.close()
    if not d:
        return jsonify({'error': 'Delivery not found'}), 404
    if d['winner_id'] != session['user_id'] and session.get('role') not in ('admin', 'delivery_boy'):
        return jsonify({'error': 'Unauthorized'}), 403
    return jsonify(d)


@app.route('/api/delivery/<int:delivery_id>/address', methods=['POST'])
@login_required
def api_save_delivery_address(delivery_id):
    data = request.get_json() or request.form
    house_number = data.get('house_number', '').strip()
    area = data.get('area', '').strip()
    city = data.get('city', '').strip()
    state = data.get('state', '').strip()
    pincode = data.get('pincode', '').strip()
    
    try:
        latitude = float(data.get('latitude'))
        longitude = float(data.get('longitude'))
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid latitude/longitude coordinates'}), 400

    if not house_number or not area or not city or not state or not pincode:
        return jsonify({'error': 'All address fields are required'}), 400

    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM deliveries WHERE id = ?', (delivery_id,))
    d = c.fetchone()
    if not d:
        conn.close()
        return jsonify({'error': 'Delivery record not found'}), 404
    if d['winner_id'] != session['user_id']:
        conn.close()
        return jsonify({'error': 'Unauthorized'}), 403

    c.execute('''UPDATE deliveries 
                 SET house_number=?, area=?, city=?, state=?, pincode=?, latitude=?, longitude=?, status='ready_for_dispatch', updated_at=CURRENT_TIMESTAMP
                 WHERE id=?''',
              (house_number, area, city, state, pincode, latitude, longitude, delivery_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'status': 'ready_for_dispatch'})


@app.route('/api/delivery/list', methods=['GET'])
@delivery_boy_required
def api_delivery_list():
    conn = get_db()
    conn.row_factory = dict_factory
    c = conn.cursor()
    c.execute('''SELECT d.*, a.item_name, a.image_path, a.current_price,
                        a.latitude as origin_lat, a.longitude as origin_lng,
                        u.username as host_name
                 FROM deliveries d 
                 JOIN auctions a ON d.auction_id = a.id 
                 JOIN users u ON a.host_id = u.id
                 ORDER BY d.updated_at DESC''')
    deliveries = c.fetchall()
    conn.close()
    return jsonify(deliveries)


@app.route('/api/delivery/<int:delivery_id>/dispatch', methods=['POST'])
@delivery_boy_required
def api_dispatch_delivery(delivery_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM deliveries WHERE id = ?', (delivery_id,))
    d = c.fetchone()
    if not d:
        conn.close()
        return jsonify({'error': 'Delivery record not found'}), 404
    if d['status'] != 'ready_for_dispatch':
        conn.close()
        return jsonify({'error': f'Cannot dispatch delivery in status {d["status"]}'}), 400

    c.execute('''UPDATE deliveries 
                 SET status='out_for_delivery', delivery_boy_id=?, updated_at=CURRENT_TIMESTAMP 
                 WHERE id=?''', (session['user_id'], delivery_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'status': 'out_for_delivery'})


@app.route('/api/delivery/<int:delivery_id>/deliver', methods=['POST'])
@delivery_boy_required
def api_complete_delivery(delivery_id):
    data = request.get_json() or request.form
    token = data.get('token', '').strip()
    expected_token = f"delivery_verify_{delivery_id}"
    
    if token != expected_token:
        return jsonify({'error': 'Invalid QR confirmation token'}), 400

    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM deliveries WHERE id = ?', (delivery_id,))
    d = c.fetchone()
    if not d:
        conn.close()
        return jsonify({'error': 'Delivery record not found'}), 404
    if d['status'] != 'out_for_delivery':
        conn.close()
        return jsonify({'error': f'Cannot deliver package in status {d["status"]}'}), 400

    c.execute('''UPDATE deliveries 
                 SET status='delivered', updated_at=CURRENT_TIMESTAMP 
                 WHERE id=?''', (delivery_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'status': 'delivered'})


@app.route('/admin/user/<int:user_id>/set-role', methods=['POST'])
@admin_required
def admin_set_user_role(user_id):
    data = request.get_json() or request.form
    role = data.get('role', 'user')
    if role not in ('user', 'admin', 'delivery_boy'):
        return jsonify({'error': 'Invalid role'}), 400
    if user_id == session['user_id'] and role != 'admin':
        return jsonify({'error': 'Cannot demote yourself'}), 400
        
    conn = get_db(); c = conn.cursor()
    c.execute('SELECT id FROM users WHERE id=?', (user_id,))
    if not c.fetchone():
        conn.close()
        return jsonify({'error': 'User not found'}), 404
    c.execute('UPDATE users SET role=? WHERE id=?', (role, user_id))
    conn.commit(); conn.close()
    return jsonify({'success': True, 'role': role})


if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5001)
