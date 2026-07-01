from bottle import Bottle, SimpleTemplate, redirect, request, response, run, static_file, template
from beaker.middleware import SessionMiddleware
import csv
from datetime import datetime
import html
import io
import json
import os
import sqlite3
import uuid


bottle_app = Bottle()
session_opts = {
    'session.type': 'file',
    'session.cookie_expires': 3600,
    'session.auto': True,
    'session.data_dir': os.environ.get('SESSION_DATA_DIR', './session_data'),
}
app = SessionMiddleware(bottle_app, session_opts)

DB_FILE = os.environ.get('CONTACT_FLOW_DB_FILE', './data/contact_chart.db')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'changeme')
PORT = int(os.environ.get('PORT', '8080'))

FLAT_FIELDS = [
    'username', 'author', 'address',
    'contact1_name', 'contact1_tel', 'contact1_email',
    'contact2_name', 'contact2_tel', 'contact2_email',
    'contact3_name', 'contact3_tel', 'contact3_email',
    'after_contact1_name', 'after_contact1_tel', 'after_contact1_email',
    'after_contact2_name', 'after_contact2_tel', 'after_contact2_email',
    'after_contact3_name', 'after_contact3_tel', 'after_contact3_email',
    'business_days', 'normal_hours', 'normal_method', 'after_hours', 'after_method',
    'remarks', 'owner', 'confirmation_status', 'last_confirmed_at',
]

CONTACT_SCOPES = {
    'normal': {
        'label': '通常連絡',
        'prefix': 'contact',
    },
    'after_hours': {
        'label': '時間外連絡',
        'prefix': 'after_contact',
    },
}

WEEKDAYS = [
    ('mon', '月'),
    ('tue', '火'),
    ('wed', '水'),
    ('thu', '木'),
    ('fri', '金'),
    ('sat', '土'),
    ('sun', '日'),
]
WEEKDAY_LABELS = dict(WEEKDAYS)
WEEKDAY_CODES_BY_LABEL = {label: code for code, label in WEEKDAYS}
DEFAULT_BUSINESS_DAYS = 'mon,tue,wed,thu,fri'


def now_text():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def get_db(row_factory=None):
    conn = sqlite3.connect(DB_FILE)
    conn.execute('PRAGMA foreign_keys = ON')
    if row_factory:
        conn.row_factory = row_factory
    return conn


def h(value):
    return html.escape(str(value or ''), quote=True)


def set_html_response():
    response.content_type = 'text/html; charset=UTF-8'


def form_value(name, default=''):
    return request.forms.getunicode(name) or default


def table_exists(conn, table_name):
    cur = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    )
    return cur.fetchone() is not None


def ensure_customer_columns(conn):
    columns = {row[1] for row in conn.execute('PRAGMA table_info(customers)').fetchall()}
    required_columns = {
        'business_days': f"TEXT NOT NULL DEFAULT '{DEFAULT_BUSINESS_DAYS}'",
    }
    for column, column_type in required_columns.items():
        if column not in columns:
            conn.execute(f'ALTER TABLE customers ADD COLUMN {column} {column_type}')


def init_db():
    db_dir = os.path.dirname(DB_FILE)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    os.makedirs(session_opts['session.data_dir'], exist_ok=True)

    with get_db() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_name TEXT NOT NULL,
                author TEXT NOT NULL DEFAULT '',
                address TEXT NOT NULL DEFAULT '',
                business_days TEXT NOT NULL DEFAULT 'mon,tue,wed,thu,fri',
                normal_hours TEXT NOT NULL DEFAULT '',
                normal_method TEXT NOT NULL DEFAULT '',
                after_hours TEXT NOT NULL DEFAULT '',
                after_method TEXT NOT NULL DEFAULT '',
                remarks TEXT NOT NULL DEFAULT '',
                owner TEXT NOT NULL DEFAULT '',
                confirmation_status TEXT NOT NULL DEFAULT '未確認',
                last_confirmed_at TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS contact_points (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                scope TEXT NOT NULL DEFAULT 'normal',
                priority INTEGER NOT NULL,
                contact_name TEXT NOT NULL DEFAULT '',
                tel TEXT NOT NULL DEFAULT '',
                email TEXT NOT NULL DEFAULT '',
                method_note TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(customer_id) REFERENCES customers(id) ON DELETE CASCADE,
                UNIQUE(customer_id, scope, priority)
            )
        ''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_customers_name ON customers(customer_name)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_contact_points_customer ON contact_points(customer_id)')
        ensure_customer_columns(conn)
        migrate_legacy_contacts(conn)
        normalize_stored_business_days(conn)


