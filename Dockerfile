FROM python:3.11-slim

# 必要なパッケージをインストール
RUN apt-get update && apt-get install -y \
    wget unzip curl \
    libnss3 libgconf-2-4 libxss1 libappindicator3-1 \
    fonts-liberation libasound2 \
    libgtk-3-0 libgbm-dev \
    && rm -rf /var/lib/apt/lists/*

# 最新のGoogle Chromeをインストール
RUN wget -q -O google-chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && apt-get install -y ./google-chrome.deb \
    && rm google-chrome.deb

# Chromeのバージョンを取得（正しいChromeDriverのバージョン取得に必要）
RUN CHROME_VERSION=$(google-chrome --version | awk '{print $3}') \
    && CHROMEDRIVER_VERSION=$(curl -s "https://googlechromelabs.github.io/chrome-for-testing/LATEST_RELEASE_${CHROME_VERSION%%.*}") \
    && wget -q "https://storage.googleapis.com/chrome-for-testing-public/${CHROMEDRIVER_VERSION}/linux64/chromedriver-linux64.zip" \
    && unzip chromedriver-linux64.zip -d /usr/local/bin/ \
    && rm chromedriver-linux64.zip

# Pythonパッケージをインストール
COPY requirements.txt /app/
WORKDIR /app
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションをコピー
COPY . /app

# エントリーポイント
CMD ["python", "app.py"]
