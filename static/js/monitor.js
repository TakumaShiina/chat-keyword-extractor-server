// 状態を管理する変数
let isMonitoring = false;
let sessionId = null;
let eventSource = null;
let messages = [];
let hideMessages = false;
let hideEpicGoals = false;
let hideExcludedWords = false;
let excludeWords = Array(20).fill('');  // 20個の空の除外ワード
let sortMode = 'time';
let groupLimits = {}; // グループごとの個別上限設定

// DOMエレメントの参照
const urlInput = document.getElementById('urlInput');
const toggleButton = document.getElementById('toggleButton');
const errorElement = document.getElementById('error');
const statusIndicator = document.getElementById('statusIndicator');
const checkboxList = document.getElementById('checkboxList');
const hideMessagesCheckbox = document.getElementById('hideMessages');
const hideEpicGoalsCheckbox = document.getElementById('hideEpicGoals');
const hideExcludedWordsCheckbox = document.getElementById('hideExcludedWords');
const sortModeSelect = document.getElementById('sortMode');
const removeCheckedButton = document.getElementById('removeChecked');
const resetButton = document.getElementById('reset');
const showExcludeWordsButton = document.getElementById('showExcludeWords');
const excludeWordsModal = document.getElementById('excludeWordsModal');
const closeModalButton = document.getElementById('closeModal');
const saveExcludeWordsButton = document.getElementById('saveExcludeWords');
const excludeWordsList = document.querySelector('.exclude-words-list');

// ローカルストレージから設定を読み込む
function loadSettings() {
  hideMessages = localStorage.getItem('hideMessages') === 'true';
  hideEpicGoals = localStorage.getItem('hideEpicGoals') === 'true';
  hideExcludedWords = localStorage.getItem('hideExcludedWords') === 'true';
  
  const storedExcludeWords = JSON.parse(localStorage.getItem('excludeWords') || '[]');
  excludeWords = storedExcludeWords.length ? storedExcludeWords : Array(20).fill('');
  
  sortMode = localStorage.getItem('sortMode') || 'time';
  groupLimits = JSON.parse(localStorage.getItem('groupLimits') || '{}');
  messages = JSON.parse(localStorage.getItem('messages') || '[]');

  // UIに設定を反映
  hideMessagesCheckbox.checked = hideMessages;
  hideEpicGoalsCheckbox.checked = hideEpicGoals;
  hideExcludedWordsCheckbox.checked = hideExcludedWords;
  sortModeSelect.value = sortMode;
}

// 設定を保存する関数
function saveSettings(key, value) {
  localStorage.setItem(key, typeof value === 'object' ? JSON.stringify(value) : value);
}

// モニタリングの開始/停止を切り替える
toggleButton.addEventListener('click', async () => {
  if (isMonitoring) {
    await stopMonitoring();
  } else {
    await startMonitoring();
  }
});

// モニタリングを開始する関数
async function startMonitoring() {
  const url = urlInput.value;
  if (!url) {
    errorElement.textContent = 'URLを入力してください';
    return;
  }

  try {
    errorElement.textContent = '';
    const response = await fetch('/api/start-monitoring', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ url }),
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.error || 'モニタリングの開始に失敗しました');
    }

    const data = await response.json();
    sessionId = data.session_id;
    
    // Server-Sent Eventsの接続を開始
    connectToEventStream(data.session_id);
    
    isMonitoring = true;
    toggleButton.textContent = 'モニタリング停止';
    statusIndicator.textContent = 'モニタリング中...';
    statusIndicator.className = 'monitoring-active';
    urlInput.disabled = true;
  } catch (err) {
    errorElement.textContent = err.message;
  }
}

// モニタリングを停止する関数
async function stopMonitoring() {
  if (!sessionId) return;

  try {
    // EventSourceを閉じる
    if (eventSource) {
      eventSource.close();
      eventSource = null;
    }

    // サーバーにモニタリング停止を通知
    await fetch(`/api/stop-monitoring/${sessionId}`, {
      method: 'POST',
    });

    isMonitoring = false;
    sessionId = null;
    toggleButton.textContent = 'モニタリング開始';
    statusIndicator.textContent = '停止中';
    statusIndicator.className = 'monitoring-inactive';
    urlInput.disabled = false;
  } catch (err) {
    errorElement.textContent = err.message;
  }
}

