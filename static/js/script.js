/* =============================================
   AuctionHub — script.js  (pure vanilla JS)
   ============================================= */

/* ── Utility ──────────────────────────────── */
const $ = (sel, ctx = document) => ctx.querySelector(sel);
const $$ = (sel, ctx = document) => [...ctx.querySelectorAll(sel)];

function togglePassword(id) {
  const f = document.getElementById(id);
  const e = document.getElementById(id + '-eye');
  if (!f) return;
  if (f.type === 'password') { f.type = 'text';     if (e) e.textContent = '🙈'; }
  else                        { f.type = 'password'; if (e) e.textContent = '👁'; }
}

function showErr(id, msg) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = msg;
  el.style.display = 'block';
}
function clearErrs() {
  $$('.field-err').forEach(el => { el.textContent = ''; el.style.display = 'none'; });
}

/* ── Flash auto-dismiss ───────────────────── */
function initFlashes() {
  $$('.flash').forEach(el => {
    const btn = el.querySelector('.flash-close');
    if (btn) btn.addEventListener('click', () => el.remove());
    setTimeout(() => { el.style.opacity = '0'; el.style.transition = '.4s'; setTimeout(() => el.remove(), 400); }, 4500);
  });
}

/* ── Card countdown timers ────────────────── */
function initCardTimers() {
  $$('.card-timer[data-end]').forEach(el => {
    function update() {
      const diff = new Date(el.dataset.end.replace(' ', 'T')) - Date.now();
      if (diff <= 0) { el.textContent = '⏹ Ended'; el.classList.add('urgent'); return; }
      const d = Math.floor(diff / 86400000);
      const h = Math.floor((diff % 86400000) / 3600000);
      const m = Math.floor((diff % 3600000) / 60000);
      const s = Math.floor((diff % 60000) / 1000);
      el.textContent = d > 0 ? `${d}d ${h}h ${m}m` : h > 0 ? `${h}h ${m}m ${s}s` : `${m}m ${s}s`;
      if (diff < 3600000) el.classList.add('urgent');
    }
    update();
    setInterval(update, 1000);
  });
}

/* ── Detail page big countdown ────────────── */
let detailTimer;
function initDetailCountdown() {
  const wrap = document.getElementById('main-countdown');
  if (!wrap) return;
  if (detailTimer) clearInterval(detailTimer);
  const endTimeStr = wrap.dataset.end;
  if (!endTimeStr) return;
  const endTime = new Date(endTimeStr.replace(' ', 'T'));
  const [dEl, hEl, mEl, sEl] = ['cd-d','cd-h','cd-m','cd-s'].map(id => document.getElementById(id));
  const section = document.getElementById('countdown-box');

  function pad(n) { return String(n).padStart(2, '0'); }
  function update() {
    const diff = endTime - Date.now();
    if (diff <= 0) {
      if (section) section.innerHTML = '<div class="bp-ended">⏹ Auction ended — refresh for results</div>';
      if (detailTimer) clearInterval(detailTimer);
      return;
    }
    const d = Math.floor(diff / 86400000);
    const h = Math.floor((diff % 86400000) / 3600000);
    const m = Math.floor((diff % 3600000) / 60000);
    const s = Math.floor((diff % 60000) / 1000);
    if (dEl) dEl.textContent = pad(d);
    if (hEl) hEl.textContent = pad(h);
    if (mEl) mEl.textContent = pad(m);
    if (sEl) sEl.textContent = pad(s);
    if (wrap && diff < 3600000) wrap.classList.add('urgent');
  }
  update();
  detailTimer = setInterval(update, 1000);
}

/* ── My-bids timers ───────────────────────── */
function initBidPageTimers() {
  $$('.bp-timer[data-end]').forEach(el => {
    function update() {
      const diff = new Date(el.dataset.end.replace(' ', 'T')) - Date.now();
      if (diff <= 0) { el.textContent = 'Ended'; return; }
      const h = Math.floor(diff / 3600000);
      const m = Math.floor((diff % 3600000) / 60000);
      const s = Math.floor((diff % 60000) / 1000);
      el.textContent = `${h}h ${m}m ${s}s left`;
    }
    update();
    setInterval(update, 1000);
  });
}

