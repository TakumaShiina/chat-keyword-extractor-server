# app.py
from flask import Flask, request, jsonify, Response, render_template
from flask_cors import CORS
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import time
import uuid
import json
import threading
import os  # osモジュールを追加
from datetime import datetime
from queue import Queue, Empty
import logging

# ロギング設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, resources={
    r"/api/*": {
        "origins": ["http://localhost:3000", "file://", "null", "*"],
        "supports_credentials": True
    }
})

# セッション管理用の辞書
active_sessions = {}
session_queues = {}
stop_events = {}

def extract_messages_from_html(html):
    """HTMLからメッセージを抽出する関数"""
    soup = BeautifulSoup(html, 'html.parser')
    messages = []
    
    # ページタイトルとボディクラスをログに出力（デバッグ用）
    title = soup.title.text if soup.title else "No title"
    body_classes = soup.body.get('class', []) if soup.body else []
    logger.info(f"Page title: {title}")
    logger.info(f"Body classes: {body_classes}")
    
    # より広範なセレクターでメッセージ要素を検索
    message_elements = soup.select('.messages .message, .chat-messages .message, .stream-messages .message, .chat-list .message-item, .tip-comment, [class*="message-item"]')
    logger.info(f"Found {len(message_elements)} message elements with expanded selector")
    
    # HTMLセレクターのデバッグ情報
    all_messages_container = soup.select('.messages, .chat-messages, .stream-messages, .chat-list')
    logger.info(f"Any message container found: {len(all_messages_container) > 0}")
    
    # 最初のいくつかの要素の詳細をログに表示
    if message_elements:
        for i, elem in enumerate(message_elements[:3]):  # 最初の3つの要素
            logger.info(f"Message element {i} classes: {elem.get('class', [])}")
            logger.info(f"Message element {i} snippet: {str(elem)[:150]}...")
    
    # メッセージ要素から情報を抽出
    for element in message_elements:
        # 要素に一意の属性があればそれを使用し、なければUUIDを生成
        element_id = element.get('data-message-id')
        # IDがなかったり空だったりする場合は新しいIDを生成
        if not element_id:
            # 要素のハッシュ値を計算するか、一意の属性の組み合わせを使用
            element_text = str(element)[:100]  # 要素の一部をIDの生成に使用
            element_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, element_text))
        
        # チップ（投げ銭）メッセージの処理
        tip_comment_body = element.select_one('.tip-comment-body')
        coin_amount = element.select_one('.tip-amount-highlight')
        username = element.select_one('.user-levels-username-text')
        
        if tip_comment_body and coin_amount and username:
            comment_text = tip_comment_body.text.strip()
            coin_text = coin_amount.text.strip()
            username_text = username.text.strip()
            
            # メッセージタイプを判定
            message_type = 'メッセージ'
            if element.select_one('.tip-comment.tip-comment-with-highlight.tip-menu'):
                message_type = 'プレゼントメニュー'
            elif element.select_one('.tip-comment-epic-goal'):
                message_type = 'エピックゴール'
            
            formatted_text = f'[{message_type}] {coin_text}：{comment_text} 【{username_text}】'
            
            messages.append({
                'id': element_id,
                'text': formatted_text,
                'type': message_type,
                'checked': False,
                'timestamp': datetime.now().isoformat()
            })
        
        # ルーレット（Wheel of Fortune）メッセージの処理
        if ('plugin-message' in element.get('class', []) or 
            element.select_one('[class*="plugin-message"]')) and \
           (element.select_one('.plugin-message-plugin-name') or 
            element.select_one('[class*="plugin-name"]')):
            
            plugin_name_elem = element.select_one('.plugin-message-plugin-name') or element.select_one('[class*="plugin-name"]')
            if plugin_name_elem and 'Wheel of Fortune' in plugin_name_elem.text:
                prize_elem = element.select_one('.plugin-message-accent') or element.select_one('[class*="accent"]')
                prize_text = prize_elem.text.strip() if prize_elem else ''
                
                username_element = element.select_one('.user-levels-username-text') or element.select_one('[class*="username"]')
                username_text = username_element.text.strip() if username_element else ''
                
                if prize_text and username_text:
                    formatted_text = f'[ルーレット] ：{prize_text} 【{username_text}】'
                    messages.append({
                        'id': element_id,
                        'text': formatted_text,
                        'type': 'ルーレット',
                        'checked': False,
                        'timestamp': datetime.now().isoformat()
                    })
    
    logger.info(f"Extracted {len(messages)} messages")
    
    return messages

