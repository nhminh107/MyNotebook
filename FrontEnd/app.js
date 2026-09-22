const storageKeys = {
  user: "notebook.currentUser",
  currentChat: (userId) => `notebook.currentChat.${userId}`,
};

const state = {
  authMode: "login",
  user: readStorage(storageKeys.user, null),
  chatId: null,
  chats: [],
  documents: [],
  messages: [],
  answerMode: "retrieval",
  isSending: false,
  isUploading: false,
};

const elements = {
  authScreen: document.querySelector("#auth-screen"),
  appShell: document.querySelector("#app-shell"),
  authForm: document.querySelector("#auth-form"),
  authTabs: document.querySelectorAll("[data-auth-mode]"),
  authTitle: document.querySelector("#auth-title"),
  authDescription: document.querySelector("#auth-description"),
  authSubmit: document.querySelector("#auth-submit"),
  authError: document.querySelector("#auth-error"),
  userNameInput: document.querySelector("#user-name"),
  passwordInput: document.querySelector("#password"),
  accountName: document.querySelector("#account-name"),
  accountAvatar: document.querySelector("#account-avatar"),
  logoutButton: document.querySelector("#logout-button"),
  newChatButton: document.querySelector("#new-chat-button"),
  chatHistoryList: document.querySelector("#chat-history-list"),
  chatCount: document.querySelector("#chat-count"),
  fileInput: document.querySelector("#file-input"),
  uploadStatus: document.querySelector("#upload-status"),
  documentList: document.querySelector("#document-list"),
  documentCount: document.querySelector("#document-count"),
  emptyState: document.querySelector("#empty-state"),
  messageList: document.querySelector("#message-list"),
  chatScroll: document.querySelector("#chat-scroll"),
  chatContext: document.querySelector("#chat-context"),
  answerMode: document.querySelector("#answer-mode"),
  agentModeOption: document.querySelector("#agent-mode-option"),
  composerNote: document.querySelector("#composer-note"),
  chatForm: document.querySelector("#chat-form"),
  questionInput: document.querySelector("#question-input"),
  sendButton: document.querySelector("#send-button"),
  suggestions: document.querySelectorAll("[data-prompt]"),
  sidebar: document.querySelector("#sidebar"),
  sidebarScrim: document.querySelector("#sidebar-scrim"),
  openSidebar: document.querySelector("#open-sidebar"),
  closeSidebar: document.querySelector("#close-sidebar"),
};

function readStorage(key, fallback) {
  try {
    const value = localStorage.getItem(key);
    return value ? JSON.parse(value) : fallback;
  } catch {
    return fallback;
  }
}

function writeStorage(key, value) {
  localStorage.setItem(key, JSON.stringify(value));
}

function createChatId() {
  return crypto.randomUUID();
}

function getErrorMessage(payload, fallback) {
  if (typeof payload?.detail === "string") {
    return payload.detail;
  }

  if (Array.isArray(payload?.detail)) {
    return payload.detail.map((item) => item.msg).filter(Boolean).join(" ") || fallback;
  }

  return fallback;
}

async function apiRequest(path, options = {}) {
  let response;

  try {
    response = await fetch(path, options);
  } catch {
    throw new Error("Không thể kết nối tới API. Hãy kiểm tra FastAPI đang chạy.");
  }

  let payload = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  if (!response.ok) {
    throw new Error(getErrorMessage(payload, `Yêu cầu thất bại với mã ${response.status}.`));
  }

  return payload;
}

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function getSafeMarkdownUrl(value) {
  try {
    const url = new URL(value, window.location.origin);
    if (!["http:", "https:", "mailto:"].includes(url.protocol)) {
      return null;
    }
    return url.href;
  } catch {
    return null;
  }
}

