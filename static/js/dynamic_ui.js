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
    } else if (path === '/admin' || path === '/admin/') {
        initAdminDashboard();
    } else if (path === '/wallet' || path === '/wallet.html') {
        initWallet();
    }
}

/* ═══════════════════════════════════════════
   Auth UI
   ═══════════════════════════════════════════ */
async function updateAuthUI() {
    try {
        const res = await fetch('/api/user/status');
        const status = await res.json();
        
        const profileDropdown = document.getElementById('profile-dropdown');
        
        if (status.logged_in) {
            document.body.classList.add('user-logged-in');
            document.body.classList.remove('user-guest');
            
            // Add admin class if admin
            if (status.role === 'admin') {
                document.body.classList.add('user-admin');
            }
            
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
            if (pmRole) pmRole.innerText = status.role === 'admin' ? '🛡️ Admin' : 'Member';
            
            // Update wallet badge in navbar
            const walletBadge = document.getElementById('nav-wallet-badge');
            if (walletBadge && status.wallet_balance !== undefined) {
                walletBadge.innerText = `₹${parseFloat(status.wallet_balance).toFixed(0)}`;
            }
            
            // Toggle menu items
            document.querySelectorAll('.pm-item-auth').forEach(el => el.style.display = 'none');
            document.querySelectorAll('.pm-item-user').forEach(el => el.style.display = 'flex');
        } else {
            document.body.classList.add('user-guest');
            document.body.classList.remove('user-logged-in', 'user-admin');
            
            if (profileDropdown) profileDropdown.style.display = 'none';

            document.querySelectorAll('.pm-item-auth').forEach(el => el.style.display = 'flex');
            document.querySelectorAll('.pm-item-user').forEach(el => el.style.display = 'none');
        }
    } catch (err) {
        console.error('Auth check failed:', err);
    }
}

/* ═══════════════════════════════════════════
   Home Page
   ═══════════════════════════════════════════ */
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

/* ═══════════════════════════════════════════
   My Auctions
   ═══════════════════════════════════════════ */
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

/* ═══════════════════════════════════════════
   My Bids
   ═══════════════════════════════════════════ */
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

        grid.innerHTML = bids.map(b => {
            let deliveryActionHtml = '';
            let deliveryBadgeHtml = '';
            
            if (b.delivery_id) {
                if (b.delivery_status === 'address_pending') {
                    deliveryActionHtml = `<a href="/delivery/${b.delivery_id}/address" class="btn btn-gold btn-sm" style="margin-top:10px; width:100%; justify-content:center;">🚚 Provide Address</a>`;
                    deliveryBadgeHtml = `<span class="badge" style="background:#e67e22; color:#fff;">WON - NEED ADDRESS</span>`;
                } else {
                    const statusLabels = {
                        'ready_for_dispatch': 'Awaiting Dispatch',
                        'out_for_delivery': 'Out for Delivery',
                        'delivered': 'Delivered'
                    };
                    const statusColors = {
                        'ready_for_dispatch': '#f1c40f',
                        'out_for_delivery': '#3498db',
                        'delivered': '#2ecc71'
                    };
                    const label = statusLabels[b.delivery_status] || b.delivery_status.toUpperCase();
                    const color = statusColors[b.delivery_status] || 'var(--gold)';
                    
                    deliveryActionHtml = `<a href="/delivery/${b.delivery_id}/track" class="btn btn-outline btn-sm" style="margin-top:10px; width:100%; justify-content:center; border-color:${color}; color:${color};">📍 Track Shipment</a>`;
                    deliveryBadgeHtml = `<span class="badge" style="background:${color}; color:#000; font-weight:700;">${label.toUpperCase()}</span>`;
                }
            } else {
                deliveryBadgeHtml = `<span class="badge ${b.status === 'active' ? 'badge-success' : 'badge-gray'}">${b.status.toUpperCase()}</span>`;
            }

            return `
                <div class="bid-card" style="display:flex; flex-direction:column; justify-content:space-between; height:100%;">
                    <div>
                        <div class="bp-title" style="font-family:'Playfair Display',serif; font-size:1.15rem; font-weight:700; margin-bottom:10px;">${b.item_name}</div>
                        <div class="bp-prices" style="display:flex; justify-content:space-between; font-size:.85rem; color:var(--text2); border-bottom:1px solid var(--border2); padding-bottom:10px; margin-bottom:10px;">
                          <div>My Bid: <strong style="color:var(--text)">₹${parseFloat(b.my_highest_bid).toFixed(2)}</strong></div>
                          <div>Current: <strong style="color:var(--gold)">₹${parseFloat(b.current_price).toFixed(2)}</strong></div>
                        </div>
                    </div>
                    <div>
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-top:8px;">
                          ${deliveryBadgeHtml}
                          <a href="/auction_detail.html?id=${b.id}" class="btn btn-ghost btn-sm">Details</a>
                        </div>
                        ${deliveryActionHtml}
                    </div>
                </div>
            `;
        }).join('');
    } catch (err) {
        console.error('Failed to load my bids:', err);
    }
}

