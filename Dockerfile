FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先に requirements.txt をコピーしてインストール
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# DB用ディレクトリの作成
RUN mkdir -p /app/data

# アプリ本体をコピー
COPY . /app

CMD ["python", "app.py"]