// EventStreamに接続する関数
function connectToEventStream(sid) {
  eventSource = new EventSource(`/api/stream/${sid}`);
  
  // 接続エラーカウンター
  let errorCount = 0;
  const maxErrors = 3;
  
  // 自動再接続タイマー
  let reconnectTimer = null;
  
  eventSource.onmessage = (event) => {
    // エラーカウンターをリセット（メッセージが来たので）
    errorCount = 0;
    
    console.log("Received event data:", event.data);
    let data;
    try {
      data = JSON.parse(event.data);
    } catch (e) {
      console.error("Failed to parse event data:", e);
      return;
    }
    
    console.log("Parsed event data:", data);
    
    switch (data.type) {
      case 'messages':
        console.log(`Received ${data.messages.length} messages from server`);
        if (data.messages.length > 0) {
          console.log("Sample message:", data.messages[0]);
        }
        
        // メッセージを受信したら即座に表示を更新
        requestAnimationFrame(() => {
          addNewMessages(data.messages);
        });
        break;
        
      case 'error':
        errorElement.textContent = data.error;
        stopMonitoring();
        break;
        
      case 'disconnected':
        stopMonitoring();
        break;
      
      case 'connected':
        console.log("Connected to stream with session ID:", data.session_id);
        errorElement.textContent = '';
        
        // 既存メッセージを再表示（接続時に一度更新）
        requestAnimationFrame(() => {
          updateCheckboxList();
        });
        break;
      
      case 'keepalive':
        console.log("Received keepalive");
        // キープアライブ受信時にもチェックリストのレンダリングを要求
        // 不要なレンダリングを防ぐため特定条件下でのみ実施
        if (messages.length > 0 && messages.some(m => !m.rendered)) {
          requestAnimationFrame(() => {
            updateCheckboxList();
          });
        }
        break;
    }
  };
  
  eventSource.onerror = (error) => {
    console.error('EventSource error:', error);
    errorCount++;
    
    if (errorCount >= maxErrors) {
      errorElement.textContent = '接続エラーが発生しました。再接続してください。';
      stopMonitoring();
    } else {
      // 一時的なエラーメッセージ
      errorElement.textContent = `接続エラーが発生しました(${errorCount}/${maxErrors})。再試行中...`;
      
      // 再接続タイマーをセット (既存のタイマーがあれば解除)
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
      }
      
      // 5秒後に自動再接続を試みる
      reconnectTimer = setTimeout(() => {
        if (eventSource) {
          eventSource.close();
        }
        
        // 新しい接続を作成
        eventSource = new EventSource(`/api/stream/${sid}`);
        console.log("Attempting to reconnect...");
      }, 5000);
    }
  };
}

// メッセージが除外ワードを含むかチェック
function containsExcludeWord(text) {
  if (!hideExcludedWords) return false;
  return excludeWords.some(word => word && text.includes(word));
}

// 新しいメッセージを追加する関数の最適化版
function addNewMessages(newMessages) {
  console.log(`Processing ${newMessages.length} new messages`);
  
  if (!Array.isArray(newMessages)) {
    console.error("Expected array but got:", typeof newMessages);
    return;
  }
  
  const existingIds = new Set();
  messages.forEach(msg => existingIds.add(msg.id));
  
  let addedCount = 0;
  
  newMessages.forEach(message => {
    if (!message.id) {
      console.warn("Message without ID:", message);
      return;
    }
    
    if (!existingIds.has(message.id)) {
      // レンダリング状態を追跡するフラグを追加
      message.rendered = false;
      
      // メッセージ配列に追加
      messages.push(message);
      existingIds.add(message.id);
      addedCount++;
    }
  });
  
  if (addedCount > 0) {
    console.log(`Added ${addedCount} new messages. Total now: ${messages.length}`);
    
    // レンダリングをリクエスト
    requestAnimationFrame(() => {
      // 配列を保存（頻繁な保存によるパフォーマンス低下を防ぐため、
      // ストレージへの保存は updateCheckboxList 内で行う）
      updateCheckboxList();
    });
  }
}

