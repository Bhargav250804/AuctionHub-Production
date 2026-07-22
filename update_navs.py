import os, re

templates_dir = r'c:\Users\bharg\Desktop\projects\AuctionHub\templates'
skip = ['index.html', 'admin_dashboard.html', 'wallet.html']

wallet_nav = (
    '        <a href="/wallet" class="nav-link auth-only nav-wallet-link">\n'
    '          \U0001f4b0 Wallet <span class="nav-wallet-badge" id="nav-wallet-badge">\u20b90</span>\n'
    '        </a>\n\n'
    '        <a href="/admin" class="nav-link admin-only nav-admin-link">\n'
    '          \U0001f6e1\ufe0f Admin\n'
    '        </a>\n\n'
)

wallet_pm = '            <a href="/wallet" class="pm-item pm-item-user">\U0001f4b0 My Wallet</a>\n'

for fname in os.listdir(templates_dir):
    if fname in skip or not fname.endswith('.html'):
        continue
    path = os.path.join(templates_dir, fname)
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    changed = False

    if 'nav-wallet-link' not in content and 'nav-menu' in content:
        faq_idx = content.find('<a href="/faq.html" class="nav-link">')
        if faq_idx > 0:
            # Find start of line
            line_start = content.rfind('\n', 0, faq_idx) + 1
            content = content[:line_start] + wallet_nav + content[line_start:]
            changed = True

    if '\U0001f4b0 My Wallet' not in content and 'pm-item-user' in content:
        profile_link_end = content.find('My Profile</a>')
        if profile_link_end > 0:
            end_of_line = content.find('\n', profile_link_end)
            if end_of_line > 0:
                content = content[:end_of_line+1] + wallet_pm + content[end_of_line+1:]
                changed = True

    if changed:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f'Updated: {fname}')
    else:
        print(f'Skipped: {fname}')