def normalize_stored_business_days(conn):
    if not table_exists(conn, 'customers'):
        return
    rows = conn.execute('SELECT id, business_days FROM customers').fetchall()
    for row_id, business_days in rows:
        normalized = ','.join(normalize_business_days(business_days))
        if normalized and normalized != business_days:
            conn.execute(
                'UPDATE customers SET business_days = ? WHERE id = ?',
                (normalized, row_id),
            )


def migrate_legacy_contacts(conn):
    if not table_exists(conn, 'contacts'):
        return
    if conn.execute('SELECT COUNT(*) FROM customers').fetchone()[0] > 0:
        return

    conn.row_factory = sqlite3.Row
    legacy_rows = conn.execute('SELECT * FROM contacts ORDER BY id').fetchall()
    for row in legacy_rows:
        created_at = row['timestamp'] if 'timestamp' in row.keys() and row['timestamp'] else now_text()
        conn.execute('''
            INSERT INTO customers (
                id, customer_name, author, address, business_days, normal_hours, normal_method,
                after_hours, after_method, remarks, owner, confirmation_status,
                last_confirmed_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            row['id'], row['username'] or '', row['author'] or '', row['address'] or '',
            DEFAULT_BUSINESS_DAYS, row['normal_hours'] or '', row['normal_method'] or '',
            row['after_hours'] or '', row['after_method'] or '',
            row['remarks'] if 'remarks' in row.keys() and row['remarks'] else '',
            row['owner'] if 'owner' in row.keys() and row['owner'] else '',
            row['confirmation_status'] if 'confirmation_status' in row.keys() and row['confirmation_status'] else '未確認',
            row['last_confirmed_at'] if 'last_confirmed_at' in row.keys() and row['last_confirmed_at'] else '',
            created_at, created_at,
        ))
        for priority in (1, 2, 3):
            name = row[f'contact{priority}_name'] or ''
            tel = row[f'contact{priority}_tel'] or ''
            email = row[f'contact{priority}_email'] or ''
            if name or tel or email:
                conn.execute('''
                    INSERT INTO contact_points (
                        customer_id, scope, priority, contact_name, tel, email,
                        created_at, updated_at
                    ) VALUES (?, 'normal', ?, ?, ?, ?, ?, ?)
                ''', (row['id'], priority, name, tel, email, created_at, created_at))
        for priority in (1, 2, 3):
            name_key = f'after_contact{priority}_name'
            tel_key = f'after_contact{priority}_tel'
            email_key = f'after_contact{priority}_email'
            if name_key not in row.keys():
                continue
            name = row[name_key] or ''
            tel = row[tel_key] or ''
            email = row[email_key] or ''
            if name or tel or email:
                conn.execute('''
                    INSERT INTO contact_points (
                        customer_id, scope, priority, contact_name, tel, email,
                        created_at, updated_at
                    ) VALUES (?, 'after_hours', ?, ?, ?, ?, ?, ?)
                ''', (row['id'], priority, name, tel, email, created_at, created_at))
    conn.row_factory = None


def fetch_contact_points(conn, customer_id, scope=None):
    conn.row_factory = sqlite3.Row
    if scope:
        return conn.execute('''
            SELECT * FROM contact_points
            WHERE customer_id = ? AND scope = ?
            ORDER BY priority
        ''', (customer_id, scope)).fetchall()
    return conn.execute('''
        SELECT * FROM contact_points
        WHERE customer_id = ?
        ORDER BY priority
    ''', (customer_id,)).fetchall()


def flatten_customer(conn, customer):
    data = dict(customer)
    data['username'] = data.pop('customer_name')
    data['business_days_label'] = format_business_days(data.get('business_days'))
    data['contact_groups'] = {}
    for scope, config in CONTACT_SCOPES.items():
        points = {p['priority']: p for p in fetch_contact_points(conn, customer['id'], scope)}
        group = []
        for priority in (1, 2, 3):
            point = points.get(priority)
            item = {
                'priority': priority,
                'name': point['contact_name'] if point else '',
                'tel': point['tel'] if point else '',
                'email': point['email'] if point else '',
            }
            group.append(item)
            prefix = config['prefix']
            data[f'{prefix}{priority}_name'] = item['name']
            data[f'{prefix}{priority}_tel'] = item['tel']
            data[f'{prefix}{priority}_email'] = item['email']
        data['contact_groups'][scope] = group
    data['timestamp'] = data.get('updated_at', '')
    return data


def fetch_contact(contact_id):
    with get_db(sqlite3.Row) as conn:
        row = conn.execute('SELECT * FROM customers WHERE id = ?', (contact_id,)).fetchone()
        return flatten_customer(conn, row) if row else None


def search_contacts(keyword=''):
    params = []
    where = ''
    if keyword:
        like = f'%{keyword}%'
        fields = [
            'c.customer_name', 'c.author', 'c.address', 'c.business_days', 'c.normal_hours',
            'c.normal_method', 'c.after_hours', 'c.after_method', 'c.remarks',
            'c.owner', 'c.confirmation_status',
        ]
        where = 'WHERE ' + ' OR '.join([f'{field} LIKE ? COLLATE NOCASE' for field in fields])
        where += ''' OR EXISTS (
            SELECT 1 FROM contact_points p
            WHERE p.customer_id = c.id
              AND (
                p.contact_name LIKE ? COLLATE NOCASE OR
                p.tel LIKE ? COLLATE NOCASE OR
                p.email LIKE ? COLLATE NOCASE OR
                p.method_note LIKE ? COLLATE NOCASE
              )
        )'''
        params = [like] * (len(fields) + 4)

    with get_db(sqlite3.Row) as conn:
        rows = conn.execute(f'SELECT c.* FROM customers c {where} ORDER BY c.id DESC', params).fetchall()
        return [flatten_customer(conn, row) for row in rows]


def build_contact_values():
    values = {field: form_value(field) for field in FLAT_FIELDS}
    selected_days = request.forms.getall('business_days')
    values['business_days'] = ','.join(selected_days)
    start_time = form_value('normal_start_time')
    end_time = form_value('normal_end_time')
    if start_time or end_time:
        values['normal_hours'] = f'{start_time}～{end_time}'
    values['confirmation_status'] = values['confirmation_status'] or '未確認'
    if values['after_hours'] == '否':
        values['after_method'] = ''
        for priority in (1, 2, 3):
            values[f'after_contact{priority}_name'] = ''
            values[f'after_contact{priority}_tel'] = ''
            values[f'after_contact{priority}_email'] = ''
    if values['confirmation_status'] == '確認済' and not values['last_confirmed_at']:
        values['last_confirmed_at'] = now_text()[:10]
    return values


def split_normal_hours(value):
    value = value or ''
    if '～' in value:
        start, end = value.split('～', 1)
        return start.strip(), end.strip()
    if '-' in value:
        start, end = value.split('-', 1)
        return start.strip(), end.strip()
    return '', ''


def repair_mojibake(value):
    if not value:
        return ''
    try:
        return value.encode('latin1').decode('utf-8')
    except UnicodeError:
        return value


def normalize_business_days(value):
    repaired = repair_mojibake(value or '')
    normalized = []
    for item in repaired.split(','):
        item = item.strip()
        if not item:
            continue
        if item in WEEKDAY_LABELS:
            normalized.append(item)
        elif item in WEEKDAY_CODES_BY_LABEL:
            normalized.append(WEEKDAY_CODES_BY_LABEL[item])
    return normalized


def format_business_days(value):
    return '・'.join([WEEKDAY_LABELS[day] for day in normalize_business_days(value)])


def validate_contact_values(values):
    required_fields = [
        'username', 'author', 'address', 'contact1_name', 'contact1_tel',
        'contact1_email', 'normal_hours', 'normal_method', 'after_hours',
        'confirmation_status',
    ]
    if values.get('after_hours') == '要':
        required_fields.append('after_method')
    for field in required_fields:
        if not values.get(field):
            return f'{field} が未入力です'
    return None


def save_contact_points(conn, customer_id, values):
    now = now_text()
    conn.execute('DELETE FROM contact_points WHERE customer_id = ?', (customer_id,))
    for scope, config in CONTACT_SCOPES.items():
        prefix = config['prefix']
        for priority in (1, 2, 3):
            name = values.get(f'{prefix}{priority}_name', '')
            tel = values.get(f'{prefix}{priority}_tel', '')
            email = values.get(f'{prefix}{priority}_email', '')
            if name or tel or email:
                conn.execute('''
                    INSERT INTO contact_points (
                        customer_id, scope, priority, contact_name, tel, email,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (customer_id, scope, priority, name, tel, email, now, now))


def create_contact(values):
    now = now_text()
    values['business_days'] = values.get('business_days') or DEFAULT_BUSINESS_DAYS
    with get_db() as conn:
        cur = conn.execute('''
            INSERT INTO customers (
                customer_name, author, address, business_days, normal_hours, normal_method,
                after_hours, after_method, remarks, owner, confirmation_status,
                last_confirmed_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            values['username'], values['author'], values['address'],
            values['business_days'], values['normal_hours'], values['normal_method'], values['after_hours'],
            values['after_method'], values['remarks'], values['owner'],
            values['confirmation_status'], values['last_confirmed_at'], now, now,
        ))
        save_contact_points(conn, cur.lastrowid, values)


def update_contact(contact_id, values):
    now = now_text()
    with get_db() as conn:
        conn.execute('''
            UPDATE customers SET
                customer_name = ?, author = ?, address = ?, business_days = ?, normal_hours = ?,
                normal_method = ?, after_hours = ?, after_method = ?,
                remarks = ?, owner = ?, confirmation_status = ?,
                last_confirmed_at = ?, updated_at = ?
            WHERE id = ?
        ''', (
            values['username'], values['author'], values['address'],
            values['business_days'], values['normal_hours'], values['normal_method'], values['after_hours'],
            values['after_method'], values['remarks'], values['owner'],
            values['confirmation_status'], values['last_confirmed_at'], now, contact_id,
        ))
        save_contact_points(conn, contact_id, values)


def mattermost_detail(row):
    lines = [
        f"**{row['username']} 連絡先**",
        f"- 構築担当者: {row['author'] or '未設定'}",
        f"- 情報オーナー: {row['owner'] or '未設定'}",
        f"- 確認ステータス: {row['confirmation_status'] or '未確認'}",
        f"- 最終確認日: {row['last_confirmed_at'] or '未確認'}",
    ]
    lines.extend([
        f"- 営業日: {row['business_days_label'] or '未設定'}",
        f"- 通常受付時間: {row['normal_hours'] or '未設定'}",
        f"- 連絡方法: {row['normal_method'] or '未設定'}",
        f"- 受付時間外: {row['after_hours'] or '未設定'} / {row['after_method'] or '未設定'}",
    ])
    for scope, config in CONTACT_SCOPES.items():
        points = [p for p in row['contact_groups'][scope] if p['name'] or p['tel'] or p['email']]
        if not points:
            continue
        lines.append(f"**{config['label']}**")
        for point in points:
            lines.append(
                f"- 第{point['priority']}連絡先: {point['name'] or '未設定'} / "
                f"{point['tel'] or '-'} / {point['email'] or '-'}"
            )
    if row['remarks']:
        lines.append(f"- 備考: {row['remarks']}")
    return '\n'.join(lines)


def mattermost_candidates(rows):
    lines = ['複数の候補が見つかりました。IDまたは詳しいキーワードで絞り込んでください。']
    for row in rows[:10]:
        lines.append(
            f"- ID: {row['id']} / {row['username']} / 担当: {row['author'] or '-'} / "
            f"状態: {row['confirmation_status'] or '未確認'}"
        )
    if len(rows) > 10:
        lines.append(f'...ほか {len(rows) - 10} 件')
    return '\n'.join(lines)


def render_modal_form(content, csrf_token, action_url):
    set_html_response()
    tmpl = SimpleTemplate('''
    <html lang="ja">
    <head>
        <title>顧客別連絡体制図</title>
        <link rel="stylesheet" href="/static/modal-style.css">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    </head>
        <div id="modal" style="display:block; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.7);" onclick="if(event.target.id==='modal'){ window.location.href='/'; }">
          <div style="background:#f9f9f9; border-radius:8px; box-shadow:0 0 20px rgba(0,0,0,0.2); margin:4% auto; padding:24px; width:min(760px, 92vw); max-height:90vh; overflow-y:auto; position:relative;" onclick="event.stopPropagation();">
            <meta charset="utf-8">
            <h2 style="margin-bottom:20px; text-align:center; color:#333;">連絡体制入力</h2>
            <form method="post" action="{{action_url}}" accept-charset="UTF-8" style="display:flex; flex-direction:column; gap:10px;">
                <input type="hidden" name="csrf_token" value="{{csrf_token}}" />
                {{!content}}
                <div style="display:flex; justify-content:space-between;">
                    <input type="submit" value="保存" style="padding:8px 16px; border:none; background:#4CAF50; color:#fff; border-radius:4px; cursor:pointer;" />
                    <button type="button" onclick="window.location.href='/'" style="padding:8px 16px; border:none; background:#f44336; color:#fff; border-radius:4px; cursor:pointer;">閉じる</button>
                </div>
            </form>
            <script>
              function toggleAfterHoursFields() {
                const select = document.querySelector('select[name="after_hours"]');
                const block = document.getElementById('after-hours-detail');
                const method = document.querySelector('input[name="after_method"]');
                if (!select || !block || !method) return;
                const enabled = select.value === '要';
                block.style.display = enabled ? 'block' : 'none';
                method.required = enabled;
              }
              document.addEventListener('change', function(event) {
                if (event.target && event.target.name === 'after_hours') {
                  toggleAfterHoursFields();
                }
              });
              toggleAfterHoursFields();
            </script>
          </div>
        </div>
    ''')
    return tmpl.render(content=content, csrf_token=csrf_token, action_url=action_url)


def render_form_content(row=None):
    row = row or {field: '' for field in FLAT_FIELDS}
    row.setdefault('confirmation_status', '未確認')
    row['business_days'] = row.get('business_days') or DEFAULT_BUSINESS_DAYS
    selected_days = set(normalize_business_days(row['business_days']))
    has_after_contacts = any(row.get(f'after_contact{priority}_{field}') for priority in (1, 2, 3) for field in ('name', 'tel', 'email'))
    has_confirm_detail = row.get('owner') or row.get('last_confirmed_at') or row.get('remarks') or row.get('confirmation_status') not in ('', '未確認')
    start_time, end_time = split_normal_hours(row.get('normal_hours'))
    start_time = start_time or '09:00'
    end_time = end_time or '18:00'
    weekday_inputs = ''.join([
        f'<label><input type="checkbox" name="business_days" value="{code}" {"checked" if code in selected_days else ""}> {label}</label>'
        for code, label in WEEKDAYS
    ])
    return f'''
        <label>ユーザー名 <input name="username" value="{h(row.get('username'))}" required /></label>
        <label>構築担当者 <input name="author" value="{h(row.get('author'))}" required /></label>
        <label>住所 <input name="address" value="{h(row.get('address'))}" required /></label>
        <fieldset style="border:1px solid #ddd; padding:12px; border-radius:6px;">
          <legend style="font-size:14px; font-weight:bold; width:auto; padding:0 6px;">通常連絡先</legend>
          <div style="display:flex; gap:10px; align-items:center;">
            <label>第一連絡先名 <input name="contact1_name" value="{h(row.get('contact1_name'))}" required /></label>
            <label>電話 <input name="contact1_tel" value="{h(row.get('contact1_tel'))}" required /></label>
            <label>Email <input name="contact1_email" value="{h(row.get('contact1_email'))}" required /></label>
          </div>
          <div style="display:flex; gap:10px; align-items:center;">
            <label>第二連絡先名 <input name="contact2_name" value="{h(row.get('contact2_name'))}" /></label>
            <label>電話 <input name="contact2_tel" value="{h(row.get('contact2_tel'))}" /></label>
            <label>Email <input name="contact2_email" value="{h(row.get('contact2_email'))}" /></label>
          </div>
          <div style="display:flex; gap:10px; align-items:center;">
            <label>第三連絡先名 <input name="contact3_name" value="{h(row.get('contact3_name'))}" /></label>
            <label>電話 <input name="contact3_tel" value="{h(row.get('contact3_tel'))}" /></label>
            <label>Email <input name="contact3_email" value="{h(row.get('contact3_email'))}" /></label>
          </div>
        </fieldset>
        <label>営業日</label>
        <div class="checkbox-row">
          {weekday_inputs}
        </div>
        <label>通常受付時間</label>
        <div style="display:flex; gap:10px; align-items:center;">
          <label>開始 <input type="time" name="normal_start_time" value="{h(start_time)}" required /></label>
          <label>終了 <input type="time" name="normal_end_time" value="{h(end_time)}" required /></label>
        </div>
        <input type="hidden" name="normal_hours" value="{h(row.get('normal_hours'))}" />
        <label>連絡方法 <input name="normal_method" value="{h(row.get('normal_method'))}" required /></label>
        <label>受付時間外の連絡要否
            <select name="after_hours" required>
                <option value="要" {'selected' if row.get('after_hours') == '要' else ''}>要</option>
                <option value="否" {'selected' if row.get('after_hours') == '否' else ''}>否</option>
            </select>
        </label>
        <div id="after-hours-detail">
          <label>受付時間外連絡方法 <input name="after_method" value="{h(row.get('after_method'))}" /></label>
          <details {'open' if has_after_contacts else ''}>
            <summary>時間外連絡先を追加</summary>
            <fieldset style="border:1px solid #ddd; padding:12px; border-radius:6px; margin-top:10px;">
              <div style="display:flex; gap:10px; align-items:center;">
                <label>第一連絡先名 <input name="after_contact1_name" value="{h(row.get('after_contact1_name'))}" /></label>
                <label>電話 <input name="after_contact1_tel" value="{h(row.get('after_contact1_tel'))}" /></label>
                <label>Email <input name="after_contact1_email" value="{h(row.get('after_contact1_email'))}" /></label>
              </div>
              <div style="display:flex; gap:10px; align-items:center;">
                <label>第二連絡先名 <input name="after_contact2_name" value="{h(row.get('after_contact2_name'))}" /></label>
                <label>電話 <input name="after_contact2_tel" value="{h(row.get('after_contact2_tel'))}" /></label>
                <label>Email <input name="after_contact2_email" value="{h(row.get('after_contact2_email'))}" /></label>
              </div>
              <div style="display:flex; gap:10px; align-items:center;">
                <label>第三連絡先名 <input name="after_contact3_name" value="{h(row.get('after_contact3_name'))}" /></label>
                <label>電話 <input name="after_contact3_tel" value="{h(row.get('after_contact3_tel'))}" /></label>
                <label>Email <input name="after_contact3_email" value="{h(row.get('after_contact3_email'))}" /></label>
              </div>
            </fieldset>
          </details>
        </div>
        <details {'open' if has_confirm_detail else ''}>
          <summary>確認情報・備考</summary>
          <div style="margin-top:10px;">
            <label>情報オーナー <input name="owner" value="{h(row.get('owner'))}" /></label>
            <label>確認ステータス
                <select name="confirmation_status" required>
                    <option value="未確認" {'selected' if row.get('confirmation_status') == '未確認' else ''}>未確認</option>
                    <option value="確認済" {'selected' if row.get('confirmation_status') == '確認済' else ''}>確認済</option>
                    <option value="要更新" {'selected' if row.get('confirmation_status') == '要更新' else ''}>要更新</option>
                </select>
            </label>
            <label>最終確認日 <input type="date" name="last_confirmed_at" value="{h(row.get('last_confirmed_at'))}" /></label>
            <label>備考 <input name="remarks" value="{h(row.get('remarks'))}" /></label>
          </div>
        </details>
    '''


@bottle_app.route('/static/<filepath:path>')
def server_static(filepath):
    return static_file(filepath, root='./static')


@bottle_app.post('/login')
def login():
    s = request.environ.get('beaker.session')
    username = request.forms.getunicode('username')
    password = request.forms.getunicode('password')
    if username == 'admin' and password == ADMIN_PASSWORD:
        s['user'] = username
        s.save()
    redirect('/')


@bottle_app.get('/logout')
def logout():
    s = request.environ.get('beaker.session')
    s.delete()
    redirect('/')


@bottle_app.get('/detail/<id:int>')
def detail(id):
    set_html_response()
    s = request.environ.get('beaker.session')
    row = fetch_contact(id)
    if not row:
        return '<p>データが見つかりません</p>'
    return template('''
        <div class="contact-detail">
            <div class="d-flex justify-content-between align-items-start mb-3">
                <div>
                    <h2 class="h4 mb-1">{{row['username']}}</h2>
                    <div class="text-muted">構築担当者: {{row['author'] or '未設定'}} / 情報オーナー: {{row['owner'] or '未設定'}}</div>
                </div>
                <span class="badge bg-{{'success' if row['confirmation_status'] == '確認済' else 'warning'}} text-{{'light' if row['confirmation_status'] == '確認済' else 'dark'}}">
                    {{row['confirmation_status'] or '未確認'}}
                </span>
            </div>
            <div class="alert alert-light border py-2">
                最終確認日: {{row['last_confirmed_at'] or '未確認'}} / 更新日時: {{row['timestamp'] or '未設定'}}
            </div>
            <div class="border rounded p-3 mb-3 bg-white">
                <p class="mb-1">住所: {{row['address'] or '未設定'}}</p>
                <p class="mb-1">営業日: {{row['business_days_label'] or '未設定'}}</p>
                <p class="mb-1">通常受付時間: {{row['normal_hours'] or '未設定'}} / 連絡方法: {{row['normal_method'] or '未設定'}}</p>
                <p class="mb-0">受付時間外: {{row['after_hours'] or '未設定'}} / 連絡方法: {{row['after_method'] or '未設定'}}</p>
            </div>
            % for scope, config in contact_scopes.items():
                <h3 class="h6 mt-3">{{config['label']}}</h3>
                % has_point = False
                % for point in row['contact_groups'][scope]:
                    % if point['name'] or point['tel'] or point['email']:
                        % has_point = True
                        <div class="border rounded p-3 mb-2 bg-white">
                            <div class="fw-bold mb-2">第{{point['priority']}}連絡先: {{point['name'] or '名称未設定'}}</div>
                            <div class="d-flex gap-2 flex-wrap">
                                % if point['tel']:
                                    <a class="btn btn-sm btn-outline-primary" href="tel:{{point['tel']}}">電話: {{point['tel']}}</a>
                                % end
                                % if point['email']:
                                    <a class="btn btn-sm btn-outline-secondary" href="mailto:{{point['email']}}">メール: {{point['email']}}</a>
                                % end
                            </div>
                        </div>
                    % end
                % end
                % if not has_point:
                    <div class="text-muted small mb-2">未設定</div>
                % end
            % end
            <div class="mt-3">
                % if row['remarks']:
                    <p class="mb-1">備考: {{row['remarks']}}</p>
                % end
            </div>
            % if user == 'admin':
                <p class="mt-3">
                    <a class="btn btn-sm btn-outline-primary" href="/editform/{{row['id']}}">編集</a>
                    <a class="btn btn-sm btn-outline-danger" href="/delete/{{row['id']}}" onclick="return confirm('本当に削除しますか？');">削除</a>
                </p>
            % end
        </div>
    ''', row=row, contact_scopes=CONTACT_SCOPES, user=s.get('user', ''))


@bottle_app.get('/form')
def form():
    set_html_response()
    s = request.environ.get('beaker.session')
    if s.get('user') != 'admin':
        return '権限がありません'
    return render_modal_form(render_form_content(), s.get('csrf_token', ''), '/form')


@bottle_app.post('/form')
def save_form():
    s = request.environ.get('beaker.session')
    if s.get('user') != 'admin' or request.forms.getunicode('csrf_token') != s.get('csrf_token'):
        return '不正なアクセス'
    values = build_contact_values()
    error = validate_contact_values(values)
    if error:
        return error
    create_contact(values)
    redirect('/')


@bottle_app.get('/editform/<id:int>')
def edit_form(id):
    set_html_response()
    s = request.environ.get('beaker.session')
    if s.get('user') != 'admin':
        return '権限がありません'
    row = fetch_contact(id)
    if not row:
        return 'データが見つかりません'
    return render_modal_form(render_form_content(row), s.get('csrf_token', ''), f'/edit/{id}')


@bottle_app.post('/edit/<id:int>')
def update_entry(id):
    s = request.environ.get('beaker.session')
    if s.get('user') != 'admin':
        return '権限がありません'
    values = build_contact_values()
    error = validate_contact_values(values)
    if error:
        return error
    update_contact(id, values)
    redirect('/')


@bottle_app.get('/delete/<id:int>')
def delete_entry(id):
    s = request.environ.get('beaker.session')
    if s.get('user') != 'admin':
        return '権限がありません'
    with get_db() as conn:
        conn.execute('DELETE FROM customers WHERE id = ?', (id,))
    redirect('/')


@bottle_app.get('/')
def index():
    set_html_response()
    s = request.environ.get('beaker.session')
    token = str(uuid.uuid4())
    s['csrf_token'] = token
    s.save()
    query = request.query.q or ''
    userlist = search_contacts(query)
    return template('index', user=s.get('user', ''), userlist=userlist, query=query)


@bottle_app.get('/api/detail/<id:int>')
def api_detail(id):
    row = fetch_contact(id)
    if not row:
        response.status = 404
        return json.dumps({'error': 'データが見つかりません'}, ensure_ascii=False)
    response.content_type = 'application/json; charset=UTF-8'
    return json.dumps(row, ensure_ascii=False)


@bottle_app.get('/api/list')
def api_list():
    rows = search_contacts('')
    response.content_type = 'application/json; charset=UTF-8'
    return json.dumps({
        'contacts': [
            {
                'id': row['id'],
                'username': row['username'],
                'author': row['author'],
                'owner': row['owner'],
                'confirmation_status': row['confirmation_status'],
                'last_confirmed_at': row['last_confirmed_at'],
            }
            for row in rows
        ]
    }, ensure_ascii=False)


@bottle_app.get('/api/search')
def api_search():
    rows = search_contacts(request.query.get('q', ''))
    response.content_type = 'application/json; charset=UTF-8'
    return json.dumps({'results': rows}, ensure_ascii=False)


@bottle_app.post('/api/search')
def api_search_mattermost():
    text = request.forms.getunicode('text', '').strip()
    trigger = request.forms.getunicode('trigger_word', '').strip()
    keyword = text[len(trigger):].strip() if trigger and text.startswith(trigger) else text
    if not keyword:
        return json.dumps({'text': '検索キーワードを指定してください'}, ensure_ascii=False)
    if keyword.isdigit():
        row = fetch_contact(int(keyword))
        if not row:
            return json.dumps({'text': f'ID {keyword} の連絡先は見つかりませんでした'}, ensure_ascii=False)
        return json.dumps({'text': mattermost_detail(row)}, ensure_ascii=False)
    rows = search_contacts(keyword)
    if not rows:
        return json.dumps({'text': f'「{keyword}」に一致する連絡先は見つかりませんでした'}, ensure_ascii=False)
    if len(rows) == 1:
        return json.dumps({'text': mattermost_detail(rows[0])}, ensure_ascii=False)
    return json.dumps({'text': mattermost_candidates(rows)}, ensure_ascii=False)


@bottle_app.get('/admin/export')
def admin_export():
    s = request.environ.get('beaker.session')
    if s.get('user') != 'admin':
        response.status = 403
        return '権限がありません'
    output = io.StringIO()
    fieldnames = ['id'] + FLAT_FIELDS + ['timestamp']
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for row in search_contacts(''):
        writer.writerow({key: row.get(key, '') for key in fieldnames})
    response.content_type = 'text/csv; charset=UTF-8'
    response.headers['Content-Disposition'] = 'attachment; filename="contacts_export.csv"'
    return output.getvalue()


@bottle_app.post('/admin/import')
def admin_import():
    s = request.environ.get('beaker.session')
    if s.get('user') != 'admin':
        response.status = 403
        return '権限がありません'
    upload = request.files.get('csv_file')
    if not upload:
        response.status = 400
        return 'CSVファイルが必要です'
    data = upload.file.read().decode('utf-8').splitlines()
    reader = csv.DictReader(data)
    for row in reader:
        values = {field: row.get(field, '') for field in FLAT_FIELDS}
        values['confirmation_status'] = values['confirmation_status'] or '未確認'
        create_contact(values)
    return 'インポートが完了しました'


if __name__ == '__main__':
    init_db()
    run(app=app, host='0.0.0.0', port=PORT, debug=True)