// メッセージアイテムを作成する関数
function createMessageItem(message, index, isGrouped = false, count = 1, isOverLimit = false) {
  const div = document.createElement('div');
  div.className = 'checkbox-item';

  const checkbox = document.createElement('input');
  checkbox.type = 'checkbox';
  checkbox.checked = message.checked || false;
  checkbox.id = `checkbox-${message.id}`;
  checkbox.addEventListener('change', function () {
    // チェック状態をメッセージオブジェクトに反映
    message.checked = checkbox.checked;
    // ローカルストレージに保存
    saveSettings('messages', messages);
  });

  const label = document.createElement('label');
  label.htmlFor = `checkbox-${message.id}`;
  label.appendChild(checkbox);
  
  // グループ化されている場合はユーザー名のみ表示
  if (isGrouped) {
    // ユーザー名部分を抽出 (【username】の形式から)
    const usernameMatch = message.text.match(/【(.*?)】/);
    const username = usernameMatch ? usernameMatch[1] : 'Unknown';
    
    // ユーザー名の後に投稿回数を表示
    const usernameText = document.createTextNode(username);
    label.appendChild(usernameText);
    
    // 件数表示（2件以上の場合のみ表示）
    if (count > 1) {
      const countSpan = document.createElement('span');
      countSpan.textContent = ` [${count}件]`;
      
      // 上限を超えている場合は赤文字で表示
      if (isOverLimit) {
        countSpan.className = 'count-over-limit';
      }
      
      label.appendChild(countSpan);
    }
  } else {
    // メッセージタイプを抽出
    const typeMatch = message.text.match(/\[(.*?)\]/);
    const messageType = typeMatch ? typeMatch[1] : '';
    
    // メッセージタイプを表示する要素
    if (messageType) {
      const typeSpan = document.createElement('span');
      typeSpan.className = `message-type ${messageType}`;
      typeSpan.textContent = messageType;
      label.appendChild(typeSpan);
    }
    
    // メッセージ本文
    label.appendChild(document.createTextNode(" " + message.text));
  }
  
  div.appendChild(label);

  return div;
}

