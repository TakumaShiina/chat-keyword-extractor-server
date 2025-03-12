FROM python:3.9

# 特定バージョンのChromeをインストール（安定版）
RUN apt-get update && apt-get install -y wget gnupg2 unzip apt-transport-https ca-certificates
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add -
RUN echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list
RUN apt-get update

# Chrome 120をインストール（特定バージョンを指定）
RUN apt-get install -y google-chrome-stable=120.0.6099.* || apt-get install -y google-chrome-stable

# 対応するChromeDriverをダウンロード（Chrome 120用）
RUN wget -O /tmp/chromedriver.zip "https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/120.0.6099.109/linux64/chromedriver-linux64.zip" \
    && unzip /tmp/chromedriver.zip -d /tmp/ \
    && mv /tmp/chromedriver-linux64/chromedriver /usr/local/bin/ \
    && rm -rf /tmp/chromedriver.zip /tmp/chromedriver-linux64 \
    && chmod +x /usr/local/bin/chromedriver

# アプリケーションをコピー
WORKDIR /app
COPY . /app

# 依存関係インストール
RUN pip install -r requirements.txt

# アプリケーション実行
CMD gunicorn app:app