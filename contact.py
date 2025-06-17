from bottle import Bottle, template, request, redirect, run, response, SimpleTemplate
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
                    timestamp TEXT
                )
            ''')

def render_modal_form(content, csrf_token, action_url):
    tmpl = SimpleTemplate('''
        <div id="modal" style="display:block; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.7); font-family:Arial, sans-serif;" onclick="if(event.target.id==='modal'){ window.location.href='/'; }">
          <div style="background:#f9f9f9; border-radius:8px; box-shadow:0 0 20px rgba(0,0,0,0.2); margin:5% auto; padding:30px; width:40%; position:relative;" onclick="event.stopPropagation();">
            <h2 style="margin-bottom:20px; text-align:center; color:#333;">連絡体制入力</h2>
            <form method="post" action="{{action_url}}" style="display:flex; flex-direction:column; gap:10px;">
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
            <p>通常受付時間外: {{row[15]}}</p>
            <p>通常受付時間外連絡方法: {{row[16]}}</p>
            <p>登録日時: {{row[17]}}</p>
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
        <label>第一連絡先名 <input name="contact1_name" required /></label>
        <label>第一連絡先電話 <input name="contact1_tel" required /></label>
        <label>第一連絡先Email <input name="contact1_email" required /></label>
        <label>第二連絡先名 <input name="contact2_name" required /></label>
        <label>第二連絡先電話 <input name="contact2_tel" required /></label>
        <label>第二連絡先Email <input name="contact2_email" required /></label>
        <label>第三連絡先名 <input name="contact3_name" required /></label>
        <label>第三連絡先電話 <input name="contact3_tel" required /></label>
        <label>第三連絡先Email <input name="contact3_email" required /></label>
        <label>通常受付時間 <input name="normal_hours" required /></label>
        <label>連絡方法 <input name="normal_method" required /></label>
        <label>受付時間外の連絡要否 
            <select name="after_hours" required>
                <option value="要">要</option>
                <option value="否">否</option>
            </select>
        </label>
        <label>受付時間外連絡方法 <input name="after_method" required /></label>
    '''
    return render_modal_form(content, csrf_token, '/form')

@bottle_app.post('/form')
def save_form():
    s = request.environ.get('beaker.session')
    if s.get('user') != 'admin' or request.forms.getunicode('csrf_token') != s.get('csrf_token'):
        return "不正なアクセス"
    required_fields = ["username", "author", "address", "contact1_name", "contact1_tel", "contact1_email",
                       "contact2_name", "contact2_tel", "contact2_email",
                       "contact3_name", "contact3_tel", "contact3_email",
                       "normal_hours", "normal_method", "after_hours", "after_method"]
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
                timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (
                request.forms.getunicode('username'), request.forms.getunicode('author'), request.forms.getunicode('address'),
                request.forms.getunicode('contact1_name'), request.forms.getunicode('contact1_tel'), request.forms.getunicode('contact1_email'),
                request.forms.getunicode('contact2_name'), request.forms.getunicode('contact2_tel'), request.forms.getunicode('contact2_email'),
                request.forms.getunicode('contact3_name'), request.forms.getunicode('contact3_tel'), request.forms.getunicode('contact3_email'),
                request.forms.getunicode('normal_hours'), request.forms.getunicode('normal_method'),
                request.forms.getunicode('after_hours'), request.forms.getunicode('after_method'),
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
        <label>第一連絡先名 <input name="contact1_name" value="{row[4]}" required /></label>
        <label>第一連絡先電話 <input name="contact1_tel" value="{row[5]}" required /></label>
        <label>第一連絡先Email <input name="contact1_email" value="{row[6]}" required /></label>
        <label>第二連絡先名 <input name="contact2_name" value="{row[7]}" required /></label>
        <label>第二連絡先電話 <input name="contact2_tel" value="{row[8]}" required /></label>
        <label>第二連絡先Email <input name="contact2_email" value="{row[9]}" required /></label>
        <label>第三連絡先名 <input name="contact3_name" value="{row[10]}" required /></label>
        <label>第三連絡先電話 <input name="contact3_tel" value="{row[11]}" required /></label>
        <label>第三連絡先Email <input name="contact3_email" value="{row[12]}" required /></label>
        <label>通常受付時間 <input name="normal_hours" value="{row[13]}" required /></label>
        <label>連絡方法 <input name="normal_method" value="{row[14]}" required /></label>
        <label>受付時間外の連絡要否 
            <select name="after_hours" required>
                <option value="要" {'selected' if row[15]=='要' else ''}>要</option>
                <option value="否" {'selected' if row[15]=='否' else ''}>否</option>
            </select>
        </label>
        <label>受付時間外連絡方法 <input name="after_method" value="{row[16]}" required /></label>
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
                timestamp=?
            WHERE id=?
        ''', (
            request.forms.getunicode('username'), request.forms.getunicode('author'), request.forms.getunicode('address'),
            request.forms.getunicode('contact1_name'), request.forms.getunicode('contact1_tel'), request.forms.getunicode('contact1_email'),
            request.forms.getunicode('contact2_name'), request.forms.getunicode('contact2_tel'), request.forms.getunicode('contact2_email'),
            request.forms.getunicode('contact3_name'), request.forms.getunicode('contact3_tel'), request.forms.getunicode('contact3_email'),
            request.forms.getunicode('normal_hours'), request.forms.getunicode('normal_method'),
            request.forms.getunicode('after_hours'), request.forms.getunicode('after_method'),
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
    return template('''
        <!DOCTYPE html>
        <html>
        <head>
            <title>顧客別連絡体制図</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
            <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
        </head>
        <body class="bg-light">
            <div class="container py-4">
                <div class="d-flex justify-content-between align-items-center mb-3">
                    <h1 class="h3">顧客別連絡体制図</h1>
                    <div>
                        % if not user:
                            <form method="post" action="/login" class="d-flex gap-2">
                                <input name="username" class="form-control form-control-sm" placeholder="ユーザー名" />
                                <input name="password" type="password" class="form-control form-control-sm" placeholder="パスワード" />
                                <input type="submit" class="btn btn-sm btn-primary" value="ログイン" />
                            </form>
                        % else:
                            <span>{{user}}</span> <a href="/logout" class="btn btn-sm btn-secondary">ログアウト</a>
                            % if user == 'admin':
                                <a href="#" onclick="showModalForm(); return false;" class="btn btn-sm btn-success">＋ 新規登録</a>
                            % end
                        % end
                    </div>
                </div>
                <div class="row">
                    <div class="col-md-4">
                        <form method="get" action="/" class="input-group mb-3">
                            <input type="text" name="q" class="form-control" placeholder="名前で検索" value="{{query or ''}}">
                            <button class="btn btn-outline-secondary" type="submit">検索</button>
                        </form>
                        <ul class="list-group">
                            % for id, name in userlist:
                                <li class="list-group-item"><a href="#" onclick="showDetails({{id}}); return false;">{{name}}</a></li>
                            % end
                        </ul>
                    </div>
                    <div class="col-md-8" id="details">
                        <h4>ユーザーを選択してください</h4>
                    </div>
                </div>
            </div>
            <div class="modal fade" id="modal" tabindex="-1" aria-hidden="true">
              <div class="modal-dialog">
                <div class="modal-content" id="modal-content">
                </div>
              </div>
            </div>
            <script>
                async function showDetails(id) {
                    const res = await fetch(`/detail/${id}`);
                    const html = await res.text();
                    document.getElementById('details').innerHTML = html;
                }
                function showModalForm(id=null) {
                    const modal = new bootstrap.Modal(document.getElementById('modal'));
                    if (id) {
                        fetch('/editform/' + id).then(res => res.text()).then(html => {
                            document.getElementById('modal-content').innerHTML = html;
                            modal.show();
                        });
                    } else {
                        fetch('/form').then(res => res.text()).then(html => {
                            document.getElementById('modal-content').innerHTML = html;
                            modal.show();
                        });
                    }
                }
            </script>
        </body>
        </html>
    ''', user=user, userlist=userlist, query=query)

@bottle_app.get('/api/detail/<id:int>')
def api_detail(id):
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM contacts WHERE id = ?", (id,))
        row = cur.fetchone()
    if not row:
        response.status = 404
        return json.dumps({"error": "データが見つかりません"}, ensure_ascii=False)
    response.content_type = 'application/json; charset=UTF-8'
    return json.dumps(dict(row), ensure_ascii=False)

@bottle_app.get('/api/list')
def api_list():
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT id, username FROM contacts ORDER BY id DESC")
        rows = cur.fetchall()
    response.content_type = 'application/json; charset=UTF-8'
    return json.dumps({"contacts": [dict(r) for r in rows]}, ensure_ascii=False)

@bottle_app.get('/api/search')
def api_search():
    keyword = request.query.get('q', '')
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM contacts WHERE username LIKE ? COLLATE NOCASE ORDER BY id DESC", ('%' + keyword + '%',))
        rows = cur.fetchall()
    response.content_type = 'application/json; charset=UTF-8'
    return json.dumps({"results": [dict(r) for r in rows]}, ensure_ascii=False)

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
            ]
            if has_remarks:
                values.append(row.get('remarks', ''))
                values.append(datetime.now().isoformat())
                conn.execute('''
                    INSERT INTO contacts (username, author, address, contact1_name, contact1_tel, contact1_email,
                        contact2_name, contact2_tel, contact2_email, contact3_name, contact3_tel, contact3_email,
                        normal_hours, normal_method, after_hours, after_method, remarks, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', values)
            else:
                values.append(datetime.now().isoformat())
                conn.execute('''
                    INSERT INTO contacts (username, author, address, contact1_name, contact1_tel, contact1_email,
                        contact2_name, contact2_tel, contact2_email, contact3_name, contact3_tel, contact3_email,
                        normal_hours, normal_method, after_hours, after_method, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', values)
    return "インポートが完了しました"


if __name__ == '__main__':
    init_db()
    run(app=app, host='0.0.0.0', port=8080, debug=True)