/* ═══════════════════════════════════════════
   Profile
   ═══════════════════════════════════════════ */
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
        
        document.getElementById('stat-auctions-count').innerText = data.auction_count;
        document.getElementById('stat-bids-count').innerText = data.bid_count;

        document.getElementById('profile-name').innerText = u.username;
        document.getElementById('profile-email').innerText = `📧 ${u.email}`;
        document.getElementById('profile-joined').innerText = u.created_at ? `📅 Joined ${u.created_at.substring(0, 10)}` : '📅 Joined N/A';

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

/* ═══════════════════════════════════════════
   Active Auctions
   ═══════════════════════════════════════════ */
let listingMap = null;
let listingMarkers = [];
let currentAuctionsData = [];
let activeViewMode = 'grid'; // 'grid' or 'map'

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

    // Set up toggle buttons
    const btnGrid = document.getElementById('btn-view-grid');
    const btnMap = document.getElementById('btn-view-map');
    
    if (btnGrid && btnMap) {
        btnGrid.addEventListener('click', () => {
            btnGrid.classList.add('active');
            btnMap.classList.remove('active');
            activeViewMode = 'grid';
            document.getElementById('auction-grid').style.display = 'grid';
            document.getElementById('auctions-map').style.display = 'none';
        });

        btnMap.addEventListener('click', () => {
            btnMap.classList.add('active');
            btnGrid.classList.remove('active');
            activeViewMode = 'map';
            document.getElementById('auction-grid').style.display = 'none';
            document.getElementById('auctions-map').style.display = 'block';
            renderListingMap();
        });
    }

    const params = new URLSearchParams(window.location.search);
    loadAuctions(params.get('search') || '', params.get('sort') || 'end_time');
}

function renderListingMap() {
    const mapContainer = document.getElementById('auctions-map');
    if (!mapContainer || currentAuctionsData.length === 0) return;

    // Initialize map if not already done
    if (!listingMap) {
        let centerLat = 16.3067;
        let centerLng = 80.4365;
        
        const withCoords = currentAuctionsData.find(a => a.latitude && a.longitude);
        if (withCoords) {
            centerLat = withCoords.latitude;
            centerLng = withCoords.longitude;
        }

        listingMap = L.map('auctions-map').setView([centerLat, centerLng], 8);

        L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
            subdomains: 'abcd',
            maxZoom: 20
        }).addTo(listingMap);
    }

    // Clear old markers
    listingMarkers.forEach(m => listingMap.removeLayer(m));
    listingMarkers = [];

    // Add new markers
    const bounds = [];
    currentAuctionsData.forEach(a => {
        if (a.latitude && a.longitude) {
            const popupHtml = `
                <div class="map-popup-card">
                    ${a.image_path ? `<img class="map-popup-img" src="/static/${a.image_path}" alt="${a.item_name}">` : '<div class="map-popup-img" style="display:flex;align-items:center;justify-content:center;background:var(--raised);color:var(--text3);">📦 No Image</div>'}
                    <div class="map-popup-title">${a.item_name}</div>
                    <div class="map-popup-price">Current Bid: ₹${parseFloat(a.current_price).toFixed(2)}</div>
                    <div style="font-size:.7rem;color:var(--text3);margin-bottom:4px;">📍 ${a.location_name || ''}</div>
                    <a class="map-popup-btn" href="/auction_detail.html?id=${a.id}">View Details →</a>
                </div>
            `;

            const marker = L.marker([a.latitude, a.longitude])
                .addTo(listingMap)
                .bindPopup(popupHtml);
            
            listingMarkers.push(marker);
            bounds.push([a.latitude, a.longitude]);
        }
    });

    if (bounds.length > 0) {
        setTimeout(() => {
            listingMap.invalidateSize();
            listingMap.fitBounds(bounds, { padding: [30, 30] });
        }, 100);
    }
}