function renderInlineMarkdown(source) {
  const tokens = [];
  const storeToken = (html) => {
    const token = `\u0000${tokens.length}\u0000`;
    tokens.push(html);
    return token;
  };

  let value = source.replace(/`([^`\n]+)`/g, (_, code) => {
    return storeToken(`<code>${escapeHtml(code)}</code>`);
  });

  value = value.replace(/\[([^\]]+)]\(([^)\s]+)\)/g, (_, label, urlValue) => {
    const safeUrl = getSafeMarkdownUrl(urlValue);
    if (!safeUrl) {
      return escapeHtml(label);
    }

    return storeToken(
      `<a href="${escapeHtml(safeUrl)}" target="_blank" rel="noreferrer">${escapeHtml(label)}</a>`,
    );
  });

  value = escapeHtml(value);
  value = value.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  value = value.replace(/__([^_]+)__/g, "<strong>$1</strong>");
  value = value.replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<em>$2</em>");
  value = value.replace(/(^|[^_])_([^_\n]+)_/g, "$1<em>$2</em>");

  return value.replace(/\u0000(\d+)\u0000/g, (_, index) => tokens[Number(index)]);
}

function getMarkdownTableCells(line) {
  return line
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((cell) => cell.trim());
}

function isMarkdownTableSeparator(line) {
  const cells = getMarkdownTableCells(line);
  return cells.length > 0 && cells.every((cell) => /^:?-{3,}:?$/.test(cell));
}

function renderMarkdown(markdown) {
  const lines = markdown.replace(/\r\n?/g, "\n").split("\n");
  const output = [];
  let paragraphLines = [];
  let listItems = [];
  let orderedList = false;

  const flushParagraph = () => {
    if (paragraphLines.length === 0) {
      return;
    }
    output.push(`<p>${renderInlineMarkdown(paragraphLines.join(" "))}</p>`);
    paragraphLines = [];
  };

  const flushList = () => {
    if (listItems.length === 0) {
      return;
    }
    const tag = orderedList ? "ol" : "ul";
    const items = listItems.map((item) => `<li>${renderInlineMarkdown(item)}</li>`).join("");
    output.push(`<${tag}>${items}</${tag}>`);
    listItems = [];
  };

  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index];
    const trimmed = line.trim();

    if (trimmed.startsWith("```")) {
      flushParagraph();
      flushList();
      const language = trimmed.slice(3).trim().replace(/[^a-zA-Z0-9_-]/g, "");
      const codeLines = [];
      index += 1;
      while (index < lines.length && !lines[index].trim().startsWith("```")) {
        codeLines.push(lines[index]);
        index += 1;
      }
      const languageAttribute = language ? ` data-language="${language}"` : "";
      output.push(`<pre><code${languageAttribute}>${escapeHtml(codeLines.join("\n"))}</code></pre>`);
      continue;
    }

    if (
      trimmed.includes("|")
      && index + 1 < lines.length
      && isMarkdownTableSeparator(lines[index + 1])
    ) {
      flushParagraph();
      flushList();
      const headers = getMarkdownTableCells(trimmed);
      const rows = [];
      index += 2;
      while (index < lines.length && lines[index].trim().includes("|")) {
        rows.push(getMarkdownTableCells(lines[index]));
        index += 1;
      }
      index -= 1;

      const headerHtml = headers
        .map((cell) => `<th>${renderInlineMarkdown(cell)}</th>`)
        .join("");
      const bodyHtml = rows
        .map((row) => {
          const cells = headers.map((_, cellIndex) => row[cellIndex] || "");
          return `<tr>${cells.map((cell) => `<td>${renderInlineMarkdown(cell)}</td>`).join("")}</tr>`;
        })
        .join("");
      output.push(
        `<div class="markdown-table-wrap"><table><thead><tr>${headerHtml}</tr></thead><tbody>${bodyHtml}</tbody></table></div>`,
      );
      continue;
    }

    const headingMatch = trimmed.match(/^(#{1,4})\s+(.+)$/);
    if (headingMatch) {
      flushParagraph();
      flushList();
      const level = headingMatch[1].length;
      output.push(`<h${level}>${renderInlineMarkdown(headingMatch[2])}</h${level}>`);
      continue;
    }

    const unorderedMatch = line.match(/^\s*[-+*]\s+(.+)$/);
    const orderedMatch = line.match(/^\s*\d+\.\s+(.+)$/);
    if (unorderedMatch || orderedMatch) {
      flushParagraph();
      const nextOrderedState = Boolean(orderedMatch);
      if (listItems.length > 0 && nextOrderedState !== orderedList) {
        flushList();
      }
      orderedList = nextOrderedState;
      listItems.push((orderedMatch || unorderedMatch)[1]);
      continue;
    }

    const quoteMatch = trimmed.match(/^>\s?(.+)$/);
    if (quoteMatch) {
      flushParagraph();
      flushList();
      output.push(`<blockquote>${renderInlineMarkdown(quoteMatch[1])}</blockquote>`);
      continue;
    }

    if (!trimmed) {
      flushParagraph();
      flushList();
      continue;
    }

    flushList();
    paragraphLines.push(trimmed);
  }

  flushParagraph();
  flushList();
  return output.join("");
}

