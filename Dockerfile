FROM python:3.11-slim

# 必要なパッケージをインストール
RUN apt-get update && apt-get install -y \
    wget curl unzip \
    libnss3 libgconf-2-4 libxss1 libappindicator3-1 \
    fonts-liberation libasound2 \
    libgtk-3-0 libgbm-dev ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Chromeのバージョンを固定（このバージョンは確実に存在することを確認済み）
ENV CHROME_VERSION=134.0.6998.88

# ChromeとChromeDriverのダウンロードURLを検証
RUN wget -q --spider "https://storage.googleapis.com/chrome-for-testing-public/${CHROME_VERSION}/linux64/chrome-linux64.zip" && \
    wget -q --spider "https://storage.googleapis.com/chrome-for-testing-public/${CHROME_VERSION}/linux64/chromedriver-linux64.zip"

# Google Chromeをインストール
RUN wget -q -O /tmp/chrome-linux64.zip "https://storage.googleapis.com/chrome-for-testing-public/${CHROME_VERSION}/linux64/chrome-linux64.zip" && \
    unzip /tmp/chrome-linux64.zip -d /opt/ && \
    ln -sf /opt/chrome-linux64/chrome /usr/bin/google-chrome && \
    rm /tmp/chrome-linux64.zip

# ChromeDriverをインストール - 各ステップを分離してエラーを特定しやすくする
RUN wget -q -O /tmp/chromedriver-linux64.zip "https://storage.googleapis.com/chrome-for-testing-public/${CHROME_VERSION}/linux64/chromedriver-linux64.zip" && \
    unzip /tmp/chromedriver-linux64.zip -d /tmp/ && \
    mv /tmp/chromedriver-linux64/chromedriver /usr/local/bin/ && \
    rm -rf /tmp/chromedriver-linux64.zip /tmp/chromedriver-linux64

# 実行権限を設定
RUN chmod +x /opt/chrome-linux64/chrome && \
    chmod +x /usr/local/bin/chromedriver

# Pythonパッケージをインストール
COPY requirements.txt /app/
WORKDIR /app
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションをコピー
COPY . /app

# エントリーポイント
# メモリ制限を設定
ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=UTF-8

# Gunicornで起動し、ワーカータイムアウトを増やす
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--timeout", "120", "--workers", "1", "--threads", "4", "app:app"]