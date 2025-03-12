FROM python:3.11-slim

# 必要なパッケージをインストール
RUN apt-get update && apt-get install -y \
    wget curl unzip \
    libnss3 libgconf-2-4 libxss1 libappindicator3-1 \
    fonts-liberation libasound2 \
    libgtk-3-0 libgbm-dev ca-certificates \
    libatk1.0-0 libatk-bridge2.0-0 libcups2 libxcomposite1 \
    libxdamage1 libxfixes3 libxrandr2 libxkbcommon0 libpango-1.0-0 \
    libcairo2 libasound2 libnspr4 libnss3 libx11-xcb1 \
    && rm -rf /var/lib/apt/lists/*

# より安定していることが知られているChromeバージョンを使用
ENV CHROME_VERSION=114.0.5735.90

# ChromeとChromeDriverのダウンロードURLを検証
RUN wget -q --spider "https://storage.googleapis.com/chrome-for-testing-public/${CHROME_VERSION}/linux64/chrome-linux64.zip" && \
    wget -q --spider "https://storage.googleapis.com/chrome-for-testing-public/${CHROME_VERSION}/linux64/chromedriver-linux64.zip"

# Google Chromeをインストール
RUN wget -q -O /tmp/chrome-linux64.zip "https://storage.googleapis.com/chrome-for-testing-public/${CHROME_VERSION}/linux64/chrome-linux64.zip" && \
    unzip /tmp/chrome-linux64.zip -d /opt/ && \
    ln -sf /opt/chrome-linux64/chrome /usr/bin/google-chrome && \
    rm /tmp/chrome-linux64.zip

# ChromeDriverをインストール
RUN wget -q -O /tmp/chromedriver-linux64.zip "https://storage.googleapis.com/chrome-for-testing-public/${CHROME_VERSION}/linux64/chromedriver-linux64.zip" && \
    unzip /tmp/chromedriver-linux64.zip -d /tmp/ && \
    mv /tmp/chromedriver-linux64/chromedriver /usr/local/bin/ && \
    rm -rf /tmp/chromedriver-linux64.zip /tmp/chromedriver-linux64

# Chromeのバージョンを確認
RUN google-chrome --version || echo "Chrome not installed correctly"
RUN ls -la /usr/bin/google-chrome || echo "Chrome symlink not created"
RUN ls -la /opt/chrome-linux64/chrome || echo "Chrome binary not found"

# 実行権限を設定
RUN chmod +x /opt/chrome-linux64/chrome && \
    chmod +x /usr/local/bin/chromedriver

# ChromeDriverのバージョンを確認
RUN /usr/local/bin/chromedriver --version || echo "ChromeDriver not installed correctly"

# 共有メモリのためのディレクトリを作成
RUN mkdir -p /dev/shm

# Pythonパッケージをインストール
COPY requirements.txt /app/
WORKDIR /app
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションをコピー
COPY . /app

# メモリ制限を設定
ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=UTF-8

# コンテナ内のChrome設定
ENV CHROME_BIN=/usr/bin/google-chrome
ENV CHROME_PATH=/usr/bin/google-chrome

# エントリーポイント
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--timeout", "300", "--workers", "1", "--threads", "4", "app:app"]