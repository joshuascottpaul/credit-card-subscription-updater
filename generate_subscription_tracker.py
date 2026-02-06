#!/usr/bin/env python3
"""
Recurring Subscription Tracker Generator

GOAL:
    Identify recurring payments from credit card transactions to update payment methods
    when a credit card is expiring.

DESIRED OUTCOMES:
    1. Parse CSV transaction data to find recurring charges (3+ occurrences)
    2. Calculate average charge amounts and predict next billing dates
    3. Generate an interactive HTML checklist with:
       - Direct links to vendor billing pages
       - Progress tracking with persistent checkboxes
       - Clean list view for focused task completion

USAGE:
    python3 generate_subscription_tracker.py input.csv output.html

INPUT CSV FORMAT:
    Expected columns: Account Type, Account Number, Transaction Date, Description 1, CAD$, USD$
    Transaction Date format: M/D/YYYY
    Negative amounts indicate charges

OUTPUT:
    HTML file with interactive subscription checklist
"""

import csv
import sys
from collections import defaultdict
from datetime import datetime, timedelta

# Current date for calculating future billing dates
TODAY = datetime.now()

def get_vendor_url(merchant):
    """Map merchant names to their billing/payment URLs"""
    urls = {
        'Amazon Web Services www.amazon.ca': 'https://console.aws.amazon.com/billing/home#/paymentmethods',
        'TRELLO.COM* ATLASSIAN ATLASSIAN.COM': 'https://trello.com/login',
        '1PASSWORD TORONTO': 'https://my.1password.com/billing',
        'ZOOM.COM 888-799-9666 ZOOM.US': 'https://zoom.us/billing',
        'MIDAS ALARM & SECURITY LT BURNABY': 'https://www.midasalarm.com/contact',
        'ADVANCED PARKING AUTO 877-909-6199': 'https://www.advancedparking.ca/contact',
        'GREENVIEW DATA INC. 888-576-4949': 'https://www.greenviewdata.com/clientarea.php',
        'CLOUD LINUX, INC CLN.CLOUDLINU': 'https://cln.cloudlinux.com/console/billing',
        'Amazon.ca Prime Member amazon.ca/pri': 'https://www.amazon.ca/mc/yourpayments',
        'SMTP2GO, I* SMTP2GO EM SMTP2GO.COM': 'https://www.smtp2go.com/settings/billing/',
        '4TE*ACCOUNTEDGE 973-586-2200': 'https://www.accountedge.com/my-account',
        'OPSSHIELD LLP KOCHI': 'https://opsshield.com/login',
        'CLOUDFLARE CLOUDFLARE.CO': 'https://dash.cloudflare.com/billing',
        'NINJAONE, LLC NINJAONE.COM': 'https://app.ninjarmm.com/#/settings/billing',
        'GOOGLE *ADS8657284425 855-222-8603': 'https://ads.google.com/aw/billing',
        'GOOGLE*ADS8657284425 CC GOOGLE.COM': 'https://ads.google.com/aw/billing',
        'OPENAI *CHATGPT SUBSCR OPENAI.COM': 'https://platform.openai.com/settings/organization/billing/overview',
        'GOOGLE *GSUITE_neocode 855-222-8603': 'https://admin.google.com/ac/billing',
        'GOOGLE *Workspace_neoc 855-222-8603': 'https://admin.google.com/ac/billing',
        'HUBSTAFF.COM HUBSTAFF.COM': 'https://app.hubstaff.com/organizations/billing',
        'BACKBLAZE INC BACKBLAZE.COM': 'https://secure.backblaze.com/billing.htm',
        'ONEPROVIDER 5142860253': 'https://oneprovider.com/portal/clientarea.php',
        'LINODE . AKAMAI 6093807100': 'https://cloud.linode.com/account/billing',
        'FILEMAKER 800-325-2747': 'https://www.claris.com/account/',
        'INBOX ZERO INC. GETINBOXZERO.': 'https://www.getinboxzero.com/settings',
        'SCRAPFLY SCRAPFLY.IO': 'https://scrapfly.io/dashboard/billing',
        'IDIGITAL INTERNET INC VANCOUVER': 'https://www.idigital.ca/clientarea.php',
        'NEW DEMOCRATIC PARTY 604-430-8600': 'https://www.ndp.ca/donate',
        'WALMART.CA MISSISSAUGA': 'https://www.walmart.ca/account',
        'WALMART DELIVERY PASS REN MISSISSAUGA': 'https://www.walmart.ca/account',
        'STARBUCKS 8007827282 800-782-7282': 'https://www.starbucks.ca/account',
        'CS *STARBUCKS GC 877-850-1977': 'https://www.starbucks.ca/account',
        'PADDLE.NET* DECODO LONDON': 'https://vendors.paddle.com/subscriptions',
        'PADDLE.NET* SMARTPROXY LONDON': 'https://vendors.paddle.com/subscriptions',
        'PADDLE.NET* SUPERDUPER LONDON': 'https://vendors.paddle.com/subscriptions',
        'MEGA LIMITED AUCKLAND': 'https://mega.nz/fm/account/plan',
        'SYNC 18553677962': 'https://cp.sync.com/billing',
        'SYNC.COM* SYNC.COM TORONTO': 'https://cp.sync.com/billing',
        'TASKRABBIT* RECEIPT VANCOUVER': 'https://www.taskrabbit.com/account/payment',
        'OPENVPN SUBSCRIPTION OPENVPN.NET': 'https://myaccount.openvpn.com/',
        'Microsoft*Microsoft 365 F Mississauga': 'https://account.microsoft.com/services/',
        'ELEVENLABS.IO ELEVENLABS.IO': 'https://elevenlabs.io/app/settings/billing',
        'ANTHROPIC ANTHROPIC.COM': 'https://console.anthropic.com/settings/billing',
        'PROTON AG* PROTON AG GENEVA': 'https://account.proton.me/u/0/mail/dashboard',
        'SSLSTORE SAINT PETERSB': 'https://www.thesslstore.com/client/login.php',
        'CHEAPSSLWEB.COM SIGNMYCODE.CO': 'https://cheapsslweb.com/client/login.php',
        'CERTERALLC* CHEAPSSLWE SIGNMYCODE.CO': 'https://cheapsslweb.com/client/login.php',
    }
    
    # Direct match
    if merchant in urls:
        return urls[merchant]
    
    # Pattern matching for common variations
    if 'CPANEL' in merchant:
        return 'https://store.cpanel.net/view-invoice'
    if 'Audible' in merchant:
        return 'https://www.audible.ca/account/payments'
    if 'GODADDY' in merchant:
        return 'https://account.godaddy.com/billing'
    if 'FS *' in merchant:
        return 'https://fsprg.com/account'
    
    # Fallback: Google search for billing page
    return f'https://www.google.com/search?q={merchant.replace(" ", "+")}+billing+payment+method'