async function loadAuctions(search = '', sort = 'end_time') {
    const grid = document.getElementById('auction-grid');
    const badge = document.getElementById('auction-count-badge');
    
    try {
        const res = await fetch(`/api/auctions?search=${encodeURIComponent(search)}&sort=${sort}`);
        const auctions = await res.json();
        
        currentAuctionsData = auctions;
        
        if (badge) badge.innerText = `${auctions.length} item(s)`;
        
        if (auctions.length === 0) {
            grid.innerHTML = '<div class="empty-state">No active auctions found.</div>';
            if (listingMap) {
                listingMarkers.forEach(m => listingMap.removeLayer(m));
                listingMarkers = [];
            }
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
        
        if (activeViewMode === 'map') {
            renderListingMap();
        }
        
    } catch (err) {
        console.error('Failed to load auctions:', err);
        grid.innerHTML = '<div class="error-state">Failed to load auctions. Please try again later.</div>';
    }
}

/* ═══════════════════════════════════════════
   Auction Detail
   ═══════════════════════════════════════════ */
async function initAuctionDetail() {
    const detailContainer = document.getElementById('detail-main-content');
    if (!detailContainer) return;

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

        const imgCont = document.getElementById('detail-img-container');
        imgCont.innerHTML = a.image_path ? 
            `<img src="/static/${a.image_path}" alt="${a.item_name}">` : 
            '<div class="detail-img-ph">📦 No Image</div>';
        imgCont.innerHTML += `<div class="detail-status ${a.status === 'active' ? 'ds-active' : 'ds-completed'}">
            ${a.status === 'active' ? 'LIVE AUCTION' : a.status.toUpperCase()}
        </div>`;

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

        const bidForm = document.getElementById('bid-form');
        const hostNotice = document.getElementById('host-notice');
        const guestNotice = document.querySelector('.guest-bid-notice');

        if (!currentUserId) {
            if (guestNotice) guestNotice.style.display = 'flex';
        } else if (currentUserId === a.host_id) {
            if (hostNotice) hostNotice.style.display = 'block';
        } else if (a.status === 'active') {
            if (bidForm) {
                bidForm.style.display = 'block';
                document.getElementById('form-auction-id').value = a.id;
                document.getElementById('bid_amount').min = parseFloat(a.current_price) + 0.01;
                document.getElementById('min-bid-val').innerText = `₹${(parseFloat(a.current_price) + 0.01).toFixed(2)}`;
            }
        }

        // ── Render Location Map ──
        if (a.latitude && a.longitude) {
            const mapBox = document.getElementById('detail-map-box');
            const locNameEl = document.getElementById('detail-location-name');
            if (mapBox) {
                mapBox.style.display = 'block';
                if (locNameEl) locNameEl.innerText = a.location_name || 'Guntur, Andhra Pradesh';
                
                if (!mapBox.dataset.initialized) {
                    mapBox.dataset.initialized = 'true';
                    setTimeout(() => {
                        const detailMap = L.map('detail-map').setView([a.latitude, a.longitude], 13);
                        L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
                            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
                            subdomains: 'abcd',
                            maxZoom: 20
                        }).addTo(detailMap);
                        
                        L.marker([a.latitude, a.longitude]).addTo(detailMap)
                            .bindPopup(`<strong>${a.item_name}</strong><br>${a.location_name || ''}`)
                            .openPopup();
                    }, 200);
                }
            }
        }

    } catch (err) {
        console.error('Failed to load auction details:', err);
    }
}


/* ═══════════════════════════════════════════
   Wallet Page
   ═══════════════════════════════════════════ */