def analyze_dom_structure(html):
    """DOM構造を詳細に分析し、メッセージ要素のパターンを探す"""
    soup = BeautifulSoup(html, 'html.parser')
    
    # 可能性のあるメッセージコンテナを調査
    container_selectors = [
        '.messages', '.chat-messages', '.stream-messages', 
        '.chat-list', '.message-list', '.comment-list'
    ]
    
    for selector in container_selectors:
        containers = soup.select(selector)
        logger.info(f"Selector '{selector}': {len(containers)} elements found")
        
        if containers:
            # 最初のコンテナの子要素を分析
            container = containers[0]
            children = container.find_all(recursive=False)
            logger.info(f"Container '{selector}' has {len(children)} direct children")
            
            # 子要素のクラス名をチェック
            if children:
                class_patterns = {}
                for child in children:
                    classes = child.get('class', [])
                    class_str = ' '.join(classes)
                    class_patterns[class_str] = class_patterns.get(class_str, 0) + 1
                
                logger.info(f"Class patterns in '{selector}': {class_patterns}")


def analyze_dom_structure_enhanced(html):
    """HTML DOM構造をより詳細に分析し、メッセージ要素のパターンを探す拡張版関数"""
    soup = BeautifulSoup(html, 'html.parser')
    analysis_results = {
        'title': soup.title.text if soup.title else "No title",
        'potential_containers': [],
        'element_counts': {},
        'class_patterns': [],
        'potential_message_elements': []
    }
    
    # 様々な可能性のあるコンテナセレクターを試す
    container_selectors = [
        '.messages', '.chat-messages', '.stream-messages', 
        '.chat-list', '.message-list', '.comment-list',
        '[class*="messages"]', '[class*="chat"]', '[class*="comment"]',
        '.chat-container', '.chat-wrapper', '.stream-chat',
        '[class*="chatContainer"]', '[class*="chatWrapper"]', '[class*="streamChat"]',
        '.conversation', '.dialog', '.feed', '.timeline',
        '[class*="conversation"]', '[class*="dialog"]', '[class*="feed"]', '[class*="timeline"]'
    ]
    
    # 各セレクターに対して検索を実行
    for selector in container_selectors:
        containers = soup.select(selector)
        count = len(containers)
        analysis_results['element_counts'][selector] = count
        
        # コンテナが見つかった場合の詳細分析
        for idx, container in enumerate(containers[:3]):  # 最初の3つのみ詳細分析
            children_count = len(container.find_all(recursive=False))
            
            # コンテナ情報を追加
            container_info = {
                'selector': selector,
                'index': idx,
                'children_count': children_count,
                'class': container.get('class', []),
                'id': container.get('id', ''),
                'sample_html': str(container)[:200] + '...' if len(str(container)) > 200 else str(container)
            }
            
            # 子要素があれば最初の子要素を分析
            if children_count > 0:
                first_child = container.find(recursive=False)
                container_info['first_child_class'] = first_child.get('class', [])
                container_info['first_child_tag'] = first_child.name
                container_info['first_child_sample'] = str(first_child)[:150] + '...' if len(str(first_child)) > 150 else str(first_child)
            
            analysis_results['potential_containers'].append(container_info)
    
    # メッセージ要素と思われる要素をピックアップ
    message_indicators = [
        '.message', '.chat-message', '.comment', 
        '.tip-comment', '.user-message', '.system-message',
        '[class*="message"]', '[class*="comment"]', '[class*="chat-item"]'
    ]
    
    # メッセージ要素を検索
    for indicator in message_indicators:
        elements = soup.select(indicator)
        count = len(elements)
        analysis_results['element_counts'][indicator] = count
        
        # サンプルメッセージ要素を追加
        for idx, elem in enumerate(elements[:5]):  # 最初の5つのみサンプルとして
            elem_info = {
                'selector': indicator,
                'index': idx,
                'class': elem.get('class', []),
                'id': elem.get('id', ''),
                'text_sample': elem.text[:100].strip() if elem.text else 'No text',
                'html_sample': str(elem)[:200] + '...' if len(str(elem)) > 200 else str(elem)
            }
            analysis_results['potential_message_elements'].append(elem_info)
    
    # 全体的なクラスパターンを分析
    all_elements = soup.find_all(class_=True)
    class_counter = {}
    
    for elem in all_elements:
        classes = elem.get('class', [])
        class_str = ' '.join(classes)
        class_counter[class_str] = class_counter.get(class_str, 0) + 1
    
    # 最も頻出するクラスパターントップ20を抽出
    top_patterns = sorted(class_counter.items(), key=lambda x: x[1], reverse=True)[:20]
    analysis_results['class_patterns'] = [{'pattern': k, 'count': v} for k, v in top_patterns]
    
    # 重要なメタデータを抽出
    meta_tags = soup.find_all('meta')
    analysis_results['meta'] = [
        {'name': meta.get('name', meta.get('property', 'unknown')), 'content': meta.get('content', '')}
        for meta in meta_tags if meta.get('name') or meta.get('property')
    ]
    
    return analysis_results

    # 使用例
    # debug_analysis = analyze_dom_structure_enhanced(html)
    # logger.info(f"Enhanced DOM analysis: {json.dumps(debug_analysis)}")

