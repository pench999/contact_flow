from bottle import Bottle, template, request, redirect, run, response, SimpleTemplate, static_file
from beaker.middleware import SessionMiddleware
import sqlite3
import os
from datetime import datetime
import uuid
import json
import csv
import io
import locale

bottle_app = Bottle()
session_opts = {
    'session.type': 'file',
    'session.cookie_expires': 3600,
    'session.auto': True,
    'session.data_dir': './session_data'
}
app = SessionMiddleware(bottle_app, session_opts)
DB_FILE = './data/contact_chart.db'
ADMIN_PASSWORD = 'changeme'

def init_db():
    if not os.path.exists(DB_FILE):
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute('''
                CREATE TABLE contacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT,
                    author TEXT,
                    address TEXT,
                    contact1_name TEXT,
                    contact1_tel TEXT,
                    contact1_email TEXT,
                    contact2_name TEXT,
                    contact2_tel TEXT,
                    contact2_email TEXT,
                    contact3_name TEXT,
                    contact3_tel TEXT,
                    contact3_email TEXT,
                    normal_hours TEXT,
                    normal_method TEXT,
                    after_hours TEXT,
                    after_method TEXT,
                    remarks TEXT,
                    timestamp TEXT,
                    after_contact1_name TEXT,
                    after_contact1_tel TEXT,
                    after_contact1_email TEXT,
                    after_contact2_name TEXT,
                    after_contact2_tel TEXT,
                    after_contact2_email TEXT,
                    after_contact3_name TEXT,
                    after_contact3_tel TEXT,
                    after_contact3_email TEXT
                )
            ''')

def render_modal_form(content, csrf_token, action_url):
    tmpl = SimpleTemplate('''
    <html lang="ja">
    <head>
        <title>顧客別連絡体制くん</title>
        <link rel="stylesheet" href="/static/modal-style.css">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    </head>
        <div id="modal" style="display:block; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.7);" onclick="if(event.target.id==='modal'){ window.location.href='/'; }">
          <div style="background:#f9f9f9; border-radius:8px; box-shadow:0 0 20px rgba(0,0,0,0.2); margin:5% auto; padding:30px; width:40%; position:relative;" onclick="event.stopPropagation();">
            <meta charset="utf-8">
            <h2 style="margin-bottom:20px; text-align:center; color:#333;">連絡体制入力</h2>
            <form method="post" action="{{action_url}}" saccept-charset="UTF-8" style="display:flex; flex-direction:column; gap:10px;">
                <input type="hidden" name="csrf_token" value="{{csrf_token}}" />
                {{!content}}
                <div style="display:flex; justify-content:space-between;">
                    <input type="submit" value="保存" style="padding:8px 16px; border:none; background:#4CAF50; color:#fff; border-radius:4px; cursor:pointer;" />
                    <button type="button" onclick="window.location.href='/'" style="padding:8px 16px; border:none; background:#f44336; color:#fff; border-radius:4px; cursor:pointer;">閉じる</button>
                </div>
            </form>
          </div>
        </div>
    ''')
    return tmpl.render(content=content, csrf_token=csrf_token, action_url=action_url)

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
    s = request.environ.get('beaker.session')
    user = s.get('user', '')
    with sqlite3.connect(DB_FILE) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM contacts WHERE id = ?", (id,))
        row = cur.fetchone()
    if not row:
        return "<p>データが見つかりません</p>"
    return template('''
        <div>
            <h2>{{row[1]}} (構築担当者: {{row[2]}})</h2>
            <p>住所: {{row[3]}}</p>
            <p>第一連絡先: {{row[4]}} / TEL: {{row[5]}} / Email: {{row[6]}}</p>
            <p>第二連絡先: {{row[7]}} / TEL: {{row[8]}} / Email: {{row[9]}}</p>
            <p>第三連絡先: {{row[10]}} / TEL: {{row[11]}} / Email: {{row[12]}}</p>
            <p>通常受付時間: {{row[13]}}</p>
            <p>連絡方法: {{row[14]}}</p>
            <p>時間外連絡: {{row[15]}}</p>
            <p>時間外連絡方法: {{row[16]}}</p>
            <p>時間外第一連絡先: {{row[19]}} / TEL: {{row[20]}} / Email: {{row[21]}}</p>
            <p>時間外第二連絡先: {{row[22]}} / TEL: {{row[23]}} / Email: {{row[24]}}</p>
            <p>時間外第三連絡先: {{row[25]}} / TEL: {{row[26]}} / Email: {{row[27]}}</p>
            <p>登録日時: {{row[18]}}</p>
            % if user == 'admin':
                <p>
                    <a href="/editform/{{row[0]}}">[編集]</a>
                    <a href="/delete/{{row[0]}}" onclick="return confirm('本当に削除しますか？');">[削除]</a>
                </p>
            % end
        </div>
    ''', row=row, user=user)

