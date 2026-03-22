/**
 * dynamic_ui.js
 * Handles client-side dynamic elements for standalone HTML pages.
 */

document.addEventListener('DOMContentLoaded', () => {
    initDynamicUI();
});

async function initDynamicUI() {
    await updateAuthUI();
    
    // Page specific initializations
    const path = window.location.pathname;
    const search = window.location.search;
    
    // Check if we are on home/index
    if (path === '/home' || path === '/index.html' || path === '/') {
        initHome();
    } else if (path === '/active-auctions' || path === '/active_auctions.html') {
        initActiveAuctions();
    } else if (path.startsWith('/auction/') || path === '/auction_detail.html') {
        initAuctionDetail();
    } else if (path === '/profile' || path === '/profile.html') {
        initProfile();
    } else if (path === '/my_auctions.html' || path === '/my-auctions') {
        initMyAuctions();
    } else if (path === '/my_bids.html' || path === '/my-bids') {
        initMyBids();
    }
}

async function initMyAuctions() {
    const tbody = document.getElementById('my-auctions-tbody');
    if (!tbody) return;

    try {
        const res = await fetch('/api/my-auctions');
        const auctions = await res.json();
        
        if (auctions.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; padding:40px;">You haven\'t created any auctions yet.</td></tr>';
            return;
        }

        tbody.innerHTML = auctions.map(a => `
            <tr>
                <td>${a.item_name}</td>
                <td>₹${parseFloat(a.starting_price).toFixed(2)}</td>
                <td><span class="tbl-price">₹${parseFloat(a.current_price).toFixed(2)}</span></td>
                <td>${a.bid_count}</td>
                <td>${a.end_time.substring(0, 10)}</td>
                <td><span class="badge ${a.status === 'active' ? 'badge-success' : 'badge-gray'}">${a.status.toUpperCase()}</span></td>
                <td><a href="/auction_detail.html?id=${a.id}" class="btn btn-ghost btn-sm">View</a></td>
            </tr>
        `).join('');
    } catch (err) {
        console.error('Failed to load my auctions:', err);
    }
}

async function initMyBids() {
    const grid = document.getElementById('my-bids-grid');
    if (!grid) return;

    try {
        const res = await fetch('/api/my-bids');
        const bids = await res.json();
        
        if (bids.length === 0) {
            grid.innerHTML = '<div class="empty-state" style="grid-column:1/-1; text-align:center; padding:50px;">You haven\'t placed any bids yet.</div>';
            return;
        }

        grid.innerHTML = bids.map(b => `
            <div class="bid-card">
                <div class="bp-title">${b.item_name}</div>
                <div class="bp-prices">
                  <div>My Highest: ₹${parseFloat(b.my_highest_bid).toFixed(2)}</div>
                  <div>Current: ₹${parseFloat(b.current_price).toFixed(2)}</div>
                </div>
                <div style="display:flex; justify-content:space-between; align-items:center; margin-top:12px;">
                  <span class="badge ${b.status === 'active' ? 'badge-success' : 'badge-gray'}">${b.status.toUpperCase()}</span>
                  <a href="/auction_detail.html?id=${b.id}" class="btn btn-ghost btn-sm">View Item</a>
                </div>
            </div>
        `).join('');
    } catch (err) {
        console.error('Failed to load my bids:', err);
    }
}

async function initProfile() {
    const profilePage = document.querySelector('.profile-page');
    if (!profilePage) return;

    try {
        const res = await fetch('/api/profile');
        const data = await res.json();
        
        if (data.error) {
            window.location.href = '/login.html';
            return;
        }

        const u = data.user;
        
        // Update Stats
        document.getElementById('stat-auctions-count').innerText = data.auction_count;
        document.getElementById('stat-bids-count').innerText = data.bid_count;

        // Update Info
        document.getElementById('profile-name').innerText = u.username;
        document.getElementById('profile-email').innerText = `📧 ${u.email}`;
        document.getElementById('profile-joined').innerText = u.created_at ? `📅 Joined ${u.created_at.substring(0, 10)}` : '📅 Joined N/A';

        // Update Pic
        const picCont = document.getElementById('profile-pic-container');
        if (u.profile_pic) {
            picCont.innerHTML = `<img src="/static/${u.profile_pic}" alt="Profile" class="pf-pic">`;
        } else {
            picCont.innerHTML = `<div class="pf-pic pf-pic-default">${u.username[0].toUpperCase()}</div>`;
        }

    } catch (err) {
        console.error('Failed to load profile data:', err);
    }
}

async function initHome() {
    try {
        const res = await fetch('/api/auctions');
        const auctions = await res.json();
        const countVal = document.getElementById('auction-count-val');
        if (countVal) countVal.innerText = auctions.length;
    } catch (err) {
        console.error('Failed to load auctions for home:', err);
    }
}

