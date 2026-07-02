# 運用連絡体制ツール

顧客ごとの運用連絡先、受付時間、時間外連絡先を保存し、Web画面やAPIから参照するためのツールです。

## 主な機能

- 顧客別の連絡体制管理
- 通常連絡先と時間外連絡先の分離
- 営業日と通常受付時間の管理
- 顧客名、担当者、住所、電話番号、メールアドレスなどを対象にした検索
- CSVインポート/エクスポート
- Mattermost Slash Command向けAPI
- Docker Composeによるデプロイ

## 動作要件

- Docker または Podman
- Docker Composeを使う場合は `docker-compose-plugin`

Pythonで直接起動する場合:

- Python 3.9以降
- bottle
- beaker
- gunicorn

## Docker Composeでの起動

1. リポジトリを取得します。

   ```bash
   git clone https://github.com/pench999/contact_flow.git
   cd contact_flow
   ```

2. `.env` を作成します。

   ```bash
   cp .env.example .env
   ```

3. `.env` の `ADMIN_PASSWORD` を変更します。

   ```env
   ADMIN_PASSWORD=change-this-password
   PORT=8080
   ```

4. 起動します。

   ```bash
   docker compose up -d --build
   ```

5. ブラウザでアクセスします。

   ```text
   http://localhost:8080
   ```

停止する場合:

```bash
docker compose down
```

## Podmanでの起動

```bash
mkdir -p ./data ./session_data
podman build -t contact-flow .
podman run -d --name contact-flow \
  -p 8080:8080 \
  -v ./data:/app/data \
  -v ./session_data:/app/session_data \
  -e ADMIN_PASSWORD='任意のパスワード' \
  contact-flow
```

## 環境変数

| 変数名 | 既定値 | 説明 |
| --- | --- | --- |
| `ADMIN_PASSWORD` | なし | adminログイン用パスワード |
| `PORT` | `8080` | アプリケーション待受ポート |
| `CONTACT_FLOW_DB_FILE` | `/app/data/contact_chart.db` | SQLite DBファイル |
| `SESSION_DATA_DIR` | `/app/session_data` | セッション保存先 |
| `WEB_CONCURRENCY` | `2` | gunicorn worker数 |

## ログイン

初期ユーザーは以下です。

```text
ユーザー名: admin
パスワード: .env の ADMIN_PASSWORD
```

## データベース

SQLiteを使用します。Docker Composeでは `./data:/app/data` をマウントするため、コンテナを作り直してもデータは保持されます。

主なテーブル:

- `customers`: 顧客単位の基本情報、営業日、受付時間、確認状態、情報オーナー
- `contact_points`: 顧客に紐づく通常/時間外連絡先

旧版の `contacts` テーブルが存在し、新しい `customers` が空の場合は、起動時に新テーブルへ自動移行します。

## API

### 一覧取得

```bash
curl http://localhost:8080/api/list
```

### 詳細取得

```bash
curl http://localhost:8080/api/detail/1
```

### 検索

```bash
curl "http://localhost:8080/api/search?q=顧客名"
```

検索対象には、顧客名、構築担当者、住所、営業日、受付時間、電話番号、メールアドレス、確認状態などが含まれます。

### Mattermost Slash Command向け検索

```bash
curl -X POST http://localhost:8080/api/search \
  -d "text=顧客名" \
  -d "trigger_word=/contact"
```

1件だけ一致した場合は詳細を返します。複数件一致した場合は候補一覧を返します。

ID指定もできます。

```bash
curl -X POST http://localhost:8080/api/search \
  -d "text=1" \
  -d "trigger_word=/contact"
```

## 注意事項

- 現時点では参照APIに認証はありません。
- 社内LANやリバースプロキシ側でアクセス制限することを推奨します。
- 本番運用では `.env` の `ADMIN_PASSWORD` を必ず変更してください。