def parse_transactions(csv_path):
    """Parse CSV and extract recurring subscriptions"""
    merchant_data = defaultdict(lambda: {'dates': [], 'amounts': [], 'charges': []})
    
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            desc = row['Description 1'].strip()
            
            # Skip non-subscription entries
            if not desc or 'PAYMENT - THANK YOU' in desc or 'PURCHASE INTEREST' in desc or 'OVERLIMIT FEE' in desc:
                continue
            
            try:
                date = datetime.strptime(row['Transaction Date'], '%m/%d/%Y')
                amount = row['CAD$'].strip() if row['CAD$'].strip() else row['USD$'].strip()
                
                if amount:
                    merchant_data[desc]['dates'].append(date)
                    merchant_data[desc]['amounts'].append(float(amount))
                    merchant_data[desc]['charges'].append({'date': date, 'amount': float(amount)})
            except:
                continue
    
    # Filter for recurring subscriptions (3+ occurrences)
    recurring = []
    for merchant, data in merchant_data.items():
        if len(data['dates']) >= 3:
            dates_sorted = sorted(data['dates'])
            amounts = [abs(a) for a in data['amounts'] if a < 0]  # Only charges
            
            if amounts:
                avg_amount = sum(amounts) / len(amounts)
                last_date = dates_sorted[-1]
                
                # Calculate average billing interval
                intervals = [(dates_sorted[i] - dates_sorted[i-1]).days for i in range(1, len(dates_sorted))]
                avg_interval = sum(intervals) / len(intervals) if intervals else 30
                
                # Predict next billing date (ensure it's in the future)
                next_billing = last_date + timedelta(days=avg_interval)
                while next_billing < TODAY:
                    next_billing += timedelta(days=avg_interval)
                
                # Sort charges by date (most recent first)
                charges_sorted = sorted([c for c in data['charges'] if c['amount'] < 0], 
                                      key=lambda x: x['date'], reverse=True)
                
                recurring.append({
                    'merchant': merchant,
                    'count': len(dates_sorted),
                    'avg_amount': avg_amount,
                    'next_billing': next_billing,
                    'interval': avg_interval,
                    'charges': charges_sorted
                })
    
    # Sort by frequency (most frequent first)
    recurring.sort(key=lambda x: x['count'], reverse=True)
    return recurring