async function initWallet() {
    // Quick amount buttons
    const quickBtns = document.querySelectorAll('.wallet-quick-btn');
    const amountInput = document.getElementById('wallet-amount-input');
    
    quickBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const amount = btn.dataset.amount;
            if (amountInput) amountInput.value = amount;
            quickBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
        });
    });

    // Payment method selection
    const pmOptions = document.querySelectorAll('.payment-method-option');
    const pmInput = document.getElementById('payment-method-input');
    const payBtn = document.getElementById('wallet-pay-btn');
    
    const pmLabels = {
        'card': '💳 Pay with Card',
        'upi': '📱 Pay with UPI',
    };

    pmOptions.forEach(opt => {
        opt.addEventListener('click', () => {
            pmOptions.forEach(o => o.classList.remove('selected'));
            opt.classList.add('selected');
            const method = opt.dataset.method;
            if (pmInput) pmInput.value = method;
            if (payBtn) payBtn.innerHTML = pmLabels[method] || '💳 Pay Now';
        });
    });

    // ── Tab switching in Wallet Balance Card ──
    const tabDeposit = document.getElementById('tab-deposit');
    const tabWithdraw = document.getElementById('tab-withdraw');
    const secDeposit = document.getElementById('wallet-add-section');
    const secWithdraw = document.getElementById('wallet-withdraw-section');

    if (tabDeposit && tabWithdraw) {
        tabDeposit.addEventListener('click', () => {
            tabDeposit.className = 'btn btn-sm btn-gold';
            tabWithdraw.className = 'btn btn-sm btn-outline';
            tabWithdraw.style.backgroundColor = 'none';
            secDeposit.style.display = 'block';
            secWithdraw.style.display = 'none';
        });
        tabWithdraw.addEventListener('click', () => {
            tabWithdraw.className = 'btn btn-sm btn-gold';
            tabDeposit.className = 'btn btn-sm btn-outline';
            tabDeposit.style.backgroundColor = 'none';
            secDeposit.style.display = 'none';
            secWithdraw.style.display = 'block';
        });
    }

    // ── Tab switching in History Card ──
    const tabHistoryTxns = document.getElementById('history-tab-txns');
    const tabHistoryWithdrawals = document.getElementById('history-tab-withdrawals');
    const listTxns = document.getElementById('wallet-txn-list');
    const listWithdrawals = document.getElementById('wallet-withdrawals-list');

    if (tabHistoryTxns && tabHistoryWithdrawals) {
        tabHistoryTxns.addEventListener('click', () => {
            tabHistoryTxns.style.color = 'var(--text)';
            tabHistoryTxns.style.borderBottom = '2px solid var(--gold)';
            tabHistoryWithdrawals.style.color = 'var(--text3)';
            tabHistoryWithdrawals.style.borderBottom = 'none';
            listTxns.style.display = 'flex';
            listWithdrawals.style.display = 'none';
        });
        tabHistoryWithdrawals.addEventListener('click', () => {
            tabHistoryWithdrawals.style.color = 'var(--text)';
            tabHistoryWithdrawals.style.borderBottom = '2px solid var(--gold)';
            tabHistoryTxns.style.color = 'var(--text3)';
            tabHistoryTxns.style.borderBottom = 'none';
            listTxns.style.display = 'none';
            listWithdrawals.style.display = 'flex';
        });
    }

    // Load wallet data
    try {
        const res = await fetch('/api/wallet');
        const data = await res.json();
        
        // Update balance
        const balanceEl = document.getElementById('wallet-balance');
        if (balanceEl) {
            balanceEl.innerText = `₹${parseFloat(data.balance).toFixed(2)}`;
        }
        
        // Update transaction list
        const txnList = document.getElementById('wallet-txn-list');
        if (txnList) {
            if (!data.transactions || data.transactions.length === 0) {
                txnList.innerHTML = '<div class="wallet-txn-empty">No transactions yet. Add funds to get started!</div>';
            } else {
                txnList.innerHTML = data.transactions.map(t => {
                    const isCredit = t.type === 'credit';
                    const icon = getCategoryIcon(t.category);
                    const dateStr = t.created_at ? t.created_at.substring(0, 16).replace('T', ' ') : '';
                    return `
                        <div class="wallet-txn-item">
                            <div class="wallet-txn-icon ${isCredit ? 'txn-icon-credit' : 'txn-icon-debit'}">${icon}</div>
                            <div class="wallet-txn-info">
                                <div class="wallet-txn-desc">${t.description || t.category}</div>
                                <div class="wallet-txn-date">${dateStr}</div>
                            </div>
                            <div class="wallet-txn-amount ${isCredit ? 'credit' : 'debit'}">
                                ${isCredit ? '+' : '-'}₹${parseFloat(t.amount).toFixed(2)}
                            </div>
                        </div>
                    `;
                }).join('');
            }
        }

        // Update withdrawal list
        const wList = document.getElementById('wallet-withdrawals-list');
        if (wList) {
            if (!data.withdrawals || data.withdrawals.length === 0) {
                wList.innerHTML = '<div class="wallet-txn-empty">No withdrawal requests yet.</div>';
            } else {
                wList.innerHTML = data.withdrawals.map(w => {
                    const dateStr = w.created_at ? w.created_at.substring(0, 16).replace('T', ' ') : '';
                    let details = '';
                    if (w.method === 'upi') {
                        details = `UPI: ${w.upi_id}`;
                    } else {
                        details = `${w.bank_name} (${w.account_number.slice(-4).padStart(w.account_number.length, '*')})`;
                    }
                    
                    let statusBadge = '';
                    if (w.status === 'pending') {
                        statusBadge = `<span class="status-badge" style="background:rgba(212,175,55,.15);color:var(--gold)">PENDING</span>`;
                    } else if (w.status === 'approved') {
                        statusBadge = `<span class="status-badge status-active">APPROVED</span>`;
                    } else {
                        statusBadge = `<span class="status-badge status-inactive">REJECTED</span>`;
                    }

                    return `
                        <div class="wallet-txn-item">
                            <div class="wallet-txn-icon txn-icon-debit">📤</div>
                            <div class="wallet-txn-info">
                                <div class="wallet-txn-desc">Withdrawal via ${w.method.toUpperCase()} (${details})</div>
                                <div class="wallet-txn-date">${dateStr}</div>
                            </div>
                            <div class="wallet-txn-amount debit" style="text-align: right;">
                                -₹${parseFloat(w.amount).toFixed(2)}<br>
                                <span style="font-size: 0.75rem;">${statusBadge}</span>
                            </div>
                        </div>
                    `;
                }).join('');
            }
        }
    } catch (err) {
        console.error('Failed to load wallet:', err);
    }
}

