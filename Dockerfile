FROM python:3.11-slim

# 必要なパッケージをインストール
RUN apt-get update && apt-get install -y \
    wget curl unzip \
    libnss3 libgconf-2-4 libxss1 libappindicator3-1 \
    fonts-liberation libasound2 \
    libgtk-3-0 libgbm-dev ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 最新のGoogle Chromeをインストール
RUN wget -q -O /tmp/google-chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && dpkg -i /tmp/google-chrome.deb || apt-get -f install -y \
    && rm /tmp/google-chrome.deb

# ChromeDriverのバージョンを手動で指定
ENV CHROMEDRIVER_VERSION=134.0.6998.88

RUN wget -q "https://storage.googleapis.com/chrome-for-testing-public/${CHROMEDRIVER_VERSION}/linux64/chromedriver-linux64.zip" \
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