def generate_html(subscriptions, output_path):
    """Generate interactive HTML checklist"""
    html = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Update Credit Card - Subscriptions</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f5f5f5; }
        .header { background: white; padding: 20px; border-bottom: 1px solid #e0e0e0; position: sticky; top: 0; z-index: 10; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
        h1 { font-size: 24px; color: #333; margin-bottom: 5px; }
        .progress { font-size: 14px; color: #666; margin-top: 8px; }
        .progress-bar { height: 6px; background: #e0e0e0; border-radius: 3px; margin-top: 8px; overflow: hidden; }
        .progress-fill { height: 100%; background: #4caf50; width: 0%; transition: width 0.3s; }
        .search-box { margin-top: 12px; position: relative; }
        .search-box input { width: 100%; padding: 10px; font-size: 14px; border: 1px solid #ddd; border-radius: 6px; box-sizing: border-box; }
        .search-box input:focus { outline: none; border-color: #1976d2; }
        .filter-count { font-size: 12px; color: #666; margin-top: 4px; }
        .sort-controls { margin-top: 12px; display: flex; gap: 8px; align-items: center; font-size: 14px; }
        .sort-controls label { color: #666; }
        .sort-controls select { padding: 6px 10px; border: 1px solid #ddd; border-radius: 4px; font-size: 14px; cursor: pointer; }
        .sort-controls select:focus { outline: none; border-color: #1976d2; }
        .list { max-width: 800px; margin: 0 auto; padding: 20px; }
        .item { background: white; padding: 20px; margin-bottom: 12px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); transition: all 0.3s; }
        .item.done { opacity: 0.5; }
        .item.done .merchant { text-decoration: line-through; }
        .top-row { display: flex; justify-content: space-between; align-items: start; margin-bottom: 12px; }
        .merchant { font-size: 18px; font-weight: 600; color: #1a1a1a; flex: 1; }
        .checkbox { width: 24px; height: 24px; cursor: pointer; margin-left: 12px; }
        .details { display: flex; gap: 20px; flex-wrap: wrap; margin-bottom: 12px; font-size: 14px; color: #666; }
        .detail { display: flex; align-items: center; gap: 6px; }
        .amount { color: #d32f2f; font-weight: 600; }
        .next { font-weight: 500; }
        .next.urgent { color: #d32f2f; }
        .next.soon { color: #f57c00; }
        .next.ok { color: #2e7d32; }
        .buttons { display: flex; gap: 10px; flex-wrap: wrap; }
        .buttons a { display: inline-block; padding: 10px 20px; color: white; text-decoration: none; border-radius: 6px; font-size: 14px; font-weight: 500; }
        .btn-primary { background: #1976d2; }
        .btn-primary:hover { background: #1565c0; }
        .btn-secondary { background: #757575; }
        .btn-secondary:hover { background: #616161; }
        .item.done .buttons a { background: #9e9e9e; pointer-events: none; }
        .toggle-charges { background: none; border: none; color: #1976d2; cursor: pointer; font-size: 14px; padding: 5px 0; display: flex; align-items: center; gap: 5px; margin-top: 8px; }
        .toggle-charges:hover { text-decoration: underline; }
        .triangle { display: inline-block; width: 0; height: 0; border-left: 5px solid transparent; border-right: 5px solid transparent; border-top: 6px solid #1976d2; transition: transform 0.2s; }
        .triangle.open { transform: rotate(180deg); }
        .charges-list { display: none; margin-top: 12px; padding: 12px; background: #f5f5f5; border-radius: 4px; font-size: 13px; }
        .charges-list.open { display: block; }
        .charge-item { padding: 6px 0; border-bottom: 1px solid #e0e0e0; display: flex; justify-content: space-between; }
        .charge-item:last-child { border-bottom: none; }
        .charge-date { color: #666; }
        .charge-amount { font-weight: 600; color: #d32f2f; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🔄 Update Credit Card</h1>
        <div class="progress"><span id="done-count">0</span> of <span id="total-count">0</span> completed</div>
        <div class="progress-bar"><div class="progress-fill" id="progress-fill"></div></div>
        <div class="search-box">
            <input type="text" id="search" placeholder="Search subscriptions..." oninput="filterItems()">
            <div class="filter-count" id="filter-count"></div>
        </div>
        <div class="sort-controls">
            <label>Sort by:</label>
            <select id="sort-select" onchange="sortItems()">
                <option value="status">Status (incomplete first)</option>
                <option value="amount-high">Amount (high to low)</option>
                <option value="amount-low">Amount (low to high)</option>
                <option value="date-soon">Next billing (soonest first)</option>
                <option value="date-later">Next billing (latest first)</option>
            </select>
        </div>
    </div>
    <div class="list" id="list">
'''
    
    for i, item in enumerate(subscriptions[:30]):  # Top 30 subscriptions
        merchant = item['merchant']
        url = get_vendor_url(merchant)
        next_date = item['next_billing'].strftime('%b %d, %Y')
        next_date_iso = item['next_billing'].strftime('%Y-%m-%d')
        interval_days = int(item['interval'])
        
        # Calculate urgency class
        days_until = (item['next_billing'] - TODAY).days
        if days_until < 7:
            urgency_class = 'urgent'
        elif days_until < 14:
            urgency_class = 'soon'
        else:
            urgency_class = 'ok'
        
        # Build charges list HTML
        charges_html = ''
        for charge in item['charges'][:10]:  # Show last 10 charges
            charge_date = charge['date'].strftime('%b %d, %Y')
            charge_amount = abs(charge['amount'])
            charges_html += f'<div class="charge-item"><span class="charge-date">{charge_date}</span><span class="charge-amount">${charge_amount:.2f}</span></div>'
        
        html += f'''        <div class="item" data-id="{i}" data-amount="{item['avg_amount']:.2f}" data-next-date="{next_date_iso}">
            <div class="top-row">
                <div class="merchant">{merchant}</div>
                <input type="checkbox" class="checkbox" onchange="toggleDone({i})">
            </div>
            <div class="details">
                <div class="detail"><span class="amount">${item['avg_amount']:.2f}</span> avg</div>
                <div class="detail">{item['count']} charges</div>
                <div class="detail">Every {interval_days} days</div>
                <div class="detail next {urgency_class}">Next: {next_date}</div>
            </div>
            <div class="buttons">
                <a href="{url}" target="_blank" class="btn-primary">Update Payment Method →</a>
                <a href="https://www.google.com/search?q={merchant.replace(' ', '+').replace('*', '')}+update+payment+method" target="_blank" class="btn-secondary">Search Google</a>
            </div>
            <button class="toggle-charges" onclick="toggleCharges({i})">
                <span class="triangle" id="triangle-{i}"></span>
                <span>Show charges</span>
            </button>
            <div class="charges-list" id="charges-{i}">
                {charges_html}
            </div>
        </div>
'''
    
    html += '''    </div>
    <script>
        const total = document.querySelectorAll('.item').length;
        document.getElementById('total-count').textContent = total;
        
        // Load saved progress from browser localStorage
        const saved = JSON.parse(localStorage.getItem('completed') || '{}');
        Object.keys(saved).forEach(id => {
            if (saved[id]) {
                const item = document.querySelector(`[data-id="${id}"]`);
                const checkbox = item.querySelector('.checkbox');
                item.classList.add('done');
                checkbox.checked = true;
            }
        });
        sortItems();
        updateProgress();
        updateFilterCount();
        
        function toggleDone(id) {
            const item = document.querySelector(`[data-id="${id}"]`);
            const checkbox = item.querySelector('.checkbox');
            item.classList.toggle('done');
            
            // Save progress
            const completed = JSON.parse(localStorage.getItem('completed') || '{}');
            completed[id] = checkbox.checked;
            localStorage.setItem('completed', JSON.stringify(completed));
            
            sortItems();
            updateProgress();
        }
        
        function toggleCharges(id) {
            const chargesList = document.getElementById('charges-' + id);
            const triangle = document.getElementById('triangle-' + id);
            chargesList.classList.toggle('open');
            triangle.classList.toggle('open');
        }
        
        function filterItems() {
            const query = document.getElementById('search').value.toLowerCase();
            const items = document.querySelectorAll('.item');
            
            items.forEach(item => {
                const merchant = item.querySelector('.merchant').textContent.toLowerCase();
                if (merchant.includes(query)) {
                    item.style.display = '';
                } else {
                    item.style.display = 'none';
                }
            });
            
            updateFilterCount();
        }
        
        function updateFilterCount() {
            const query = document.getElementById('search').value;
            const items = document.querySelectorAll('.item');
            const visible = Array.from(items).filter(item => item.style.display !== 'none').length;
            const countEl = document.getElementById('filter-count');
            
            if (query) {
                countEl.textContent = `Showing ${visible} of ${total} subscriptions`;
            } else {
                countEl.textContent = '';
            }
        }
        
        function sortItems() {
            const list = document.getElementById('list');
            const items = Array.from(list.querySelectorAll('.item'));
            const sortBy = document.getElementById('sort-select').value;
            
            items.sort((a, b) => {
                const aDone = a.classList.contains('done');
                const bDone = b.classList.contains('done');
                
                // Primary sort by selected option
                if (sortBy === 'status') {
                    if (aDone === bDone) return 0;
                    return aDone ? 1 : -1;
                } else if (sortBy === 'amount-high') {
                    const aAmount = parseFloat(a.dataset.amount);
                    const bAmount = parseFloat(b.dataset.amount);
                    return bAmount - aAmount;
                } else if (sortBy === 'amount-low') {
                    const aAmount = parseFloat(a.dataset.amount);
                    const bAmount = parseFloat(b.dataset.amount);
                    return aAmount - bAmount;
                } else if (sortBy === 'date-soon') {
                    const aDate = new Date(a.dataset.nextDate);
                    const bDate = new Date(b.dataset.nextDate);
                    return aDate - bDate;
                } else if (sortBy === 'date-later') {
                    const aDate = new Date(a.dataset.nextDate);
                    const bDate = new Date(b.dataset.nextDate);
                    return bDate - aDate;
                }
                return 0;
            });
            
            // Re-append in sorted order
            items.forEach(item => list.appendChild(item));
        }
        
        function updateProgress() {
            const done = document.querySelectorAll('.item.done').length;
            document.getElementById('done-count').textContent = done;
            document.getElementById('progress-fill').style.width = (done / total * 100) + '%';
        }
    </script>
</body>
</html>'''
    
    with open(output_path, 'w') as f:
        f.write(html)

def main():
    if len(sys.argv) != 3:
        print("Usage: python3 generate_subscription_tracker.py input.csv output.html")
        print("\nExample:")
        print("  python3 generate_subscription_tracker.py transactions.csv subscriptions.html")
        sys.exit(1)
    
    input_csv = sys.argv[1]
    output_html = sys.argv[2]
    
    print(f"📄 Reading transactions from: {input_csv}")
    subscriptions = parse_transactions(input_csv)
    
    print(f"✓ Found {len(subscriptions)} recurring subscriptions (3+ charges)")
    
    print(f"📝 Generating HTML: {output_html}")
    generate_html(subscriptions, output_html)
    
    print(f"✓ Done! Open {output_html} in your browser")
    print(f"  - Check off items as you update them")
    print(f"  - Progress is saved automatically")

if __name__ == '__main__':
    main()