// Global scope helper for toggling withdrawal input fields
window.toggleWithdrawMethod = function(method) {
    const upiFields = document.getElementById('withdraw-fields-upi');
    const bankFields = document.getElementById('withdraw-fields-bank');
    const upiLabel = document.getElementById('w-method-upi-label');
    const bankLabel = document.getElementById('w-method-bank-label');
    const upiInput = document.getElementById('withdraw-upi-id');

    const accHolder = document.getElementById('withdraw-acc-holder');
    const bankName = document.getElementById('withdraw-bank-name');
    const accNum = document.getElementById('withdraw-acc-num');
    const ifsc = document.getElementById('withdraw-ifsc');

    if (method === 'upi') {
        if (upiFields) upiFields.style.display = 'block';
        if (bankFields) bankFields.style.display = 'none';
        if (upiInput) upiInput.required = true;
        if (accHolder) accHolder.required = false;
        if (bankName) bankName.required = false;
        if (accNum) accNum.required = false;
        if (ifsc) ifsc.required = false;

        if (upiLabel) {
            upiLabel.style.border = '1.5px solid var(--gold)';
            upiLabel.style.background = 'rgba(200,168,75,.08)';
        }
        if (bankLabel) {
            bankLabel.style.border = '1.5px solid var(--border2)';
            bankLabel.style.background = 'none';
        }
    } else {
        if (upiFields) upiFields.style.display = 'none';
        if (bankFields) bankFields.style.display = 'flex';
        if (upiInput) upiInput.required = false;
        if (accHolder) accHolder.required = true;
        if (bankName) bankName.required = true;
        if (accNum) accNum.required = true;
        if (ifsc) ifsc.required = true;

        if (bankLabel) {
            bankLabel.style.border = '1.5px solid var(--gold)';
            bankLabel.style.background = 'rgba(200,168,75,.08)';
        }
        if (upiLabel) {
            upiLabel.style.border = '1.5px solid var(--border2)';
            upiLabel.style.background = 'none';
        }
    }
}

function getCategoryIcon(category) {
    const icons = {
        'deposit': '💳',
        'bid_escrow': '🔒',
        'bid_refund': '🔓',
        'auction_win': '🏆',
        'platform_fee': '🏦',
        'processing_fee': '⚙️',
        'host_payout': '💰',
        'admin_commission': '👑',
    };
    return icons[category] || '📋';
}


/* ═══════════════════════════════════════════
   Admin Dashboard
   ═══════════════════════════════════════════ */
let adminData = { users: [], auctions: [], transactions: [], withdrawals: [], deposits: [] };

async function initAdminDashboard() {
    // Tab switching
    const tabs = document.querySelectorAll('.admin-tab');
    const panels = document.querySelectorAll('.admin-panel');
    
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const target = tab.dataset.tab;
            tabs.forEach(t => t.classList.remove('active'));
            panels.forEach(p => p.classList.remove('active'));
            tab.classList.add('active');
            document.getElementById(`panel-${target}`).classList.add('active');
            
            // Load data on first tab visit
            if (target === 'users' && adminData.users.length === 0) loadAdminUsers();
            if (target === 'auctions' && adminData.auctions.length === 0) loadAdminAuctions();
            if (target === 'transactions' && adminData.transactions.length === 0) loadAdminTransactions();
            if (target === 'deposits' && adminData.deposits.length === 0) loadAdminDeposits();
            if (target === 'withdrawals' && adminData.withdrawals.length === 0) loadAdminWithdrawals();
            if (target === 'settings') loadAdminSettings();
        });
    });
    
    // Load overview stats
    loadAdminStats();
    
    // Settings form
    const settingsForm = document.getElementById('admin-settings-form');
    if (settingsForm) {
        settingsForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const payload = {
                platform_fee: parseFloat(document.getElementById('setting-platform-fee').value),
                processing_fee: parseFloat(document.getElementById('setting-processing-fee').value),
                min_deposit: parseFloat(document.getElementById('setting-min-deposit').value),
            };
            try {
                const res = await fetch('/admin/settings', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload),
                });
                const data = await res.json();
                if (data.success) {
                    alert('Settings saved successfully!');
                }
            } catch (err) {
                alert('Failed to save settings.');
            }
        });
    }
    
    // Transaction filter
    const txnFilter = document.getElementById('txn-filter-category');
    if (txnFilter) {
        txnFilter.addEventListener('change', () => {
            renderAdminTransactions(txnFilter.value);
        });
    }
}