// チェックリスト更新関数を最適化
function updateCheckboxList() {
  // 表示前にメッセージをレンダリング済みとマーク
  messages.forEach(msg => {
    msg.rendered = true;
  });
  
  // ローカルストレージに保存（レンダリングの前に保存）
  saveSettings('messages', messages);

  // レンダリング処理
  checkboxList.innerHTML = '';

  // フィルターを適用
  let filteredMessages = messages.filter(msg => {
    if (hideMessages && msg.type === 'メッセージ') return false;
    if (hideEpicGoals && msg.type === 'エピックゴール') return false;
    if (containsExcludeWord(msg.text)) return false;
    return true;
  });

  if (sortMode === 'time') {
    // 時間順
    filteredMessages.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
    filteredMessages.forEach((message, index) => {
      checkboxList.appendChild(createMessageItem(message, index));
    });
  } else {
    // 内容でグループ化
    const groupedMessages = {};
    filteredMessages.forEach(message => {
      const match = message.text.match(/\[(.*?)\] .*?：(.*?) 【/);
      if (match) {
        const [, type, commentText] = match;
        const groupKey = `[${type}] ：${commentText}`;

        if (!groupedMessages[groupKey]) {
          groupedMessages[groupKey] = [];
        }
        groupedMessages[groupKey].push(message);
      }
    });

    // グループごとに表示
    Object.entries(groupedMessages).forEach(([groupKey, messages]) => {
      const groupDiv = document.createElement('div');
      groupDiv.className = 'message-group';

      // ユーザーごとのカウント用マップを作成
      const userCounts = {};
      messages.forEach(message => {
        const usernameMatch = message.text.match(/【(.*?)】/);
        if (usernameMatch) {
          const username = usernameMatch[1];
          userCounts[username] = (userCounts[username] || 0) + 1;
        }
      });

      // ユーザー数とメッセージ数を計算
      const uniqueUsers = Object.keys(userCounts);
      const totalUsers = uniqueUsers.length;

      // グループのヘッダー部分
      const headerDiv = document.createElement('div');
      headerDiv.className = 'message-group-header';

      // まとめてチェックボタン
      const groupCheckButton = document.createElement('button');
      groupCheckButton.type = 'button';
      groupCheckButton.className = 'group-check-button';
      groupCheckButton.textContent = 'All Check';
      headerDiv.appendChild(groupCheckButton);

      // メッセージ内容と件数を設定するための変数
      const titleSpan = document.createElement('span');
      titleSpan.textContent = ` ${groupKey}`; // 初期値
      headerDiv.appendChild(titleSpan);

      // ユーザーカウント上限設定
      const limitContainer = document.createElement('div');
      limitContainer.className = 'user-limit-container';

      const limitLabel = document.createElement('label');
      limitLabel.textContent = '上限:';
      limitLabel.style.fontSize = '12px';

      // セレクトボックス
      const limitSelect = document.createElement('select');
      limitSelect.className = 'user-limit-select';
      
      // 無制限オプション
      const infinityOption = document.createElement('option');
      infinityOption.value = 'infinity';
      infinityOption.textContent = '∞';
      limitSelect.appendChild(infinityOption);
      
      // 数値オプション
      for (let i = 1; i <= 20; i++) {
        const option = document.createElement('option');
        option.value = i;
        option.textContent = i;
        limitSelect.appendChild(option);
      }
      
      // グループキーに基づいて個別の上限を取得（デフォルトは無制限）
      const currentLimit = groupLimits[groupKey] !== undefined ? groupLimits[groupKey] : 'infinity';
      limitSelect.value = currentLimit;

      limitSelect.addEventListener('change', function() {
        const newLimit = this.value;
        
        // 上限変更をローカルストレージに保存
        groupLimits[groupKey] = newLimit;
        saveSettings('groupLimits', groupLimits);
        
        // 表示可能なメッセージ数を再計算
        let displayableCount = 0;
        const recountedUserCounts = {};
        
        messages.forEach((message) => {
          const usernameMatch = message.text.match(/【(.*?)】/);
          if (usernameMatch) {
            const username = usernameMatch[1];
            recountedUserCounts[username] = (recountedUserCounts[username] || 0) + 1;
            
            // 無制限の場合は全てカウント、そうでなければ上限まで
            if (newLimit === 'infinity' || recountedUserCounts[username] <= parseInt(newLimit, 10)) {
              displayableCount++;
            }
          }
        });
        
        // ヘッダーの件数表示だけを更新
        titleSpan.innerHTML = ` ${groupKey} (<strong>${displayableCount}件</strong> / <strong>${totalUsers}ユーザー</strong>)`;
        
        // 上限変更後に再度リストを更新
        updateGroupContent(groupDiv, messages, newLimit, userCounts);
      });

      limitContainer.appendChild(limitLabel);
      limitContainer.appendChild(limitSelect);
      headerDiv.appendChild(limitContainer);

      groupDiv.appendChild(headerDiv);

      // グループコンテンツの更新機能
      function updateGroupContent(container, groupMessages, limit, userCountMap) {
        // ヘッダーの次の要素から全て削除（ヘッダーは保持）
        while (container.childElementCount > 1) {
          container.removeChild(container.lastChild);
        }
        
        // ユーザーごとのメッセージを管理
        const userMessages = {};
        
        // まずメッセージをユーザーごとにグループ化
        groupMessages.forEach(message => {
          const usernameMatch = message.text.match(/【(.*?)】/);
          if (usernameMatch) {
            const username = usernameMatch[1];
            if (!userMessages[username]) {
              userMessages[username] = [];
            }
            userMessages[username].push(message);
          }
        });
        
        // ユーザーごとに1件だけ表示し、投稿数を表示
        Object.entries(userMessages).forEach(([username, userMsgs]) => {
          // 最新の投稿を表示
          userMsgs.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
          const latestMessage = userMsgs[0];
          const count = userMsgs.length;
          
          // 上限を超えているかどうかチェック
          const isOverLimit = limit !== 'infinity' && count > parseInt(limit, 10);
          
          // メッセージアイテムを作成して追加
          const messageItem = createMessageItem(
            latestMessage, 
            0, 
            true, 
            count, 
            isOverLimit
          );
          
          container.appendChild(messageItem);
        });
      }

      // 個別のメッセージを時間順にソート
      messages.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));

      // 表示可能なメッセージ数を計算（上限を適用）
      let displayableMessageCount = 0;
      const displayLimits = {};
      
      // グループの上限設定を取得（デフォルトは無制限）
      const groupLimit = groupLimits[groupKey] !== undefined ? groupLimits[groupKey] : 'infinity';
      
      // ユーザーごとに表示上限を計算
      Object.entries(userCounts).forEach(([username, count]) => {
        if (groupLimit === 'infinity') {
          displayableMessageCount += count;
          displayLimits[username] = count;
        } else {
          const limit = Math.min(count, parseInt(groupLimit, 10));
          displayableMessageCount += limit;
          displayLimits[username] = limit;
        }
      });

      // ヘッダーのメッセージ数を更新（件数とユーザー数を太字で表示）
      titleSpan.innerHTML = ` ${groupKey} (<strong>${displayableMessageCount}件</strong> / <strong>${totalUsers}ユーザー</strong>)`;

      // グループコンテンツを初期化
      updateGroupContent(groupDiv, messages, groupLimit, userCounts);

      // まとめてチェックボタンのイベントハンドラ
      groupCheckButton.addEventListener('click', () => {
        // 表示されているチェックボックスの状態を確認
        const checkboxes = Array.from(groupDiv.querySelectorAll('input[type="checkbox"]'));
        const allChecked = checkboxes.every(cb => cb.checked);

        // 全てチェック済みなら全解除、そうでなければ全チェック
        const newState = !allChecked;

        // 表示されている項目のチェック状態を変更
        checkboxes.forEach(checkbox => {
          checkbox.checked = newState;
          const messageId = checkbox.id.replace('checkbox-', '');
          const messageIndex = messages.findIndex(m => m.id === messageId);
          if (messageIndex !== -1) {
            messages[messageIndex].checked = newState;
          }
        });

        // ストレージを更新
        saveSettings('messages', messages);
      });

      checkboxList.appendChild(groupDiv);
    });
  }
}