/* ── Quick bid buttons ────────────────────── */
function initQuickBids() {
  const input = document.getElementById('bid_amount');
  if (!input) return;
  const base = parseFloat(input.dataset.current || 0);

  $$('.qb').forEach(btn => {
    btn.addEventListener('click', () => {
      const cur = parseFloat(input.value) || base;
      const add = parseFloat(btn.dataset.add || 0);
      input.value = (cur + add).toFixed(2);
      validateBid();
    });
  });
}

/* ── Bid validation ───────────────────────── */
function validateBid() {
  const input = document.getElementById('bid_amount');
  const err   = document.getElementById('bid-err');
  if (!input || !err) return true;
  const cur   = parseFloat(input.dataset.current || 0);
  const val   = parseFloat(input.value);
  if (!val || val <= cur) {
    err.textContent = `Must be greater than ₹${cur.toFixed(2)}`;
    err.style.display = 'block';
    return false;
  }
  err.style.display = 'none';
  return true;
}

/* ── Register form ────────────────────────── */
function initRegisterForm() {
  const form = document.getElementById('register-form');
  if (!form) return;

  const pwInput = document.getElementById('password');
  if (pwInput) {
    pwInput.addEventListener('input', function() {
      const bar = document.getElementById('str-bar');
      const fill = document.getElementById('str-fill');
      const lbl  = document.getElementById('str-lbl');
      if (!bar) return;
      if (!this.value) { bar.style.display = 'none'; return; }
      bar.style.display = 'block';
      let score = 0;
      if (this.value.length >= 6)  score++;
      if (this.value.length >= 10) score++;
      if (/[A-Z]/.test(this.value)) score++;
      if (/[0-9]/.test(this.value)) score++;
      if (/[^A-Za-z0-9]/.test(this.value)) score++;
      const colors = ['','#e74c3c','#e67e22','#f1c40f','#2ecc71','#27ae60'];
      const labels = ['','Very Weak','Weak','Fair','Strong','Very Strong'];
      fill.style.width = (score / 5 * 100) + '%';
      fill.style.background = colors[score];
      lbl.textContent = labels[score];
      lbl.style.color = colors[score];
    });
  }

  form.addEventListener('submit', function(e) {
    clearErrs();
    let ok = true;
    const username = document.getElementById('username');
    const email    = document.getElementById('email');
    const password = document.getElementById('password');
    const confirm  = document.getElementById('confirm_password');

    if (!username?.value.trim() || username.value.trim().length < 3) {
      showErr('err-username', 'Username must be at least 3 characters'); ok = false;
    }
    if (!email?.value || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.value)) {
      showErr('err-email', 'Enter a valid email'); ok = false;
    }
    if (!password?.value || password.value.length < 6) {
      showErr('err-password', 'Password must be at least 6 characters'); ok = false;
    }
    if (password?.value !== confirm?.value) {
      showErr('err-confirm', 'Passwords do not match'); ok = false;
    }
    if (!ok) e.preventDefault();
  });
}

/* ── Login form ───────────────────────────── */
function initLoginForm() {
  const form = document.getElementById('login-form');
  if (!form) return;
  form.addEventListener('submit', function(e) {
    clearErrs();
    let ok = true;
    if (!document.getElementById('username')?.value.trim()) {
      showErr('err-username', 'Username is required'); ok = false;
    }
    if (!document.getElementById('password')?.value) {
      showErr('err-password', 'Password is required'); ok = false;
    }
    if (!ok) e.preventDefault();
  });
}