async function loadAdminStats() {
    try {
        const res = await fetch('/api/admin/stats');
        const s = await res.json();
        
        document.getElementById('stat-total-users').innerText = s.total_users;
        document.getElementById('stat-total-auctions').innerText = s.total_auctions;
        document.getElementById('stat-active-auctions').innerText = s.active_auctions;
        document.getElementById('stat-settled-auctions').innerText = s.settled_auctions;
        document.getElementById('stat-total-revenue').innerText = `₹${parseFloat(s.total_revenue).toFixed(0)}`;
        document.getElementById('stat-platform-earnings').innerText = `₹${parseFloat(s.platform_earnings).toFixed(0)}`;
        document.getElementById('stat-total-deposits').innerText = `₹${parseFloat(s.total_deposits).toFixed(0)}`;
        document.getElementById('stat-admin-balance').innerText = `₹${parseFloat(s.admin_balance).toFixed(0)}`;
    } catch (err) {
        console.error('Failed to load admin stats:', err);
    }
}

async function loadAdminUsers() {
    try {
        const res = await fetch('/api/admin/users');
        adminData.users = await res.json();
        renderAdminUsers();
    } catch (err) {
        console.error('Failed to load users:', err);
    }
}

function renderAdminUsers() {
    const tbody = document.getElementById('admin-users-tbody');
    if (!tbody) return;
    
    if (adminData.users.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="admin-loading">No users found.</td></tr>';
        return;
    }
    
    tbody.innerHTML = adminData.users.map(u => `
        <tr>
            <td>${u.id}</td>
            <td><strong>${u.username}</strong></td>
            <td>${u.email}</td>
            <td>
                <span class="role-badge ${u.role === 'admin' ? 'role-badge-admin' : 'role-badge-user'}">
                    ${u.role === 'admin' ? '👑 Admin' : '👤 User'}
                </span>
            </td>
            <td>₹${parseFloat(u.wallet_balance || 0).toFixed(2)}</td>
            <td>
                <span class="status-badge ${u.is_active ? 'status-active' : 'status-inactive'}">
                    ${u.is_active ? '● Active' : '● Inactive'}
                </span>
            </td>
            <td>${u.created_at ? u.created_at.substring(0, 10) : '—'}</td>
            <td>
                <div class="admin-btn-group">
                    <button class="admin-btn ${u.is_active ? 'admin-btn-danger' : 'admin-btn-success'}"
                            onclick="toggleUserStatus(${u.id})" title="${u.is_active ? 'Deactivate' : 'Activate'}">
                        ${u.is_active ? '🚫' : '✅'}
                    </button>
                    <button class="admin-btn admin-btn-gold"
                            onclick="toggleUserRole(${u.id})" title="${u.role === 'admin' ? 'Demote' : 'Promote to Admin'}">
                        ${u.role === 'admin' ? '⬇️' : '👑'}
                    </button>
                </div>
            </td>
        </tr>
    `).join('');
}

async function toggleUserStatus(userId) {
    if (!confirm('Are you sure you want to toggle this user\'s status?')) return;
    try {
        const res = await fetch(`/admin/user/${userId}/toggle-status`, { method: 'POST' });
        const data = await res.json();
        if (data.error) { alert(data.error); return; }
        // Update local data and re-render
        const user = adminData.users.find(u => u.id === userId);
        if (user) user.is_active = data.is_active;
        renderAdminUsers();
    } catch (err) {
        alert('Failed to update user status.');
    }
}

async function toggleUserRole(userId) {
    if (!confirm('Are you sure you want to change this user\'s role?')) return;
    try {
        const res = await fetch(`/admin/user/${userId}/make-admin`, { method: 'POST' });
        const data = await res.json();
        if (data.error) { alert(data.error); return; }
        const user = adminData.users.find(u => u.id === userId);
        if (user) user.role = data.role;
        renderAdminUsers();
    } catch (err) {
        alert('Failed to update user role.');
    }
}

async function loadAdminAuctions() {
    try {
        const res = await fetch('/api/admin/auctions');
        adminData.auctions = await res.json();
        renderAdminAuctions();
    } catch (err) {
        console.error('Failed to load auctions:', err);
    }
}

function renderAdminAuctions() {
    const tbody = document.getElementById('admin-auctions-tbody');
    if (!tbody) return;
    
    if (adminData.auctions.length === 0) {
        tbody.innerHTML = '<tr><td colspan="10" class="admin-loading">No auctions found.</td></tr>';
        return;
    }
    
    tbody.innerHTML = adminData.auctions.map(a => {
        const statusClass = a.status === 'active' ? 'status-active' : 
                           a.status === 'completed' ? 'status-completed' : 'status-cancelled';
        return `
        <tr>
            <td>${a.id}</td>
            <td><strong>${a.item_name}</strong></td>
            <td>${a.host_name}</td>
            <td>₹${parseFloat(a.current_price).toFixed(2)}</td>
            <td>${a.bid_count}</td>
            <td><span class="status-badge ${statusClass}">${a.status.toUpperCase()}</span></td>
            <td>${a.winner_name || '—'}</td>
            <td>${a.settled ? `₹${parseFloat(a.platform_fee + a.processing_fee).toFixed(2)}` : '—'}</td>
            <td>${a.host_payout ? `₹${parseFloat(a.host_payout).toFixed(2)}` : '—'}</td>
            <td>
                ${a.status === 'active' ? 
                    `<button class="admin-btn admin-btn-danger" onclick="cancelAuction(${a.id})">Cancel</button>` : 
                    '<span style="color:var(--text3)">—</span>'}
            </td>
        </tr>
        `;
    }).join('');
}