// フィルターの変更を監視
hideMessagesCheckbox.addEventListener('change', function () {
  hideMessages = this.checked;
  saveSettings('hideMessages', hideMessages);
  updateCheckboxList();
});

hideEpicGoalsCheckbox.addEventListener('change', function () {
  hideEpicGoals = this.checked;
  saveSettings('hideEpicGoals', hideEpicGoals);
  updateCheckboxList();
});

hideExcludedWordsCheckbox.addEventListener('change', function () {
  hideExcludedWords = this.checked;
  saveSettings('hideExcludedWords', hideExcludedWords);
  updateCheckboxList();
});

sortModeSelect.addEventListener('change', function () {
  sortMode = this.value;
  saveSettings('sortMode', sortMode);
  updateCheckboxList();
});

// 除外ワード設定モーダルの処理
showExcludeWordsButton.addEventListener('click', function() {
  createExcludeWordFields();
  excludeWordsModal.classList.add('show');
});

closeModalButton.addEventListener('click', function() {
  excludeWordsModal.classList.remove('show');
});

saveExcludeWordsButton.addEventListener('click', function() {
  const inputs = excludeWordsList.querySelectorAll('input');
  excludeWords = Array.from(inputs).map(input => input.value.trim());
  
  const filtered = excludeWords.filter(word => word !== '');
  excludeWords = filtered.length ? filtered : Array(20).fill('');
  
  saveSettings('excludeWords', excludeWords);
  excludeWordsModal.classList.remove('show');
  updateCheckboxList();
});

// 除外ワード入力フィールドを生成
function createExcludeWordFields() {
  excludeWordsList.innerHTML = '';
  excludeWords.forEach((word, index) => {
    const div = document.createElement('div');
    div.className = 'exclude-word-item';

    const input = document.createElement('input');
    input.type = 'text';
    input.value = word;
    input.placeholder = `除外ワード ${index + 1}`;
    input.dataset.index = index;

    div.appendChild(input);
    excludeWordsList.appendChild(div);
  });
}

// チェック済み項目の削除
removeCheckedButton.addEventListener('click', function() {
  const uncheckedMessages = messages.filter(message => !message.checked);
  messages = uncheckedMessages;
  saveSettings('messages', messages);
  updateCheckboxList();
});

// リセット
resetButton.addEventListener('click', function() {
  messages = [];
  saveSettings('messages', messages);
  updateCheckboxList();
});

// ポーリング更新を追加
let updatePollingInterval = null;

// ページが閉じられるときにモニタリングを停止
window.addEventListener('beforeunload', () => {
  if (updatePollingInterval) {
    clearInterval(updatePollingInterval);
  }
  
  if (isMonitoring) {
    stopMonitoring();
  }
});

// 初期化
document.addEventListener('DOMContentLoaded', function() {
  loadSettings();
  updateCheckboxList();
  
  // 5秒ごとにメッセージ表示を更新（セッション中のみ）
  updatePollingInterval = setInterval(() => {
    if (isMonitoring && messages.some(m => !m.rendered)) {
      console.log("Updating display via polling interval");
      updateCheckboxList();
    }
  }, 5000);
});