/* ── Create auction form ──────────────────── */
function initCreateForm() {
  const form = document.getElementById('create-form');
  if (!form) return;

  // Set min datetime
  const endInput = document.getElementById('end_time');
  if (endInput) {
    const min = new Date(Date.now() + 3600000);
    endInput.min = min.toISOString().slice(0, 16);
  }

  // Char counter
  const desc = document.getElementById('description');
  const cnt  = document.getElementById('desc-count');
  if (desc && cnt) {
    desc.addEventListener('input', () => cnt.textContent = desc.value.length + ' / 2000');
  }

  // Image preview
  const imgInput = document.getElementById('image');
  if (imgInput) {
    imgInput.addEventListener('change', function() {
      if (!this.files[0]) return;
      const reader = new FileReader();
      reader.onload = ev => {
        const preview = document.getElementById('img-preview');
        const prompt  = document.getElementById('upload-prompt');
        const wrap    = document.getElementById('preview-wrap');
        if (preview) preview.src = ev.target.result;
        if (wrap)    wrap.style.display = 'block';
        if (prompt)  prompt.style.display = 'none';
      };
      reader.readAsDataURL(this.files[0]);
    });
  }

  // Form validate
  form.addEventListener('submit', function(e) {
    clearErrs();
    let ok = true;
    const name  = document.getElementById('item_name')?.value.trim();
    const price = parseFloat(document.getElementById('starting_price')?.value);
    const end   = document.getElementById('end_time')?.value;
    if (!name) { showErr('err-name', 'Item name is required'); ok = false; }
    if (!price || price <= 0) { showErr('err-price', 'Enter a valid price > 0'); ok = false; }
    if (!end) { showErr('err-end', 'End time is required'); ok = false; }
    else if (new Date(end) <= new Date()) { showErr('err-end', 'End time must be in the future'); ok = false; }
    if (!ok) e.preventDefault();
  });
}

/* ── Remove preview image ─────────────────── */
function removePreview(e) {
  e.stopPropagation();
  document.getElementById('image').value = '';
  const wrap   = document.getElementById('preview-wrap');
  const prompt = document.getElementById('upload-prompt');
  if (wrap)   wrap.style.display = 'none';
  if (prompt) prompt.style.display = 'flex';
}

/* ── Duration quick-set ───────────────────── */
function setDuration(hours) {
  const input = document.getElementById('end_time');
  if (!input) return;
  const d = new Date(Date.now() + hours * 3600000);
  input.value = d.toISOString().slice(0, 16);
  $$('.dur-btn').forEach(b => b.classList.remove('active'));
  event.currentTarget.classList.add('active');
}

/* ── Nav toggle (mobile) ──────────────────── */
function initNavToggle() {
  const btn  = document.getElementById('nav-toggle');
  const menu = document.getElementById('nav-menu');
  if (!btn || !menu) return;
  btn.addEventListener('click', () => menu.classList.toggle('open'));
}

/* ── Profile dropdown toggle ──────────────── */
function initProfileDropdown() {
  const trigger = document.getElementById('profile-trigger');
  const menu    = document.getElementById('profile-menu');
  if (!trigger || !menu) return;

  trigger.addEventListener('click', (e) => {
    e.stopPropagation();
    menu.classList.toggle('open');
  });

  document.addEventListener('click', (e) => {
    if (!menu.contains(e.target) && !trigger.contains(e.target)) {
      menu.classList.remove('open');
    }
  });
}

/* ── Activity dropdown toggle ─────────────── */
function initActivityDropdown() {
  const trigger = document.getElementById('activity-trigger');
  const menu    = document.getElementById('activity-menu');
  if (!trigger || !menu) return;

  trigger.addEventListener('click', (e) => {
    e.stopPropagation();
    menu.classList.toggle('open');
  });

  document.addEventListener('click', (e) => {
    if (!menu.contains(e.target) && !trigger.contains(e.target)) {
      menu.classList.remove('open');
    }
  });
}

