# 運用連絡体制ツール
アラートエスカレーション先のリストを保存し、参照するためのツール
## 動作要件
    - python 3.9以降
    - bottle,beaker 使う

## インストール
1. git cloneする
2. ボリューム用ディレクトリを作成する  
   `# mkdir -p ./data`
4. コンテナをビルドする  
   `# podman build --no-cache -t my-bottle-app .`
5. コンテナ起動する  
   `# podman run -d -p 8080:8080 -v ./data:/app/data -e ADMIN_PASSWORD='任意のパスワード' my-bottle-app`
6. URLアクセスする  
   `http://ホストIP:8080`

## データベース
SQLiteを使用し、既定では `/app/data/contact_chart.db` にデータを保存します。
コンテナ起動時に `./data:/app/data` をマウントすることで、コンテナを作り直してもデータを保持できます。

DBファイルの場所を変更したい場合は、環境変数 `CONTACT_FLOW_DB_FILE` を指定します。

内部テーブルは以下の構成です。

- `customers`: 顧客単位の基本情報、受付時間、確認状態、情報オーナーを保存
- `contact_points`: 顧客に紐づく連絡先を優先順位付きで保存

旧版の `contacts` テーブルが存在し、新しい `customers` が空の場合は、起動時に新テーブルへ自動移行します。

例:
`# podman run -d -p 8080:8080 -v ./data:/app/data -e CONTACT_FLOW_DB_FILE=/app/data/contact_chart.db -e ADMIN_PASSWORD='任意のパスワード' my-bottle-app`

## Ubuntu 24.04 / WSLでの起動例
DockerまたはPodmanを使って起動します。

### Docker Composeを使う場合
1. パッケージをインストールする  
   `sudo apt update && sudo apt install -y docker.io docker-compose-plugin`
2. `.env` を作成する  
   `cp .env.example .env`
3. `.env` の `ADMIN_PASSWORD` を変更する
4. 起動する  
   `sudo docker compose up -d --build`
5. URLアクセスする  
   `http://localhost:8080`

停止する場合:
`sudo docker compose down`

### Podmanを使う場合
1. パッケージをインストールする  
   `sudo apt update && sudo apt install -y podman`
2. 起動する  
   `podman build -t contact-flow .`
   `podman run -d --name contact-flow -p 8080:8080 -v ./data:/app/data -v ./session_data:/app/session_data -e ADMIN_PASSWORD='任意のパスワード' contact-flow`
