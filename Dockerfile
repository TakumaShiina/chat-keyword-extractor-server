FROM python:3.9

# Chrome と ChromeDriver インストール
RUN apt-get update && apt-get install -y wget gnupg2 unzip
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add -
RUN echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list
RUN apt-get update && apt-get install -y google-chrome-stable

# ChromiumDriver（最新版）を使用する設定
RUN pip install webdriver-manager

# アプリケーションをコピー
WORKDIR /app
COPY . /app

# 依存関係インストール
RUN pip install -r requirements.txt

# アプリケーション実行
CMD gunicorn app:app