async function cancelAuction(auctionId) {
    if (!confirm('Are you sure you want to cancel this auction? All bidders will be refunded.')) return;
    try {
        const res = await fetch(`/admin/auction/${auctionId}/cancel`, { method: 'POST' });
        const data = await res.json();
        if (data.error) { alert(data.error); return; }
        // Reload
        loadAdminAuctions();
        loadAdminStats();
        alert('Auction cancelled. All bidders have been refunded.');
    } catch (err) {
        alert('Failed to cancel auction.');
    }
}

async function loadAdminTransactions() {
    try {
        const res = await fetch('/api/admin/transactions');
        adminData.transactions = await res.json();
        renderAdminTransactions('');
    } catch (err) {
        console.error('Failed to load transactions:', err);
    }
}

function renderAdminTransactions(categoryFilter) {
    const tbody = document.getElementById('admin-txn-tbody');
    if (!tbody) return;
    
    let txns = adminData.transactions;
    if (categoryFilter) {
        txns = txns.filter(t => t.category === categoryFilter);
    }
    
    if (txns.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="admin-loading">No transactions found.</td></tr>';
        return;
    }
    
    tbody.innerHTML = txns.map(t => `
        <tr>
            <td>${t.id}</td>
            <td><strong>${t.username}</strong></td>
            <td class="${t.type === 'credit' ? 'txn-credit' : 'txn-debit'}">
                ${t.type === 'credit' ? '+' : '-'}₹${parseFloat(t.amount).toFixed(2)}
            </td>
            <td>
                <span class="status-badge ${t.type === 'credit' ? 'status-active' : 'status-inactive'}">
                    ${t.type.toUpperCase()}
                </span>
            </td>
            <td><span class="txn-category">${getCategoryIcon(t.category)} ${t.category.replace(/_/g, ' ')}</span></td>
            <td>${t.description || '—'}</td>
            <td>${t.created_at ? t.created_at.substring(0, 16).replace('T', ' ') : '—'}</td>
        </tr>
    `).join('');
}

async function loadAdminSettings() {
    try {
        const res = await fetch('/api/admin/settings');
        const s = await res.json();
        document.getElementById('setting-platform-fee').value = s.platform_fee;
        document.getElementById('setting-processing-fee').value = s.processing_fee;
        document.getElementById('setting-min-deposit').value = s.min_deposit;
    } catch (err) {
        console.error('Failed to load settings:', err);
    }
}

async function loadAdminWithdrawals() {
    try {
        const res = await fetch('/api/admin/withdrawals');
        adminData.withdrawals = await res.json();
        renderAdminWithdrawals();
    } catch (err) {
        console.error('Failed to load withdrawals:', err);
    }
}

function renderAdminWithdrawals() {
    const tbody = document.getElementById('admin-withdrawals-tbody');
    if (!tbody) return;

    if (adminData.withdrawals.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="admin-loading">No withdrawal requests found.</td></tr>';
        return;
    }

    tbody.innerHTML = adminData.withdrawals.map(w => {
        let details = '';
        if (w.method === 'upi') {
            details = `<strong>UPI ID:</strong> ${w.upi_id}`;
        } else {
            details = `<strong>Holder:</strong> ${w.account_holder}<br>
                       <strong>Bank:</strong> ${w.bank_name}<br>
                       <strong>Acc:</strong> ${w.account_number}<br>
                       <strong>IFSC:</strong> ${w.ifsc_code}`;
        }

        let statusClass = 'status-cancelled';
        if (w.status === 'pending') statusClass = 'status-completed';
        if (w.status === 'approved') statusClass = 'status-active';
        if (w.status === 'rejected') statusClass = 'status-inactive';

        const actionBtns = w.status === 'pending' ? `
            <div class="admin-btn-group">
                <button class="admin-btn admin-btn-success" onclick="approveWithdrawal(${w.id})">Approve</button>
                <button class="admin-btn admin-btn-danger" onclick="rejectWithdrawal(${w.id})">Reject</button>
            </div>
        ` : '—';

        const dateStr = w.created_at ? w.created_at.substring(0, 16).replace('T', ' ') : '—';

        return `
            <tr>
                <td>${w.id}</td>
                <td><strong>${w.username}</strong><br><span style="font-size:0.75rem;color:var(--text3)">${w.email}</span></td>
                <td>₹${parseFloat(w.amount).toFixed(2)}</td>
                <td><span class="txn-category">${w.method === 'upi' ? '📱' : '🏦'} ${w.method.toUpperCase()}</span></td>
                <td><div style="font-size:0.8rem;line-height:1.4">${details}</div></td>
                <td><span class="status-badge ${statusClass}">${w.status.toUpperCase()}</span></td>
                <td>${dateStr}</td>
                <td>${actionBtns}</td>
            </tr>
        `;
    }).join('');
}