@bottle_app.get('/form')
def form():
    s = request.environ.get('beaker.session')
    if s.get('user') != 'admin':
        return "権限がありません"
    csrf_token = s.get('csrf_token', '')
    content = '''
        <label>ユーザー名 <input name="username" required /></label>
        <label>構築担当者 <input name="author" required /></label>
        <label>住所 <input name="address" required /></label>
        <div style="display: flex; gap: 10px; align-items: center;">
          <label>第一連絡先名 <input name="contact1_name" required /></label>
          <label>電話 <input name="contact1_tel" required /></label>
          <label>Email <input name="contact1_email" required /></label>
       </div>

       <div style="display: flex; gap: 10px; align-items: center;">
         <label>第二連絡先名 <input name="contact2_name" required /></label>
         <label>電話 <input name="contact2_tel" required /></label>
         <label>Email <input name="contact2_email" required /></label>
       </div>

       <div style="display: flex; gap: 10px; align-items: center;">
         <label>第三連絡先名 <input name="contact3_name" required /></label>
         <label>電話 <input name="contact3_tel" required /></label>
         <label>Email <input name="contact3_email" required /></label>
       </div>
        <label>通常受付時間 <input name="normal_hours" required /></label>
        <label>連絡方法 <input name="normal_method" required /></label>
        <label>時間外の連絡要否 
            <select name="after_hours" required>
                <option value="要">要</option>
                <option value="否">否</option>
            </select>
        </label>
        <label>時間外連絡方法 <input name="after_method" required /></label>
        <div style="display: flex; gap: 10px; align-items: center;">
          <label>時間外第一連絡先名 <input name="after_contact1_name" required /></label>
          <label>電話 <input name="after_contact1_tel" required /></label>
          <label>Email <input name="after_contact1_email" required /></label>
       </div>

       <div style="display: flex; gap: 10px; align-items: center;">
         <label>時間外第二連絡先名 <input name="after_contact2_name" required /></label>
         <label>電話 <input name="after_contact2_tel" required /></label>
         <label>Email <input name="after_contact2_email" required /></label>
       </div>

       <div style="display: flex; gap: 10px; align-items: center;">
         <label>時間外第三連絡先名 <input name="after_contact3_name" required /></label>
         <label>電話 <input name="after_contact3_tel" required /></label>
         <label>Email <input name="after_contact3_email" required /></label>
       </div>
    '''
    return render_modal_form(content, csrf_token, '/form')

