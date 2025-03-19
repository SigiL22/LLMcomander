// js/llmChat.js

(function() {
  // Создаем контейнер для чата
  function createChatWindow() {
    const chatContainer = document.createElement('div');
    chatContainer.id = "llmChatContainer";
    chatContainer.style.position = "absolute";
    chatContainer.style.left = "10px";
    chatContainer.style.top = "10px";
    chatContainer.style.width = "300px";
    chatContainer.style.height = "calc(100vh - 20px)";
    chatContainer.style.backgroundColor = "rgba(255, 255, 255, 0.9)";
    chatContainer.style.border = "1px solid #ccc";
    chatContainer.style.zIndex = "1000";
    chatContainer.style.display = "flex";
    chatContainer.style.flexDirection = "column";
    chatContainer.style.overflow = "hidden";

    // Заголовок
    const header = document.createElement('div');
    header.innerText = "LLM Чат";
    header.style.padding = "5px";
    header.style.backgroundColor = "#f0f0f0";
    header.style.borderBottom = "1px solid #ccc";
    header.style.fontWeight = "bold";
    chatContainer.appendChild(header);

    // Окно сообщений
    const messagesDiv = document.createElement('div');
    messagesDiv.id = "llmMessages";
    messagesDiv.style.flex = "1";
    messagesDiv.style.padding = "10px";
    messagesDiv.style.overflowY = "auto";
    messagesDiv.style.fontSize = "12px";
    chatContainer.appendChild(messagesDiv);

    // Поле ввода
    const inputContainer = document.createElement('div');
    inputContainer.style.padding = "5px";
    inputContainer.style.borderTop = "1px solid #ccc";
    inputContainer.style.display = "flex";

    const input = document.createElement('input');
    input.type = "text";
    input.id = "llmInput";
    input.placeholder = "Введите команду для LLM...";
    input.style.flex = "1";
    input.style.padding = "5px";
    input.style.border = "1px solid #ccc";
    input.style.marginRight = "5px";
    inputContainer.appendChild(input);

    const sendBtn = document.createElement('button');
    sendBtn.innerText = "Отправить";
    sendBtn.style.padding = "5px";
    sendBtn.onclick = sendMessage;
    inputContainer.appendChild(sendBtn);

    chatContainer.appendChild(inputContainer);
    document.body.appendChild(chatContainer);

    // Обработчик Enter
    input.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') {
        sendMessage();
      }
    });

    // Сдвигаем карту вправо
    const mapDiv = document.getElementById('map');
    mapDiv.style.width = "calc(100% - 320px)";
    mapDiv.style.left = "320px";
  }

  // Добавление сообщения в окно
  function addMessage(content, isUser = false) {
    const messagesDiv = document.getElementById('llmMessages');
    const messageDiv = document.createElement('div');
    messageDiv.style.marginBottom = "10px";
    messageDiv.style.padding = "5px";
    messageDiv.style.backgroundColor = isUser ? "#e0f7fa" : "#f1f8e9";
    messageDiv.style.borderRadius = "3px";
    messageDiv.textContent = content;
    messagesDiv.appendChild(messageDiv);
    messagesDiv.scrollTop = messagesDiv.scrollHeight; // Прокрутка вниз
  }

  // Отправка сообщения в LLM
  function sendMessage() {
    const input = document.getElementById('llmInput');
    const message = input.value.trim();
    if (!message) return;

    addMessage(message, true); // Добавляем сообщение пользователя
    input.value = ""; // Очищаем поле ввода

    const jsonInput = { "command": message }; // Формируем JSON
    fetch('/llm_command', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ json_input: jsonInput })
    })
    .then(response => response.json())
    .then(data => {
      if (data.status === "success" && data.response) {
        const responseText = JSON.stringify(data.response, null, 2);
        addMessage(responseText); // Добавляем ответ LLM
      } else {
        addMessage(`Ошибка: ${data.message || 'Нет ответа от LLM'}`);
      }
    })
    .catch(err => {
      addMessage(`Ошибка отправки: ${err}`);
      console.error("Ошибка отправки сообщения в LLM:", err);
    });
  }

  // Инициализация
  createChatWindow();
})();