def monitor_chat(url, session_id, message_queue, stop_event):
    """チャットを監視し、新しいメッセージをキューに追加するバックグラウンド処理"""
    logger.info(f"Starting monitoring for session {session_id} at {url}")
    
    # 過去に処理したメッセージIDを記録
    processed_ids = set()
    
    # ブラウザインスタンスとドライバーの参照
    driver = None
    last_refresh_time = time.time()
    refresh_interval = 30  # 30秒ごとに再接続（負荷軽減のため延長）
    periodic_check_interval = 5  # 5秒ごとに更新チェック（負荷軽減のため延長）

    try:
        # ブラウザの設定
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")  # 新しいヘッドレスモード
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")

        # 重要: レンダラーの問題を回避するための設定
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-infobars")
        chrome_options.add_argument("--mute-audio")
        chrome_options.add_argument("--disable-browser-side-navigation")
        chrome_options.add_argument("--disable-features=VizDisplayCompositor")
        chrome_options.add_argument("--disable-web-security")
        chrome_options.add_argument("--disable-features=IsolateOrigins,site-per-process")

        # メモリ使用量を最適化
        chrome_options.add_argument("--js-flags=--max-old-space-size=512")
        chrome_options.add_argument("--memory-pressure-off")

        # 安定性のための設定
        chrome_options.add_argument("--disable-setuid-sandbox")
        chrome_options.add_argument("--ignore-certificate-errors")
        chrome_options.add_argument("--disable-accelerated-2d-canvas")
        chrome_options.add_argument("--disable-accelerated-jpeg-decoding")
        chrome_options.add_argument("--disable-accelerated-mjpeg-decode")
        chrome_options.add_argument("--disable-accelerated-video-decode")
        chrome_options.add_argument("--disable-gpu-compositing")
        chrome_options.add_argument("--remote-debugging-port=9222")

        # UAを設定
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

        # ページロード戦略を設定
        chrome_options.page_load_strategy = 'eager'  # DOMContentLoadedイベント時に読み込み完了とみなす

        # 環境変数をチェック
        chrome_binary = os.environ.get('CHROME_BIN', '/usr/bin/google-chrome')
        logger.info(f"Using Chrome binary at: {chrome_binary}")

        # バイナリの場所を明示的に設定
        chrome_options.binary_location = chrome_binary

        # デバッグ情報をログに出力
        logger.info(f"Chrome options: {', '.join(chrome_options.arguments)}")

        # WebDriverの設定
        service = Service("/usr/local/bin/chromedriver")
        
        # ブラウザ起動前にデバッグログ
        logger.info(f"Starting Chrome with binary: {chrome_binary}")
        logger.info("Using ChromeDriver from: /usr/local/bin/chromedriver")
        
        # タイムアウトを長めに設定して起動
        driver = webdriver.Chrome(service=service, options=chrome_options)
        logger.info("ChromeDriver started successfully")
        
        # ブラウザバージョン情報を取得
        version = driver.capabilities.get('browserVersion', 'unknown')
        driver_version = driver.capabilities.get('chrome', {}).get('chromedriverVersion', 'unknown')
        logger.info(f"Chrome version: {version}, ChromeDriver version: {driver_version}")

        # URLにアクセス
        driver.get(url)
        logger.info(f"Browser accessed {url}")
        
        # 初期データを送信（接続確認用）
        initial_messages = [{
            'id': str(uuid.uuid4()),
            'text': f'[接続確認] モニタリングを開始しました 【System】',
            'type': 'システム',
            'checked': False,
            'timestamp': datetime.now().isoformat()
        }]
        message_queue.put(initial_messages)
        
        # 最初のロード待機
        time.sleep(3)  # 初期ロードも高速化
        
        # 前回の最終チェック時間
        last_check_time = time.time()
        
        # 監視ループ
        while not stop_event.is_set():
            try:
                current_time = time.time()
                
                # 定期的なチェックの時間になったか
                is_check_time = (current_time - last_check_time) >= periodic_check_interval
                
                # ブラウザのリフレッシュが必要か
                is_refresh_time = (current_time - last_refresh_time) >= refresh_interval
                
                # 定期的にブラウザセッションをリフレッシュ
                if is_refresh_time:
                    logger.info("Refreshing browser session")
                    driver.refresh()
                    
                    # ページロード後にJavaScriptを実行してコンテンツを表示
                    try:
                        driver.execute_script("""
                            // メッセージコンテナをスクロール
                            const messagesContainer = document.querySelector('.messages');
                            if (messagesContainer) {
                                messagesContainer.scrollTop = messagesContainer.scrollHeight;
                            }
                        """)
                    except Exception as js_err:
                        logger.error(f"Error executing scroll script: {str(js_err)}")
                        
                    time.sleep(2)  # ページロード待機時間
                    last_refresh_time = current_time
                    last_check_time = current_time  # チェックタイマーもリセット
                    is_check_time = True  # 強制的にチェック
                
                # 定期的なチェック時間かリフレッシュ時にメッセージを取得
                if is_check_time:
                    # ページのHTMLを取得
                    html = driver.page_source

                    # デバッグ用に一部のHTMLを保存
                    try:
                        debug_path = '/tmp/debug.html'
                        with open(debug_path, 'w', encoding='utf-8') as f:
                            f.write(html[:200000])  # 最初の20万文字を保存（十分な量）
                        logger.info(f"Saved debug HTML to {debug_path}")

                        # 重要なセレクターの出現回数をカウント
                        count_messages = html.count('class="messages"')
                        count_message = html.count('class="message"')
                        count_chat_messages = html.count('class="chat-messages"')
                        count_tip_comment = html.count('class="tip-comment"')
                        
                        logger.info(f"HTML stats - messages: {count_messages}, message: {count_message}, chat-messages: {count_chat_messages}, tip-comment: {count_tip_comment}")
                    except Exception as write_err:
                        logger.error(f"Failed to save debug HTML: {str(write_err)}")

                    # ページ全体の構造情報を取得
                    try:
                        structure_info = driver.execute_script("""
                            const allNodes = document.querySelectorAll('div, section, aside');
                            const classes = {};
                            for (let i = 0; i < allNodes.length; i++) {
                                if (allNodes[i].className) {
                                    const cls = allNodes[i].className.toString();
                                    classes[cls] = (classes[cls] || 0) + 1;
                                }
                            }
                            
                            // メッセージ関連の要素を特に探す
                            const messageContainers = document.querySelectorAll(
                                '.messages, .chat-messages, .stream-messages, .chat-list, .message-list, ' + 
                                '.comment-list, [class*="message"], [class*="chat"], [class*="comment"]'
                            );
                            
                            const potentialContainers = [];
                            for (let i = 0; i < messageContainers.length; i++) {
                                potentialContainers.push({
                                    className: messageContainers[i].className,
                                    childCount: messageContainers[i].children.length,
                                    html: messageContainers[i].children.length > 0 ? 
                                        messageContainers[i].children[0].outerHTML.substring(0, 150) : 'No children'
                                });
                            }
                            
                            return {
                                title: document.title,
                                url: window.location.href,
                                bodyClass: document.body.className,
                                topClasses: Object.entries(classes)
                                    .sort((a, b) => b[1] - a[1])
                                    .slice(0, 20),  // 出現頻度の高い上位20クラス
                                potentialMessageContainers: potentialContainers
                            }
                        """)
                        logger.info(f"Page structure: {json.dumps(structure_info)}")
                    except Exception as js_err:
                        logger.error(f"Failed to analyze page structure: {str(js_err)}")

                    # スクリーンショットを撮影（HTMLだけでは分からない要素の位置関係を確認）
                    try:
                        screenshot_path = '/tmp/debug_screenshot.png'
                        driver.save_screenshot(screenshot_path)
                        logger.info(f"Saved screenshot to {screenshot_path}")
                    except Exception as ss_err:
                        logger.error(f"Failed to take screenshot: {str(ss_err)}")

                    # 拡張DOM分析を実行
                    try:
                        debug_analysis = analyze_dom_structure_enhanced(html)
                        logger.info(f"Enhanced DOM analysis: {json.dumps(debug_analysis)}")
                    except Exception as analysis_err:
                        logger.error(f"Failed to perform enhanced DOM analysis: {str(analysis_err)}")
                        
                    # メッセージを抽出
                    all_messages = extract_messages_from_html(html)
                    
                    # 新しいメッセージのみをフィルタリング
                    new_messages = []
                    for msg in all_messages:
                        msg_id = msg['id']
                        if msg_id not in processed_ids:
                            new_messages.append(msg)
                            processed_ids.add(msg_id)
                    
                    if new_messages:
                        logger.info(f"Found {len(new_messages)} new messages")
                        # 新しいメッセージをキューに追加
                        message_queue.put(new_messages)
                    else:
                        # メッセージがなければログ
                        logger.info("No new messages found")
                        
                        # Seleniumを使用して直接DOMをチェック
                        try:
                            # JavaScriptを実行してメッセージ要素を検出
                            message_count = driver.execute_script("""
                                const messages = document.querySelectorAll('.messages .message, .chat-messages .message, .stream-messages .message, [class*="message-item"]');
                                return messages.length;
                            """)
                            logger.info(f"JavaScript detected {message_count} message elements")
                            
                        except Exception as js_err:
                            logger.error(f"JavaScript execution error: {str(js_err)}")
                    
                    # チェック時間を更新
                    last_check_time = current_time
                
                # 短い待機で監視ループを継続
                time.sleep(0.5)
                
            except Exception as loop_err:
                logger.error(f"Error in monitoring loop: {str(loop_err)}")
                # エラーが発生しても継続
                time.sleep(1)
        
        # 監視終了時にブラウザを閉じる
        driver.quit()
        logger.info(f"Monitoring stopped for session {session_id}")
        
    except Exception as e:
        logger.error(f"Error in monitoring thread: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        # エラー情報をキューに送信
        message_queue.put({"error": str(e)})
        # エラーが発生したらブラウザを閉じる
        try:
            if driver:
                driver.quit()
        except:
            pass

@app.route('/api/start-monitoring', methods=['POST'])
def start_monitoring():
    """モニタリングセッションを開始するエンドポイント"""
    data = request.json
    url = data.get('url')
    
    if not url:
        return jsonify({"error": "URLが必要です"}), 400
    
    # 新しいセッションIDを生成
    session_id = str(uuid.uuid4())
    
    # セッション用のメッセージキューとストップイベントを作成
    message_queue = Queue()
    stop_event = threading.Event()
    
    # セッション情報を保存
    session_queues[session_id] = message_queue
    stop_events[session_id] = stop_event
    
    # モニタリングスレッドを開始
    monitoring_thread = threading.Thread(
        target=monitor_chat,
        args=(url, session_id, message_queue, stop_event)
    )
    monitoring_thread.daemon = True
    monitoring_thread.start()
    
    active_sessions[session_id] = {
        'thread': monitoring_thread,
        'url': url,
        'started_at': datetime.now().isoformat()
    }
    
    return jsonify({
        "session_id": session_id,
        "message": "モニタリングを開始しました",
        "stream_url": f"/api/stream/{session_id}"
    })

@app.route('/api/stop-monitoring/<session_id>', methods=['POST'])
def stop_monitoring(session_id):
    """モニタリングセッションを停止するエンドポイント"""
    if session_id not in active_sessions:
        return jsonify({"error": "セッションが見つかりません"}), 404
    
    # ストップイベントをセット
    stop_events[session_id].set()
    
    # セッション情報をクリーンアップ
    del active_sessions[session_id]
    del session_queues[session_id]
    del stop_events[session_id]
    
    return jsonify({"message": "モニタリングを停止しました"})

@app.route('/api/stream/<session_id>')
def stream(session_id):
    """Server-Sent Events (SSE) ストリームを提供するエンドポイント"""
    if session_id not in active_sessions:
        return jsonify({"error": "セッションが見つかりません"}), 404
    
    def generate():
        try:
            # 接続時にまず初期メッセージを送信
            yield f"data: {json.dumps({'type': 'connected', 'session_id': session_id})}\n\n"
            
            message_queue = session_queues[session_id]
            stop_event = stop_events[session_id]
            
            # 最後にメッセージを送信した時間を記録
            last_message_time = time.time()
            last_sample_time = time.time()  # サンプルメッセージ用の別タイマー（使用しない）
            keepalive_interval = 5  # 5秒ごとにキープアライブを送信
            
            # キューからメッセージを読み取り、クライアントに送信
            while not stop_event.is_set():
                try:
                    # タイムアウト付きでキューからメッセージを取得（短めのタイムアウト）
                    messages = message_queue.get(timeout=1)  # 1秒のタイムアウト
                    
                    # エラーメッセージの場合
                    if isinstance(messages, dict) and "error" in messages:
                        yield f"data: {json.dumps({'type': 'error', 'error': messages['error']})}\n\n"
                        break
                    
                    # メッセージを送信
                    yield f"data: {json.dumps({'type': 'messages', 'messages': messages})}\n\n"
                    last_message_time = time.time()
                    last_sample_time = time.time()  # 更新（使用しない変数だが念のため）
                    
                except Empty:
                    # キューが空（タイムアウト）の場合
                    current_time = time.time()
                    
                    # 一定時間経過していたらキープアライブを送信
                    if current_time - last_message_time > keepalive_interval:
                        logger.info("Sending keepalive to client")
                        yield f"data: {json.dumps({'type': 'keepalive'})}\n\n"
                        last_message_time = current_time
                                            
                except Exception as e:
                    # その他のエラー
                    logger.error(f"Error in stream generation: {str(e)}")
                    if stop_event.is_set():
                        break
                    time.sleep(0.5)  # エラー時の待機時間
                
                # ループごとに少し待機
                time.sleep(0.1)
            
            # 接続終了時のメッセージ
            yield f"data: {json.dumps({'type': 'disconnected'})}\n\n"
            
        except GeneratorExit:
            # クライアントが接続を閉じた場合
            logger.info(f"Client disconnected from session {session_id}")
            if session_id in active_sessions:
                stop_events[session_id].set()
    
    response = Response(generate(), mimetype='text/event-stream')
    # CORS関連のヘッダーを追加
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Accel-Buffering'] = 'no'  # Nginxのバッファリングを無効化
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response

@app.route('/dashboard')
def dashboard():
    """ダッシュボードページを提供するエンドポイント"""
    return render_template('dashboard.html')

@app.route('/monitor.js')
def test_js():
    """テスト用JavaScriptファイルを提供するエンドポイント"""
    try:
        with open('monitor.js', 'r', encoding='utf-8') as file:
            return Response(file.read(), mimetype='application/javascript')
    except Exception as e:
        logger.error(f"Error reading test JavaScript: {str(e)}")
        return "console.error('Error loading JavaScript file');"

if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=5000, threaded=True)