@bottle_app.post('/form')
def save_form():
    s = request.environ.get('beaker.session')
    if s.get('user') != 'admin' or request.forms.getunicode('csrf_token') != s.get('csrf_token'):
        return "不正なアクセス"
    # デバッグ出力: フォームから受け取った値を確認
    print("DEBUG username:", request.forms.getunicode('username'), flush=True)
    print("DEBUG author:", request.forms.getunicode('author'), flush=True)
    required_fields = ["username", "author", "address", "contact1_name", "contact1_tel", "contact1_email",
                       "contact2_name", "contact2_tel", "contact2_email",
                       "contact3_name", "contact3_tel", "contact3_email",
                       "normal_hours", "normal_method", "after_hours", "after_method",
                       "after_contact1_name", "after_contact1_tel", "after_contact1_email",
                       "after_contact2_name", "after_contact2_tel", "after_contact2_email",
                       "after_contact3_name", "after_contact3_tel", "after_contact3_email"
                       ]
    for field in required_fields:
        if not request.forms.getunicode(field):
            return f"{field} が未入力です"
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute('''
            INSERT INTO contacts (
                username, author, address, contact1_name, contact1_tel, contact1_email,
                contact2_name, contact2_tel, contact2_email,
                contact3_name, contact3_tel, contact3_email,
                normal_hours, normal_method, after_hours, after_method,
                after_contact1_name, after_contact1_tel, after_contact1_email,
                after_contact2_name, after_contact2_tel, after_contact2_email,
                after_contact3_name, after_contact3_tel, after_contact3_email,
                timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (
                request.forms.getunicode('username'), request.forms.getunicode('author'), request.forms.getunicode('address'),
                request.forms.getunicode('contact1_name'), request.forms.getunicode('contact1_tel'), request.forms.getunicode('contact1_email'),
                request.forms.getunicode('contact2_name'), request.forms.getunicode('contact2_tel'), request.forms.getunicode('contact2_email'),
                request.forms.getunicode('contact3_name'), request.forms.getunicode('contact3_tel'), request.forms.getunicode('contact3_email'),
                request.forms.getunicode('normal_hours'), request.forms.getunicode('normal_method'),
                request.forms.getunicode('after_hours'), request.forms.getunicode('after_method'),
                request.forms.getunicode('after_contact1_name'), request.forms.getunicode('after_contact1_tel'), request.forms.getunicode('after_contact1_email'),
                request.forms.getunicode('after_contact2_name'), request.forms.getunicode('after_contact2_tel'), request.forms.getunicode('after_contact2_email'),
                request.forms.getunicode('after_contact3_name'), request.forms.getunicode('after_contact3_tel'), request.forms.getunicode('after_contact3_email'),
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ))
    redirect('/')

@bottle_app.get('/editform/<id:int>')
def edit_form(id):
    s = request.environ.get('beaker.session')
    if s.get('user') != 'admin':
        return "権限がありません"
    with sqlite3.connect(DB_FILE) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM contacts WHERE id = ?", (id,))
        row = cur.fetchone()
    if not row:
        return "データが見つかりません"
    csrf_token = s.get('csrf_token', '')
    content = f'''
        <label>ユーザー名 <input name="username" value="{row[1]}" required /></label>
        <label>構築担当者 <input name="author" value="{row[2]}" required /></label>
        <label>住所 <input name="address" value="{row[3]}" required /></label>
        <div style="display: flex; gap: 10px; align-items: center;">
          <label>第一連絡先名 <input name="contact1_name" value="{row[4]}" required /></label>
          <label>第一連絡先電話 <input name="contact1_tel" value="{row[5]}" required /></label>
          <label>第一連絡先Email <input name="contact1_email" value="{row[6]}" required /></label>
        </div>

        <div style="display: flex; gap: 10px; align-items: center;">
          <label>第二連絡先名 <input name="contact2_name" value="{row[7]}" required /></label>
          <label>第二連絡先電話 <input name="contact2_tel" value="{row[8]}" required /></label>
          <label>第二連絡先Email <input name="contact2_email" value="{row[9]}" required /></label>
        </div>

        <div style="display: flex; gap: 10px; align-items: center;">
          <label>第三連絡先名 <input name="contact3_name" value="{row[10]}" required /></label>
          <label>第三連絡先電話 <input name="contact3_tel" value="{row[11]}" required /></label>
          <label>第三連絡先Email <input name="contact3_email" value="{row[12]}" required /></label>
        </div>

        <label>通常受付時間 <input name="normal_hours" value="{row[13]}" required /></label>
        <label>連絡方法 <input name="normal_method" value="{row[14]}" required /></label>
        <label>時間外の連絡要否
            <select name="after_hours" required>
                <option value="要" {'selected' if row[15]=='要' else ''}>要</option>
                <option value="否" {'selected' if row[15]=='否' else ''}>否</option>
            </select>
        </label>
        <label>時間外連絡方法 <input name="after_method" value="{row[16]}" required /></label>
        <div style="display: flex; gap: 10px; align-items: center;">
          <label>時間外第一連絡先名 <input name="after_contact1_name" value="{row[19]}" required /></label>
          <label>時間外第一連絡先電話 <input name="after_contact1_tel" value="{row[20]}" required /></label>
          <label>時間外第一連絡先Email <input name="after_contact1_email" value="{row[21]}" required /></label>
        </div>
        <div style="display: flex; gap: 10px; align-items: center;">
          <label>時間外第二連絡先名 <input name="after_contact2_name" value="{row[22]}" required /></label>
          <label>時間外第二連絡先電話 <input name="after_contact2_tel" value="{row[23]}" required /></label>
          <label>時間外第二連絡先Email <input name="after_contact2_email" value="{row[24]}" required /></label>
        </div>
        <div style="display: flex; gap: 10px; align-items: center;">
          <label>時間外第三連絡先名 <input name="after_contact3_name" value="{row[25]}" required /></label>
          <label>時間外第三連絡先電話 <input name="after_contact3_tel" value="{row[26]}" required /></label>
          <label>時間外第三連絡先Email <input name="after_contact3_email" value="{row[27]}" required /></label>
        </div>
    '''
    return render_modal_form(content, csrf_token, f'/edit/{id}')

@bottle_app.post('/edit/<id:int>')
def update_entry(id):
    s = request.environ.get('beaker.session')
    if s.get('user') != 'admin':
        return "権限がありません"
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute('''
            UPDATE contacts SET
                username=?, author=?, address=?,
                contact1_name=?, contact1_tel=?, contact1_email=?,
                contact2_name=?, contact2_tel=?, contact2_email=?,
                contact3_name=?, contact3_tel=?, contact3_email=?,
                normal_hours=?, normal_method=?, after_hours=?, after_method=?,
                after_contact1_name=?, after_contact1_tel=?, after_contact1_email=?,
                after_contact2_name=?, after_contact2_tel=?, after_contact2_email=?,
                after_contact3_name=?, after_contact3_tel=?, after_contact3_email=?,
                timestamp=?
            WHERE id=?
        ''', (
            request.forms.getunicode('username'), request.forms.getunicode('author'), request.forms.getunicode('address'),
            request.forms.getunicode('contact1_name'), request.forms.getunicode('contact1_tel'), request.forms.getunicode('contact1_email'),
            request.forms.getunicode('contact2_name'), request.forms.getunicode('contact2_tel'), request.forms.getunicode('contact2_email'),
            request.forms.getunicode('contact3_name'), request.forms.getunicode('contact3_tel'), request.forms.getunicode('contact3_email'),
            request.forms.getunicode('normal_hours'), request.forms.getunicode('normal_method'),
            request.forms.getunicode('after_hours'), request.forms.getunicode('after_method'),
            request.forms.getunicode('after_contact1_name'), request.forms.getunicode('after_contact1_tel'), request.forms.getunicode('after_contact1_email'),
            request.forms.getunicode('after_contact2_name'), request.forms.getunicode('after_contact2_tel'), request.forms.getunicode('after_contact2_email'),
            request.forms.getunicode('after_contact3_name'), request.forms.getunicode('after_contact3_tel'), request.forms.getunicode('after_contact3_email'),
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'), id
        ))
    redirect('/')

@bottle_app.get('/delete/<id:int>')
def delete_entry(id):
    s = request.environ.get('beaker.session')
    if s.get('user') != 'admin':
        return "権限がありません"
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("DELETE FROM contacts WHERE id = ?", (id,))
    redirect('/')

@bottle_app.get('/')
def index():
    s = request.environ.get('beaker.session')
    user = s.get('user', '')
    token = str(uuid.uuid4())
    s['csrf_token'] = token
    s.save()
    query = request.query.q or ''
    with sqlite3.connect(DB_FILE) as conn:
        cur = conn.cursor()
        if query:
            cur.execute("SELECT id, username FROM contacts WHERE username LIKE ? ORDER BY id DESC", ('%' + query + '%',))
        else:
            cur.execute("SELECT id, username FROM contacts ORDER BY id DESC")
        userlist = cur.fetchall()
        query = request.query.q or ''
    return template('index', user=user, userlist=userlist, query=query)

def get_contact_detail(id):
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM contacts WHERE id = ?", (id,))
        row = cur.fetchone()

    if not row:
        response.status = 404
        return json.dumps({"text": "❌ データが見つかりません"}, ensure_ascii=False)

    # データを整形してMattermost向けメッセージ作成
    detail = f"""\
📄 **連絡先詳細**
- ユーザー名: {row["username"]}
- 運用担当者: {row["author"]}
- 住所: {row["address"]}
- 第一連絡先: {row["contact1_name"]} / {row["contact1_tel"]} / {row["contact1_email"]}
- 第二連絡先: {row["contact2_name"]} / {row["contact2_tel"]} / {row["contact2_email"]}
- 第三連絡先: {row["contact3_name"]} / {row["contact3_tel"]} / {row["contact3_email"]}
- 通常受付時間: {row["normal_hours"]}（連絡方法: {row["normal_method"]}）
- 時間外連絡: {row["after_hours"]}（連絡方法: {row["after_method"]}）
- 時間外第一連絡先: {row["after_contact1_name"]} / {row["after_contact1_tel"]} / {row["after_contact1_email"]}
- 時間外第二連絡先: {row["after_contact2_name"]} / {row["after_contact2_tel"]} / {row["after_contact2_email"]}
- 時間外第三連絡先: {row["after_contact3_name"]} / {row["after_contact3_tel"]} / {row["after_contact3_email"]}"""

    return json.dumps({"text": detail}, ensure_ascii=False)

@bottle_app.get('/api/detail/<id:int>')
def api_detail(id):
    response.content_type = 'application/json; charset=UTF-8'
    return get_contact_detail(id)

@bottle_app.get('/api/list')
def api_list():
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT id, username FROM contacts ORDER BY id DESC")
        rows = cur.fetchall()

    if not rows:
        response.status = 200
        return json.dumps({"text": "📭 ユーザーが登録されていません"}, ensure_ascii=False)

    # Mattermost表示用に整形
    lines = ["📋 **ユーザー一覧**"]
    for row in rows:
        lines.append(f"- ID: {row['id']}, ユーザー名: {row['username']}")

    message = "\n".join(lines)

    response.content_type = 'application/json; charset=UTF-8'
    return json.dumps({"text": message}, ensure_ascii=False)

@bottle_app.post('/api/search')
def api_search_use_detail():
    text = request.forms.getunicode('text', '')
    trigger = request.forms.getunicode('trigger_word', '')
    keyword = text[len(trigger):].strip()

    if not keyword:
        return json.dumps({"text": "❗検索キーワードが指定されていません"}, ensure_ascii=False)

    # usernameで部分一致検索し、最初のidを取得
    with sqlite3.connect(DB_FILE) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM contacts WHERE username LIKE ? COLLATE NOCASE ORDER BY id DESC", ('%' + keyword + '%',))
        row = cur.fetchone()

    if not row:
        return json.dumps({"text": f"🔍 「{keyword}」に一致するユーザーは見つかりませんでした"}, ensure_ascii=False)

    response.content_type = 'application/json; charset=UTF-8'
    return get_contact_detail(row[0])

@bottle_app.get('/admin/export')
def admin_export():
    s = request.environ.get('beaker.session')
    if s.get('user') != 'admin':
        response.status = 403
        return "権限がありません"
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM contacts")
        rows = cur.fetchall()
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=rows[0].keys())
    writer.writeheader()
    for r in rows:
        writer.writerow(dict(r))
    response.content_type = 'text/csv; charset=UTF-8'
    response.headers['Content-Disposition'] = 'attachment; filename="contacts_export.csv"'
    return output.getvalue()

@bottle_app.post('/admin/import')
def admin_import():
    s = request.environ.get('beaker.session')
    if s.get('user') != 'admin':
        response.status = 403
        return "権限がありません"
    upload = request.files.get('csv_file')
    if not upload:
        response.status = 400
        return "CSVファイルが必要です"
    data = upload.file.read().decode('utf-8').splitlines()
    reader = csv.DictReader(data)
    with sqlite3.connect(DB_FILE) as conn:
        # カラム確認
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(contacts)")
        columns = [info[1] for info in cur.fetchall()]
        has_remarks = 'remarks' in columns
        for row in reader:
            values = [
                row.get('username', ''),
                row.get('author', ''),
                row.get('address', ''),
                row.get('contact1_name', ''),
                row.get('contact1_tel', ''),
                row.get('contact1_email', ''),
                row.get('contact2_name', ''),
                row.get('contact2_tel', ''),
                row.get('contact2_email', ''),
                row.get('contact3_name', ''),
                row.get('contact3_tel', ''),
                row.get('contact3_email', ''),
                row.get('normal_hours', ''),
                row.get('normal_method', ''),
                row.get('after_hours', ''),
                row.get('after_method', ''),
                row.get('after_contact1_name', ''),
                row.get('after_contact1_tel', ''),
                row.get('after_contact1_email', ''),
                row.get('after_contact2_name', ''),
                row.get('after_contact2_tel', ''),
                row.get('after_contact2_email', ''),
                row.get('after_contact3_name', ''),
                row.get('after_contact3_tel', ''),
                row.get('after_contact3_email', ''),
            ]
            if has_remarks:
                values.append(row.get('remarks', ''))
                values.append(datetime.now().isoformat())
                conn.execute('''
                    INSERT INTO contacts (username, author, address, contact1_name, contact1_tel, contact1_email,
                        contact2_name, contact2_tel, contact2_email, contact3_name, contact3_tel, contact3_email,
                        normal_hours, normal_method, after_hours, after_method, remarks, timestamp,
                        after_contact1_name, after_contact1_tel, after_contact1_email,
                        after_contact2_name, after_contact2_tel, after_contact2_email,
                        after_contact3_name, after_contact3_tel, after_contact3_email)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', values)
            else:
                values.append(datetime.now().isoformat())
                conn.execute('''
                    INSERT INTO contacts (username, author, address, contact1_name, contact1_tel, contact1_email,
                        contact2_name, contact2_tel, contact2_email, contact3_name, contact3_tel, contact3_email,
                        normal_hours, normal_method, after_hours, after_method, timestamp,
                        after_contact1_name, after_contact1_tel, after_contact1_email,
                        after_contact2_name, after_contact2_tel, after_contact2_email,
                        after_contact3_name, after_contact3_tel, after_contact3_email)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', values)
    return "インポートが完了しました"

if __name__ == '__main__':
    init_db()
    run(app=app, host='0.0.0.0', port=8081, debug=True)

