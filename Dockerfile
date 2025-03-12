FROM python:3.11-slim

# 必要なパッケージをインストール
RUN apt-get update && apt-get install -y \
    wget curl unzip \
    libnss3 libgconf-2-4 libxss1 libappindicator3-1 \
    fonts-liberation libasound2 \
    libgtk-3-0 libgbm-dev ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# ChromeとChromeDriverのバージョンを固定
ENV CHROME_VERSION=114.0.5735.90

# 指定されたURLから最新のGoogle Chromeをインストール
RUN wget -q -O /tmp/chrome-linux64.zip "https://storage.googleapis.com/chrome-for-testing-public/${CHROME_VERSION}/linux64/chrome-linux64.zip" \
    && unzip /tmp/chrome-linux64.zip -d /opt/ \
    && ln -s /opt/chrome-linux64/chrome /usr/bin/google-chrome \
    && rm /tmp/chrome-linux64.zip

# ChromeDriverをインストール
RUN wget -q "https://storage.googleapis.com/chrome-for-testing-public/${CHROME_VERSION}/linux64/chromedriver-linux64.zip" \
    && unzip chromedriver-linux64.zip -d /usr/local/bin/ \
    && mv /usr/local/bin/chromedriver-linux64/chromedriver /usr/local/bin/ \
    && rm -rf chromedriver-linux64.zip /usr/local/bin/chromedriver-linux64

# Pythonパッケージをインストール
COPY requirements.txt /app/
WORKDIR /app
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションをコピー
COPY . /app

# Chromeの実行権限を確認
RUN chmod +x /opt/chrome-linux64/chrome

# エントリーポイント
CMD ["python", "app.py", "--host=0.0.0.0"]