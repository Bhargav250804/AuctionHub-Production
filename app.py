from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3, os, hashlib, uuid
from datetime import datetime, timedelta
from functools import wraps
from werkzeug.utils import secure_filename
from authlib.integrations.flask_client import OAuth
import os
app = Flask(__name__)
app.secret_key = 'auctionvault_secret_2024'

DATABASE = 'database.db'
UPLOAD_FOLDER = 'static/images/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ── Google OAuth Setup ────────────────────────────────────────
oauth = OAuth(app)
google = oauth.register(
    name='google',
   

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'},
)


# ── DB helpers ────────────────────────────────────────────────
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
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            username     TEXT UNIQUE NOT NULL,
            email        TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            profile_pic  TEXT,
            created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS auctions (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            item_name     TEXT NOT NULL,
            description   TEXT,
            starting_price REAL NOT NULL,
            current_price  REAL NOT NULL,
            host_id       INTEGER NOT NULL,
            start_time    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            end_time      TIMESTAMP NOT NULL,
            status        TEXT DEFAULT 'active',
            image_path    TEXT,
            FOREIGN KEY (host_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS bids (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            auction_id INTEGER NOT NULL,
            bidder_id  INTEGER NOT NULL,
            bid_amount REAL NOT NULL,
            timestamp  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (auction_id) REFERENCES auctions(id),
            FOREIGN KEY (bidder_id)  REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS item_history (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            item_name TEXT NOT NULL,
            sold_price REAL NOT NULL,
            sold_date  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            winner_id  INTEGER,
            FOREIGN KEY (winner_id) REFERENCES users(id)
        );
    ''')
    conn.commit()
    # Add profile_pic column if upgrading existing DB
    try:
        c.execute('ALTER TABLE users ADD COLUMN profile_pic TEXT')
        conn.commit()
    except Exception:
        pass
    conn.close()

def hash_password(p):
    return hashlib.sha256(p.encode()).hexdigest()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ── Auto-complete expired auctions ───────────────────────────
def complete_expired():
    conn = get_db()
    c = conn.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    c.execute("SELECT * FROM auctions WHERE status='active' AND end_time <= ?", (now,))
    for a in c.fetchall():
        row_a = dict(a)
        c.execute("SELECT * FROM bids WHERE auction_id=? ORDER BY bid_amount DESC LIMIT 1", (row_a['id'],))
        top = c.fetchone()
        if top:
            row_top = dict(top)
            c.execute("INSERT INTO item_history (item_name,sold_price,sold_date,winner_id) VALUES (?,?,?,?)",
                      (row_a['item_name'], row_top['bid_amount'], now, row_top['bidder_id']))
        c.execute("UPDATE auctions SET status='completed' WHERE id=?", (row_a['id'],))
    conn.commit()
    conn.close()


# ── Context processor — inject profile pic into all templates ─
@app.context_processor
def inject_profile():
    pic = session.get('profile_pic')
    return dict(user_profile_pic=pic)


# ── Auth decorator ────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in first.', 'warning')
            return redirect('/login.html')
        return f(*args, **kwargs)
    return decorated


# ── API Endpoints ─────────────────────────────────────────────
@app.route('/api/user/status')
def api_user_status():
    if 'user_id' in session:
        return jsonify({
            'logged_in': True,
            'user_id': session['user_id'],
            'username': session['username'],
            'profile_pic': session.get('profile_pic')
        })
    return jsonify({'logged_in': False})


@app.route('/api/auctions')
def api_auctions():
    complete_expired()
    conn = get_db()
    # Temporarily set a different row factory for JSON serialization
    conn.row_factory = dict_factory
    c = conn.cursor()
    
    search = request.args.get('search', '')
    sort   = request.args.get('sort', 'end_time')

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
    return jsonify(auctions)


# ── Routes ────────────────────────────────────────────────────
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
    complete_expired()
    conn = get_db()
    c = conn.cursor()
    search = request.args.get('search', '')
    sort   = request.args.get('sort', 'end_time')

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
    return render_template('active_auctions.html', auctions=auctions, search=search, sort=sort)


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
        c.execute('INSERT INTO users (username,email,password_hash) VALUES (?,?,?)',
                  (username, email, hash_password(password)))
        conn.commit()
        uid = c.lastrowid
        conn.close()
        session['user_id'] = uid
        session['username'] = username
        session['profile_pic'] = None
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
            if u_dict['password_hash'] == hash_password(password):
                session['user_id'] = u_dict['id']
                session['username'] = u_dict['username']
                session['profile_pic'] = u_dict['profile_pic']
                flash(f'Welcome back, {u_dict["username"]}!', 'success')
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
    redirect_uri = url_for('google_callback', _external=True)
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
        # Existing user — log them in
        u_dict = dict(user)
        session['user_id']  = u_dict['id']
        session['username'] = u_dict['username']
        session['profile_pic'] = u_dict['profile_pic']
        flash(f'Welcome back, {u_dict["username"]}!', 'success')
    else:
        # New user — create account with Google info
        username = name.replace(' ', '_').lower()
        # Ensure username uniqueness
        c.execute('SELECT id FROM users WHERE username=?', (username,))
        if c.fetchone():
            username = username + '_' + uuid.uuid4().hex[:4]
        random_hash = hashlib.sha256(uuid.uuid4().hex.encode()).hexdigest()
        c.execute('INSERT INTO users (username, email, password_hash) VALUES (?,?,?)',
                  (username, email, random_hash))
        conn.commit()
        session['user_id']  = c.lastrowid
        session['username'] = username
        session['profile_pic'] = None
        flash(f'Welcome, {username}! Your account has been created with Google.', 'success')

    conn.close()
    return redirect('/index.html')


@app.route('/create_auction.html', methods=['GET','POST'])
@app.route('/create-auction', methods=['GET','POST'])
@login_required
def create_auction():
    if request.method == 'POST':
        item_name     = request.form.get('item_name','').strip()
        description   = request.form.get('description','').strip()
        starting_price = request.form.get('starting_price','')
        end_time      = request.form.get('end_time','')
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
                     (item_name,description,starting_price,current_price,host_id,end_time,image_path)
                     VALUES (?,?,?,?,?,?,?)''',
                  (item_name, description, starting_price, starting_price,
                   session['user_id'], end_dt.strftime('%Y-%m-%d %H:%M:%S'), image_path))
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
    elif datetime.now() > datetime.strptime(auction['end_time'], '%Y-%m-%d %H:%M:%S'):
        flash('This auction has ended.', 'warning')
    elif auction['host_id'] == session['user_id']:
        flash('You cannot bid on your own auction.', 'warning')
    elif bid_amount <= auction['current_price']:
        flash(f'Bid must be higher than current bid of ${auction["current_price"]:.2f}.', 'error')
    else:
        c.execute('INSERT INTO bids (auction_id,bidder_id,bid_amount) VALUES (?,?,?)',
                  (auction_id, session['user_id'], bid_amount))
        c.execute('UPDATE auctions SET current_price=? WHERE id=?', (bid_amount, auction_id))
        conn.commit()
        flash(f'Bid of ${bid_amount:.2f} placed!', 'success')
    conn.close()
    return redirect(f'/auction_detail.html?id={auction_id}')


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

    # Count auctions and bids
    c.execute('SELECT COUNT(*) FROM auctions WHERE host_id=?', (session['user_id'],))
    auction_count = c.fetchone()[0]
    c.execute('SELECT COUNT(DISTINCT auction_id) FROM bids WHERE bidder_id=?', (session['user_id'],))
    bid_count = c.fetchone()[0]
    conn.close()
    return render_template('profile.html', user=user, auction_count=auction_count, bid_count=bid_count)


@app.route('/auction/<int:auction_id>/edit', methods=['GET','POST'])
@login_required
def edit_auction(auction_id):
    conn = get_db(); c = conn.cursor()
    c.execute('SELECT * FROM auctions WHERE id=?', (auction_id,))
    auction = c.fetchone()
    if not auction:
        flash('Auction not found.', 'error'); conn.close(); return redirect('/my_auctions.html')
    if auction['host_id'] != session['user_id']:
        flash('You can only edit your own auctions.', 'error'); conn.close(); return redirect('/index.html')
    if auction['status'] != 'active':
        flash('Cannot edit a completed auction.', 'warning'); conn.close(); return redirect(f'/auction_detail.html?id={auction_id}')

    if request.method == 'POST':
        item_name   = request.form.get('item_name','').strip()
        description = request.form.get('description','').strip()
        end_time    = request.form.get('end_time','')

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

        c.execute('''UPDATE auctions SET item_name=?, description=?, end_time=?, image_path=?
                     WHERE id=?''',
                  (item_name, description, end_dt.strftime('%Y-%m-%d %H:%M:%S'), image_path, auction_id))
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
    if auction['host_id'] != session['user_id']:
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


@app.route('/api/auction/<int:auction_id>')
def api_auction_detail(auction_id):
    db = get_db()
    # Auction query
    auction_row = db.execute('''
        SELECT a.*, u.username as host_name 
        FROM auctions a 
        JOIN users u ON a.host_id = u.id 
        WHERE a.id = ?
    ''', (auction_id,)).fetchone()
    
    if not auction_row:
        return jsonify({'error': 'Auction not found'}), 404
        
    auction = dict(auction_row)
    
    # Bids query
    bid_rows = db.execute('''
        SELECT b.*, u.username as bidder_name 
        FROM bids b 
        JOIN users u ON b.bidder_id = u.id 
        WHERE b.auction_id = ? 
        ORDER BY b.bid_amount DESC, b.timestamp DESC
    ''', (auction_id,)).fetchall()
    
    bids = [dict(b) for b in bid_rows]
    
    # Winner (if completed)
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
    
    # User data
    user = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    if not user:
        return jsonify({'error': 'User not found'}), 404
        
    # Stats
    auction_count = db.execute('SELECT COUNT(*) FROM auctions WHERE host_id = ?', (user_id,)).fetchone()[0]
    bid_count = db.execute('SELECT COUNT(*) FROM bids WHERE bidder_id = ?', (user_id,)).fetchone()[0]
    
    return jsonify({
        'user': dict(user),
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
               (SELECT MAX(bid_amount) FROM bids WHERE auction_id = a.id AND bidder_id = ?) as my_highest_bid
        FROM auctions a
        JOIN bids b ON a.id = b.auction_id
        WHERE b.bidder_id = ?
        ORDER BY b.timestamp DESC
    ''', (user_id, user_id)).fetchall()
    return jsonify([dict(r) for r in rows])

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5001)