/**
 * Updates navbar and profile UI based on login status
 */
async function updateAuthUI() {
    try {
        const res = await fetch('/api/user/status');
        const status = await res.json();
        
        const profileDropdown = document.getElementById('profile-dropdown');
        const authLinks = document.querySelectorAll('.nav-auth-link'); // We'll add this class to Sign In/Join Now
        
        if (status.logged_in) {
            // Logged In state
            document.body.classList.add('user-logged-in');
            document.body.classList.remove('user-guest');
            
            if (profileDropdown) profileDropdown.style.display = 'block';

            // Update profile avatar and name
            const avatars = document.querySelectorAll('.profile-avatar, .pm-avatar');
            avatars.forEach(av => {
                if (status.profile_pic) {
                    av.innerHTML = `<img src="/static/${status.profile_pic}" alt="Profile" style="width:100%; height:100%; object-fit:cover;">`;
                    av.classList.remove('profile-avatar-default', 'pm-avatar-default');
                } else {
                    const initial = status.username[0].toUpperCase();
                    av.innerText = initial;
                    av.classList.add('profile-avatar-default', 'pm-avatar-default');
                }
            });
            
            const pmName = document.querySelector('.pm-name');
            if (pmName) pmName.innerText = status.username;
            
            const pmRole = document.querySelector('.pm-role');
            if (pmRole) pmRole.innerText = 'Member';
            
            // Toggle menu items
            document.querySelectorAll('.pm-item-auth').forEach(el => el.style.display = 'none');
            document.querySelectorAll('.pm-item-user').forEach(el => el.style.display = 'flex');
        } else {
            // Guest state
            document.body.classList.add('user-guest');
            document.body.classList.remove('user-logged-in');
            
            if (profileDropdown) profileDropdown.style.display = 'none';

            document.querySelectorAll('.pm-item-auth').forEach(el => el.style.display = 'flex');
            document.querySelectorAll('.pm-item-user').forEach(el => el.style.display = 'none');
        }
    } catch (err) {
        console.error('Auth check failed:', err);
    }
}

/**
 * active_auctions.html logic
 */
async function initActiveAuctions() {
    const grid = document.getElementById('auction-grid');
    if (!grid) return;

    const filterForm = document.getElementById('filter-form');
    if (filterForm) {
        filterForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const formData = new FormData(filterForm);
            const search = formData.get('search');
            const sort = formData.get('sort');
            loadAuctions(search, sort);
        });
    }

    // Initial load
    const params = new URLSearchParams(window.location.search);
    loadAuctions(params.get('search') || '', params.get('sort') || 'end_time');
}

async function loadAuctions(search = '', sort = 'end_time') {
    const grid = document.getElementById('auction-grid');
    const badge = document.getElementById('auction-count-badge');
    
    try {
        const res = await fetch(`/api/auctions?search=${encodeURIComponent(search)}&sort=${sort}`);
        const auctions = await res.json();
        
        if (badge) badge.innerText = `${auctions.length} item(s)`;
        
        if (auctions.length === 0) {
            grid.innerHTML = '<div class="empty-state">No active auctions found.</div>';
            return;
        }

        grid.innerHTML = auctions.map(a => `
            <div class="auction-card">
              <div class="card-img">
                ${a.image_path ? 
                    `<img src="/static/${a.image_path}" alt="${a.item_name}">` : 
                    '<div class="card-img-ph">📦</div>'}
                <div class="card-live-badge"><span class="blink"></span> LIVE</div>
                <div class="card-timer" data-end="${a.end_time}">⏱ …</div>
              </div>
              <div class="card-body">
                <div class="card-meta">
                  <span>👤 ${a.host_name}</span>
                  <span>🔨 ${a.bid_count} bid(s)</span>
                </div>
                <div class="card-title">${a.item_name}</div>
                <div class="card-desc">${a.description || ''}</div>
                <div class="card-prices">
                  <div>
                    <div class="price-lbl">Current Bid</div>
                    <div class="price-big">₹${parseFloat(a.current_price).toFixed(2)}</div>
                  </div>
                  <div style="text-align:right">
                    <div class="price-lbl">Starting</div>
                    <div class="price-sm">₹${parseFloat(a.starting_price).toFixed(2)}</div>
                  </div>
                </div>
                <a href="/auction_detail.html?id=${a.id}" class="btn btn-gold btn-full">Place a Bid →</a>
              </div>
            </div>
        `).join('');
        
    } catch (err) {
        console.error('Failed to load auctions:', err);
        grid.innerHTML = '<div class="error-state">Failed to load auctions. Please try again later.</div>';
    }
}