/* ── Image Carousel ───────────────────────── */
function initCarousel() {
  const track = document.getElementById('carousel-track');
  const prev  = document.getElementById('carousel-prev');
  const next  = document.getElementById('carousel-next');
  const dotsWrap = document.getElementById('carousel-dots');
  if (!track || !prev || !next) return;

  const slides = track.querySelectorAll('.carousel-slide');
  if (slides.length === 0) return;

  let perView = window.innerWidth <= 700 ? 1 : 3;
  let current = 0;
  const maxIndex = Math.max(0, slides.length - perView);

  // Create dots
  if (dotsWrap) {
    for (let i = 0; i <= maxIndex; i++) {
      const dot = document.createElement('button');
      dot.classList.add('carousel-dot');
      if (i === 0) dot.classList.add('active');
      dot.addEventListener('click', () => goTo(i));
      dotsWrap.appendChild(dot);
    }
  }

  function goTo(idx) {
    current = Math.max(0, Math.min(idx, maxIndex));
    track.style.transform = `translateX(-${current * (100 / perView)}%)`;
    if (dotsWrap) {
      dotsWrap.querySelectorAll('.carousel-dot').forEach((d, i) => {
        d.classList.toggle('active', i === current);
      });
    }
  }

  prev.addEventListener('click', () => goTo(current - 1));
  next.addEventListener('click', () => goTo(current + 1));

  // Auto-scroll
  let autoTimer = setInterval(() => goTo(current >= maxIndex ? 0 : current + 1), 4000);
  track.parentElement.addEventListener('mouseenter', () => clearInterval(autoTimer));
  track.parentElement.addEventListener('mouseleave', () => {
    autoTimer = setInterval(() => goTo(current >= maxIndex ? 0 : current + 1), 4000);
  });

  window.addEventListener('resize', () => {
    perView = window.innerWidth <= 700 ? 1 : 3;
    goTo(0);
  });
}

/* ── Scroll navbar shadow ─────────────────── */
function initNavShadow() {
  const nav = document.querySelector('nav');
  if (!nav) return;
  window.addEventListener('scroll', () => {
    nav.style.boxShadow = window.scrollY > 10 ? '0 4px 24px rgba(0,0,0,.5)' : 'none';
  });
}

/* ── Card entrance animation ──────────────── */
function initAnimations() {
  if (!window.IntersectionObserver) return;
  const cards = $$('.auction-card, .bp-card, .stat-tile');
  const observer = new IntersectionObserver(entries => {
    entries.forEach((e, i) => {
      if (e.isIntersecting) {
        setTimeout(() => {
          e.target.style.opacity = '1';
          e.target.style.transform = 'translateY(0)';
        }, i * 55);
        observer.unobserve(e.target);
      }
    });
  }, { threshold: 0.06 });
  cards.forEach(c => {
    c.style.opacity = '0';
    c.style.transform = 'translateY(18px)';
    c.style.transition = 'opacity .4s ease, transform .4s ease';
    observer.observe(c);
  });
}

/* ── Bid form submit ──────────────────────── */
function initBidForm() {
  const form = document.getElementById('bid-form');
  if (!form) return;
  const input = document.getElementById('bid_amount');
  if (input) input.addEventListener('input', validateBid);
  form.addEventListener('submit', function(e) {
    if (!validateBid()) e.preventDefault();
  });
}

/* ── Loading state on submit buttons ─────── */
function initLoadingState() {
  $$('form').forEach(form => {
    form.addEventListener('submit', function() {
      const btn = this.querySelector('[type="submit"]');
      if (btn && !btn.disabled) {
        const orig = btn.textContent;
        setTimeout(() => {
          btn.textContent = 'Processing...';
          btn.disabled = true;
          setTimeout(() => { btn.textContent = orig; btn.disabled = false; }, 7000);
        }, 30);
      }
    });
  });
}

/* ── Boot ─────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  initFlashes();
  initCardTimers();
  initDetailCountdown();
  initBidPageTimers();
  initQuickBids();
  initBidForm();
  initRegisterForm();
  initLoginForm();
  initCreateForm();
  initNavToggle();
  initProfileDropdown();
  initActivityDropdown();
  initCarousel();
  initNavShadow();
  initAnimations();
  initLoadingState();
});