function renderMarkdownInto(element, markdown) {
  element.innerHTML = renderMarkdown(markdown);
}

function parseSseEvent(block) {
  let event = "message";
  const dataLines = [];

  block.split("\n").forEach((line) => {
    if (line.startsWith("event:")) {
      event = line.slice(6).trim();
    }
    if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trimStart());
    }
  });

  if (dataLines.length === 0) {
    return null;
  }

  return {
    event,
    payload: JSON.parse(dataLines.join("\n")),
  };
}

async function streamRetrieval(request, onToken, mode = "retrieval") {
  const endpoint = mode === "agent"
    ? "/documents/retrieval/agent-stream"
    : "/documents/retrieval/stream";
  let response;
  try {
    response = await fetch(endpoint, {
      method: "POST",
      headers: {
        Accept: "text/event-stream",
        "Content-Type": "application/json",
      },
      body: JSON.stringify(request),
    });
  } catch {
    throw new Error("Không thể kết nối tới API. Hãy kiểm tra FastAPI đang chạy.");
  }

  if (!response.ok) {
    let payload = null;
    try {
      payload = await response.json();
    } catch {
      payload = null;
    }
    throw new Error(getErrorMessage(payload, `Yêu cầu thất bại với mã ${response.status}.`));
  }

  if (!response.body) {
    throw new Error("Trình duyệt không hỗ trợ nhận dữ liệu streaming.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let completed = false;

  try {
    while (true) {
      const { done, value } = await reader.read();
      buffer += decoder.decode(value || new Uint8Array(), { stream: !done });

      let boundaryIndex = buffer.indexOf("\n\n");
      while (boundaryIndex >= 0) {
        const eventBlock = buffer.slice(0, boundaryIndex);
        buffer = buffer.slice(boundaryIndex + 2);
        const streamEvent = parseSseEvent(eventBlock);

        if (streamEvent?.event === "token") {
          onToken(streamEvent.payload.content || "");
        } else if (streamEvent?.event === "error") {
          throw new Error(streamEvent.payload.detail || "Streaming thất bại.");
        } else if (streamEvent?.event === "done") {
          completed = true;
        }

        boundaryIndex = buffer.indexOf("\n\n");
      }

      if (done) {
        break;
      }
    }
  } finally {
    reader.releaseLock();
  }

  if (!completed) {
    throw new Error("Luồng trả lời đã kết thúc không đầy đủ.");
  }
}

function setAuthMode(mode) {
  state.authMode = mode;
  const isLogin = mode === "login";

  elements.authTabs.forEach((tab) => {
    const isActive = tab.dataset.authMode === mode;
    tab.classList.toggle("is-active", isActive);
    tab.setAttribute("aria-selected", String(isActive));
  });

  elements.authTitle.textContent = isLogin ? "Chào mừng trở lại" : "Tạo tài khoản mới";
  elements.authDescription.textContent = isLogin
    ? "Đăng nhập để tiếp tục với tài liệu của bạn."
    : "Tạo không gian riêng để tải lên và hỏi đáp tài liệu.";
  elements.authSubmit.textContent = isLogin ? "Đăng nhập" : "Tạo tài khoản";
  elements.passwordInput.autocomplete = isLogin ? "current-password" : "new-password";
  elements.authError.textContent = "";
}

function setAuthLoading(isLoading) {
  elements.authSubmit.disabled = isLoading;
  elements.userNameInput.disabled = isLoading;
  elements.passwordInput.disabled = isLoading;

  if (isLoading) {
    elements.authSubmit.textContent = "Đang xử lý...";
  } else {
    elements.authSubmit.textContent = state.authMode === "login" ? "Đăng nhập" : "Tạo tài khoản";
  }
}

async function handleAuthSubmit(event) {
  event.preventDefault();
  elements.authError.textContent = "";

  if (!elements.authForm.checkValidity()) {
    elements.authForm.reportValidity();
    return;
  }

  const credentials = {
    user_name: elements.userNameInput.value.trim(),
    password: elements.passwordInput.value,
  };

  setAuthLoading(true);

  try {
    const payload = await apiRequest(`/auth/${state.authMode}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(credentials),
    });

    state.user = payload.data;
    writeStorage(storageKeys.user, state.user);
    elements.authForm.reset();
    showApplication();
  } catch (error) {
    elements.authError.textContent = error.message;
  } finally {
    setAuthLoading(false);
  }
}

function showApplication() {
  if (!state.user) {
    elements.authScreen.classList.remove("is-hidden");
    elements.appShell.classList.add("is-hidden");
    window.setTimeout(() => elements.userNameInput.focus(), 0);
    return;
  }

  elements.authScreen.classList.add("is-hidden");
  elements.appShell.classList.remove("is-hidden");
  elements.accountName.textContent = state.user.user_name;
  elements.accountAvatar.textContent = state.user.user_name.slice(0, 1) || "N";
  configureAnswerMode();
  state.chatId = readStorage(storageKeys.currentChat(state.user.user_id), null) || createChatId();
  writeStorage(storageKeys.currentChat(state.user.user_id), state.chatId);
  state.documents = [];
  renderDocuments();
  initializeChatHistory();
  window.setTimeout(() => elements.questionInput.focus(), 0);
}

function handleLogout() {
  localStorage.removeItem(storageKeys.user);
  state.user = null;
  state.chatId = null;
  state.chats = [];
  state.documents = [];
  state.answerMode = "retrieval";
  resetConversation();
  closeSidebar();
  setAuthMode("login");
  showApplication();
}

function getChatTitle(chat) {
  const firstTurn = Array.isArray(chat.conversation) ? chat.conversation[0] : null;
  const firstMessage = firstTurn?.user?.trim();
  return firstMessage || `Cuộc trò chuyện ${chat.chat_id.slice(0, 8)}`;
}

function renderChatHistory() {
  elements.chatHistoryList.replaceChildren();
  elements.chatCount.textContent = String(state.chats.length);

  if (state.chats.length === 0) {
    const emptyItem = document.createElement("li");
    emptyItem.className = "chat-history-empty";
    emptyItem.textContent = "Chưa có cuộc trò chuyện.";
    elements.chatHistoryList.append(emptyItem);
    return;
  }

  state.chats.forEach((chat) => {
    const item = document.createElement("li");
    item.className = "chat-history-item";

    const button = document.createElement("button");
    button.type = "button";
    button.classList.toggle("is-active", chat.chat_id === state.chatId);

    const title = document.createElement("span");
    title.className = "chat-history-title";
    title.textContent = getChatTitle(chat);

    const date = document.createElement("span");
    date.className = "chat-history-date";
    date.textContent = new Date(chat.created_at).toLocaleString("vi-VN");

    button.append(title, date);
    button.addEventListener("click", async () => {
      try {
        await selectChat(chat.chat_id);
      } catch (error) {
        elements.chatContext.textContent = error.message;
      }
    });
    item.append(button);
    elements.chatHistoryList.append(item);
  });
}

function renderConversation() {
  elements.messageList.replaceChildren();

  if (state.messages.length === 0) {
    elements.emptyState.classList.remove("is-hidden");
  } else {
    elements.emptyState.classList.add("is-hidden");
    state.messages.forEach((message) => {
      elements.messageList.append(createMessage(message.role, message.text));
    });
  }

  elements.chatContext.textContent = state.documents.length
    ? `${state.documents.length} tài liệu trong cuộc trò chuyện`
    : "Sẵn sàng nhận câu hỏi";
  scrollToLatestMessage();
}

async function loadChatHistory() {
  const payload = await apiRequest(
    `/documents/chats/${encodeURIComponent(state.user.user_id)}`,
  );
  state.chats = payload.data || [];
  renderChatHistory();
  return state.chats;
}

async function selectChat(chatId) {
  const payload = await apiRequest(
    `/documents/chats/${encodeURIComponent(state.user.user_id)}/${encodeURIComponent(chatId)}`,
  );
  const { chat, documents } = payload.data;

  state.chatId = chat.chat_id;
  writeStorage(storageKeys.currentChat(state.user.user_id), state.chatId);
  state.documents = (documents || []).map((documentItem) => ({
    document_id: documentItem.document_id,
    name: documentItem.file_name || `Tài liệu ${documentItem.document_id.slice(0, 8)}`,
    type: documentItem.type,
  }));
  state.messages = [];

  (chat.conversation || []).forEach((turn) => {
    state.messages.push({ role: "user", text: turn.user || "" });
    state.messages.push({ role: "assistant", text: turn.chatbot || "" });
  });

  renderDocuments();
  renderConversation();
  renderChatHistory();
  closeSidebar();
}

async function initializeChatHistory() {
  try {
    const chats = await loadChatHistory();
    if (chats.length === 0) {
      resetConversation();
      return;
    }

    const selectedChat = chats.find((chat) => chat.chat_id === state.chatId) || chats[0];
    await selectChat(selectedChat.chat_id);
  } catch (error) {
    elements.chatContext.textContent = error.message;
  }
}

function renderDocuments() {
  elements.documentList.replaceChildren();
  elements.documentCount.textContent = String(state.documents.length);

  if (state.documents.length === 0) {
    const emptyItem = document.createElement("li");
    emptyItem.className = "document-empty";
    emptyItem.textContent = "Chưa có tài liệu trong phiên này.";
    elements.documentList.append(emptyItem);
    return;
  }

  state.documents.forEach((documentItem) => {
    const item = document.createElement("li");
    item.className = "document-item";

    const name = document.createElement("span");
    name.className = "document-name";
    name.textContent = documentItem.name;
    name.title = documentItem.name;

    const type = document.createElement("span");
    type.className = "document-type";
    type.textContent = documentItem.type;

    item.append(name, type);
    elements.documentList.append(item);
  });
}

function setUploadStatus(message, type = "loading") {
  elements.uploadStatus.textContent = message;
  elements.uploadStatus.classList.remove("is-hidden", "is-error", "is-success");

  if (type === "error") {
    elements.uploadStatus.classList.add("is-error");
  }

  if (type === "success") {
    elements.uploadStatus.classList.add("is-success");
  }
}

async function handleFileUpload() {
  const [file] = elements.fileInput.files;
  if (!file || !state.user || state.isUploading) {
    return;
  }

  const extension = file.name.split(".").pop()?.toLowerCase();
  if (!new Set(["pdf", "docx", "txt"]).has(extension)) {
    setUploadStatus("Định dạng không được hỗ trợ. Chỉ nhận PDF, DOCX và TXT.", "error");
    elements.fileInput.value = "";
    return;
  }

  const formData = new FormData();
  formData.append("user_id", state.user.user_id);
  formData.append("chat_id", state.chatId);
  formData.append("file", file);
  state.isUploading = true;
  elements.fileInput.disabled = true;
  elements.chatContext.textContent = `Đang xử lý ${file.name}`;
  setUploadStatus(`Đang tải ${file.name}...`);

  try {
    const payload = await apiRequest("/documents/upload", {
      method: "POST",
      body: formData,
    });

    await loadChatHistory();
    await selectChat(state.chatId);

    setUploadStatus(`${payload.filename} đã sẵn sàng để hỏi đáp.`, "success");
    elements.chatContext.textContent = `${state.documents.length} tài liệu đã tải lên`;
  } catch (error) {
    setUploadStatus(error.message, "error");
    elements.chatContext.textContent = "Tải tài liệu thất bại";
  } finally {
    state.isUploading = false;
    elements.fileInput.disabled = false;
    elements.fileInput.value = "";
  }
}

function createMessage(role, text, options = {}) {
  const message = document.createElement("article");
  message.className = `message ${role}`;
  if (options.error) {
    message.classList.add("error");
  }

  const avatar = document.createElement("span");
  avatar.className = "message-avatar";
  avatar.setAttribute("aria-hidden", "true");
  avatar.textContent = role === "user" ? state.user.user_name.slice(0, 1) : "N";

  const content = document.createElement("div");
  content.className = "message-content";

  const roleLabel = document.createElement("span");
  roleLabel.className = "message-role";
  roleLabel.textContent = role === "user" ? "Bạn" : "Notebook";

  content.append(roleLabel);

  if (options.loading) {
    const loading = document.createElement("div");
    loading.className = "message-loading";
    loading.setAttribute("aria-label", "Đang tạo câu trả lời");
    loading.append(document.createElement("span"), document.createElement("span"), document.createElement("span"));
    content.append(loading);
  } else {
    const messageBody = document.createElement(role === "assistant" ? "div" : "p");
    messageBody.className = "message-text";

    if (role === "assistant" && !options.error) {
      messageBody.classList.add("markdown-body");
      renderMarkdownInto(messageBody, text);
    } else {
      messageBody.textContent = text;
    }

    content.append(messageBody);
  }

  message.append(avatar, content);
  return message;
}

function scrollToLatestMessage() {
  window.requestAnimationFrame(() => {
    elements.chatScroll.scrollTop = elements.chatScroll.scrollHeight;
  });
}

function setSending(isSending) {
  state.isSending = isSending;
  elements.sendButton.disabled = isSending;
  elements.questionInput.disabled = isSending;
  elements.answerMode.disabled = isSending;
  elements.sendButton.textContent = isSending ? "Đợi..." : "Gửi";
  elements.chatForm.setAttribute("aria-busy", String(isSending));
}

function configureAnswerMode() {
  const isProUser = state.user?.plan?.toLowerCase() === "pro";
  elements.agentModeOption.disabled = !isProUser;

  if (!isProUser && state.answerMode === "agent") {
    state.answerMode = "retrieval";
  }

  elements.answerMode.value = state.answerMode;
  elements.composerNote.textContent = state.answerMode === "agent"
    ? "Agent có thể dùng tài liệu và công cụ bổ sung. Hãy kiểm tra lại thông tin quan trọng."
    : "Câu trả lời được tạo từ dữ liệu retrieval. Hãy kiểm tra lại thông tin quan trọng.";
}

async function handleQuestionSubmit(event) {
  event.preventDefault();
  const question = elements.questionInput.value.trim();

  if (!question || !state.user || state.isSending) {
    return;
  }

  elements.emptyState.classList.add("is-hidden");
  const userMessage = createMessage("user", question);
  const loadingMessage = createMessage("assistant", "", { loading: true });
  elements.messageList.append(userMessage, loadingMessage);
  state.messages.push({ role: "user", text: question });
  elements.questionInput.value = "";
  resizeQuestionInput();
  setSending(true);
  const answerMode = state.answerMode;
  elements.chatContext.textContent = answerMode === "agent"
    ? "Agent đang xử lý yêu cầu"
    : "Đang tìm trong tài liệu";
  scrollToLatestMessage();

  let answer = "";
  let assistantMessage = null;
  let assistantBody = null;
  let renderFrame = null;

  try {
    await streamRetrieval(
      {
        user_id: state.user.user_id,
        chat_id: state.chatId,
        user_query: question,
      },
      (token) => {
        if (!token) {
          return;
        }

        answer += token;
        if (!assistantMessage) {
          assistantMessage = createMessage("assistant", "");
          assistantBody = assistantMessage.querySelector(".message-text");
          loadingMessage.replaceWith(assistantMessage);
        }

        if (!renderFrame) {
          renderFrame = window.requestAnimationFrame(() => {
            renderMarkdownInto(assistantBody, answer);
            renderFrame = null;
            scrollToLatestMessage();
          });
        }
      },
      answerMode,
    );

    if (renderFrame) {
      window.cancelAnimationFrame(renderFrame);
      renderFrame = null;
    }

    answer = answer || "Không tìm thấy câu trả lời phù hợp trong tài liệu.";
    if (!assistantMessage) {
      assistantMessage = createMessage("assistant", answer);
      loadingMessage.replaceWith(assistantMessage);
    } else {
      renderMarkdownInto(assistantBody, answer);
    }
    state.messages.push({ role: "assistant", text: answer });
    await loadChatHistory();
    elements.chatContext.textContent = answerMode === "agent"
      ? "Agent đã hoàn tất câu trả lời"
      : "Đã trả lời từ dữ liệu retrieval";
  } catch (error) {
    if (renderFrame) {
      window.cancelAnimationFrame(renderFrame);
      renderFrame = null;
    }

    if (assistantMessage) {
      const streamError = document.createElement("p");
      streamError.className = "stream-error";
      streamError.textContent = error.message;
      assistantMessage.querySelector(".message-content").append(streamError);
    } else {
      loadingMessage.replaceWith(createMessage("assistant", error.message, { error: true }));
    }
    elements.chatContext.textContent = "Không thể tạo câu trả lời";
  } finally {
    setSending(false);
    scrollToLatestMessage();
    elements.questionInput.focus();
  }
}

function resetConversation() {
  state.messages = [];
  elements.messageList.replaceChildren();
  elements.emptyState.classList.remove("is-hidden");
  elements.chatContext.textContent = state.documents.length
    ? `${state.documents.length} tài liệu đã tải lên`
    : "Sẵn sàng nhận câu hỏi";
  elements.questionInput.value = "";
  resizeQuestionInput();
}

function resizeQuestionInput() {
  elements.questionInput.style.height = "auto";
  elements.questionInput.style.height = `${Math.min(elements.questionInput.scrollHeight, 180)}px`;
}

function openSidebar() {
  elements.sidebar.classList.add("is-open");
  elements.sidebarScrim.classList.add("is-visible");
  elements.closeSidebar.focus();
}

function closeSidebar() {
  elements.sidebar.classList.remove("is-open");
  elements.sidebarScrim.classList.remove("is-visible");
}

elements.authTabs.forEach((tab) => {
  tab.addEventListener("click", () => setAuthMode(tab.dataset.authMode));
});

elements.authForm.addEventListener("submit", handleAuthSubmit);
elements.logoutButton.addEventListener("click", handleLogout);
elements.newChatButton.addEventListener("click", () => {
  state.chatId = createChatId();
  writeStorage(storageKeys.currentChat(state.user.user_id), state.chatId);
  state.documents = [];
  renderDocuments();
  renderChatHistory();
  resetConversation();
  closeSidebar();
  elements.questionInput.focus();
});
elements.fileInput.addEventListener("change", handleFileUpload);
elements.answerMode.addEventListener("change", () => {
  state.answerMode = elements.answerMode.value;
  configureAnswerMode();
});
elements.chatForm.addEventListener("submit", handleQuestionSubmit);
elements.questionInput.addEventListener("input", resizeQuestionInput);
elements.questionInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    elements.chatForm.requestSubmit();
  }
});
elements.suggestions.forEach((button) => {
  button.addEventListener("click", () => {
    elements.questionInput.value = button.dataset.prompt;
    resizeQuestionInput();
    elements.chatForm.requestSubmit();
  });
});
elements.openSidebar.addEventListener("click", openSidebar);
elements.closeSidebar.addEventListener("click", closeSidebar);
elements.sidebarScrim.addEventListener("click", closeSidebar);
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    closeSidebar();
  }
});

setAuthMode("login");
showApplication();