async function initAuctionDetail() {
    const detailContainer = document.getElementById('detail-main-content');
    if (!detailContainer) return;

    // Get ID from URL (/auction/123 or /auction_detail.html?id=123)
    let auctionId = window.location.pathname.split('/').pop();
    if (isNaN(auctionId)) {
        const params = new URLSearchParams(window.location.search);
        auctionId = params.get('id');
    }

    if (!auctionId) {
        console.error('No auction ID found');
        return;
    }

    loadAuctionDetail(auctionId);
}

async function loadAuctionDetail(id) {
    try {
        const res = await fetch(`/api/auction/${id}`);
        const data = await res.json();
        
        if (data.error) {
            document.querySelector('.detail-layout').innerHTML = `<div class="error-state">${data.error}</div>`;
            return;
        }

        const a = data.auction;
        const bids = data.bids;
        const winner = data.winner;
        const currentUserId = data.current_user_id;

        // Update Text
        document.getElementById('page-title').innerText = `${a.item_name} — AuctionHub`;
        document.getElementById('breadcrumb-item-name').innerText = a.item_name;
        document.getElementById('detail-title').innerText = a.item_name;
        document.getElementById('detail-host').innerHTML = `Hosted by <strong>${a.host_name}</strong>`;
        document.getElementById('detail-start').innerText = `Started ${a.start_time.substring(0, 10)}`;
        document.getElementById('detail-description').innerText = a.description || 'No description provided.';
        document.getElementById('current-bid').innerText = `₹${parseFloat(a.current_price).toFixed(2)}`;
        document.getElementById('starting-price').innerText = `₹${parseFloat(a.starting_price).toFixed(2)}`;
        document.getElementById('bid-history-count').innerText = bids.length;
        document.getElementById('stat-total-bids').innerText = bids.length;
        document.getElementById('stat-highest-bid').innerText = bids.length > 0 ? `₹${parseFloat(bids[0].bid_amount).toFixed(2)}` : '—';
        document.getElementById('stat-end-date').innerText = a.end_time.substring(0, 10);

        // Update Image
        const imgCont = document.getElementById('detail-img-container');
        imgCont.innerHTML = a.image_path ? 
            `<img src="/static/${a.image_path}" alt="${a.item_name}">` : 
            '<div class="detail-img-ph">📦 No Image</div>';
        imgCont.innerHTML += `<div class="detail-status ${a.status === 'active' ? 'ds-active' : 'ds-completed'}">
            ${a.status === 'active' ? 'LIVE AUCTION' : 'COMPLETED'}
        </div>`;

        // Update Bid History
        const bhList = document.getElementById('bid-history-list');
        bhList.innerHTML = bids.map((b, idx) => `
            <div class="bh-item ${idx === 0 ? 'top' : ''}">
                <div class="bh-rank">#${idx + 1}</div>
                <div class="bh-avatar">${b.bidder_name[0].toUpperCase()}</div>
                <div class="bh-name">${b.bidder_name}</div>
                <div class="bh-amount ${idx === 0 ? 'top-amt' : ''}">₹${parseFloat(b.bid_amount).toFixed(2)}</div>
                <div class="bh-time">${b.timestamp.substring(0, 16).replace('T', ' ')}</div>
            </div>
        `).join('');

        // Toggles
        if (a.status === 'active') {
            document.getElementById('countdown-box').style.display = 'block';
            const countdownEl = document.getElementById('main-countdown');
            if (countdownEl) {
                countdownEl.setAttribute('data-end', a.end_time);
                if (typeof initDetailCountdown === 'function') initDetailCountdown();
            }
        } else {
            document.getElementById('ended-msg').style.display = 'block';
        }

        if (winner) {
            document.getElementById('winner-container').style.display = 'block';
            document.getElementById('winner-name').innerText = winner.bidder_name;
            document.getElementById('winner-price').innerText = `Won at ₹${parseFloat(winner.bid_amount).toFixed(2)}`;
        }

        // Form logic
        const bidForm = document.getElementById('bid-form');
        const hostNotice = document.getElementById('host-notice');
        const guestNotice = document.querySelector('.guest-bid-notice');

        if (!currentUserId) {
            guestNotice.style.display = 'flex';
        } else if (currentUserId === a.host_id) {
            hostNotice.style.display = 'block';
        } else if (a.status === 'active') {
            bidForm.style.display = 'block';
            document.getElementById('form-auction-id').value = a.id;
            document.getElementById('bid_amount').min = parseFloat(a.current_price) + 0.01;
            document.getElementById('min-bid-val').innerText = `₹${(parseFloat(a.current_price) + 0.01).toFixed(2)}`;
        }

    } catch (err) {
        console.error('Failed to load auction details:', err);
    }
}