async function approveWithdrawal(id) {
    if (!confirm('Are you sure you want to APPROVE this withdrawal? The amount will be marked as processed.')) return;
    try {
        const res = await fetch(`/admin/withdrawal/${id}/approve`, { method: 'POST' });
        const data = await res.json();
        if (data.error) { alert(data.error); return; }
        
        // Update local status
        const item = adminData.withdrawals.find(w => w.id === id);
        if (item) item.status = 'approved';
        renderAdminWithdrawals();
        loadAdminStats();
    } catch (err) {
        alert('Failed to approve withdrawal.');
    }
}

async function rejectWithdrawal(id) {
    if (!confirm('Are you sure you want to REJECT this withdrawal? The amount will be refunded back to the user\'s wallet.')) return;
    try {
        const res = await fetch(`/admin/withdrawal/${id}/reject`, { method: 'POST' });
        const data = await res.json();
        if (data.error) { alert(data.error); return; }
        
        // Update local status
        const item = adminData.withdrawals.find(w => w.id === id);
        if (item) item.status = 'rejected';
        renderAdminWithdrawals();
        loadAdminStats();
    } catch (err) {
        alert('Failed to reject withdrawal.');
    }
}

async function loadAdminDeposits() {
    try {
        const res = await fetch('/api/admin/deposits');
        adminData.deposits = await res.json();
        renderAdminDeposits();
    } catch (err) {
        console.error('Failed to load deposits:', err);
    }
}

function renderAdminDeposits() {
    const tbody = document.getElementById('admin-deposits-tbody');
    if (!tbody) return;

    if (adminData.deposits.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="admin-loading">No manual deposits found.</td></tr>';
        return;
    }

    tbody.innerHTML = adminData.deposits.map(d => {
        let statusClass = 'status-cancelled';
        if (d.status === 'pending') statusClass = 'status-completed';
        if (d.status === 'approved') statusClass = 'status-active';
        if (d.status === 'rejected') statusClass = 'status-inactive';

        const actionBtns = d.status === 'pending' ? `
            <div class="admin-btn-group">
                <button class="admin-btn admin-btn-success" onclick="approveDeposit(${d.id})">Approve</button>
                <button class="admin-btn admin-btn-danger" onclick="rejectDeposit(${d.id})">Reject</button>
            </div>
        ` : '—';

        const dateStr = d.created_at ? d.created_at.substring(0, 16).replace('T', ' ') : '—';

        return `
            <tr>
                <td>${d.id}</td>
                <td><strong>${d.username}</strong><br><span style="font-size:0.75rem;color:var(--text3)">${d.email}</span></td>
                <td>₹${parseFloat(d.amount).toFixed(2)}</td>
                <td><span class="txn-category">📱 ${d.method.toUpperCase()}</span></td>
                <td><code style="background:rgba(255,255,255,.05);padding:3px 6px;border-radius:4px">${d.reference_num}</code></td>
                <td><span class="status-badge ${statusClass}">${d.status.toUpperCase()}</span></td>
                <td>${dateStr}</td>
                <td>${actionBtns}</td>
            </tr>
        `;
    }).join('');
}

async function approveDeposit(id) {
    if (!confirm('Are you sure you want to APPROVE this deposit reference? The user\'s wallet will be credited.')) return;
    try {
        const res = await fetch(`/admin/deposit/${id}/approve`, { method: 'POST' });
        const data = await res.json();
        if (data.error) { alert(data.error); return; }
        
        const item = adminData.deposits.find(d => d.id === id);
        if (item) item.status = 'approved';
        renderAdminDeposits();
        loadAdminStats();
    } catch (err) {
        alert('Failed to approve deposit.');
    }
}

async function rejectDeposit(id) {
    if (!confirm('Are you sure you want to REJECT this deposit reference? The user will be notified of rejection.')) return;
    try {
        const res = await fetch(`/admin/deposit/${id}/reject`, { method: 'POST' });
        const data = await res.json();
        if (data.error) { alert(data.error); return; }
        
        const item = adminData.deposits.find(d => d.id === id);
        if (item) item.status = 'rejected';
        renderAdminDeposits();
        loadAdminStats();
    } catch (err) {
        alert('Failed to reject deposit.');
    }
}

window.approveWithdrawal = approveWithdrawal;
window.rejectWithdrawal = rejectWithdrawal;
window.approveDeposit = approveDeposit;
window.rejectDeposit = rejectDeposit;

