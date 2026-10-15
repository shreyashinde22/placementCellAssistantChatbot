(() => {
  const form = document.querySelector("#chat-form");
  const input = document.querySelector("#message-input");
  const sendButton = document.querySelector("#send-button");
  const messageList = document.querySelector("#message-list");
  const welcome = document.querySelector("#welcome");
  const errorBanner = document.querySelector("#error-banner");
  const errorMessage = document.querySelector("#error-message");
  const retryButton = document.querySelector("#retry-button");
  const newChatButton = document.querySelector("#new-chat-button");
  const suggestions = document.querySelector("#suggestions");

  if (
    !form || !input || !sendButton || !messageList || !welcome ||
    !errorBanner || !errorMessage || !retryButton || !newChatButton || !suggestions
  ) {
    return;
  }

  const history = [];
  let pendingMessage = null;
  let loading = false;
  let loadingElement = null;

  function addMessage(role, content, sources = []) {
    const row = document.createElement("article");
    row.className = `message ${role}`;
    row.setAttribute("aria-label", role === "user" ? "Your message" : "Assistant response");

    const avatar = document.createElement("span");
    avatar.className = "avatar";
    avatar.setAttribute("aria-hidden", "true");
    avatar.textContent = role === "user" ? "Y" : "A";

    const bubble = document.createElement("div");
    bubble.className = "message-content";
    const text = document.createElement("p");
    text.className = "message-text";
    text.textContent = content;
    bubble.append(text);

    if (role === "assistant" && Array.isArray(sources) && sources.length > 0) {
      const sourceSection = document.createElement("section");
      sourceSection.className = "sources";
      const heading = document.createElement("h3");
      heading.textContent = "Sources";
      const list = document.createElement("ul");
      sources.forEach((source) => {
        if (typeof source !== "string") return;
        const item = document.createElement("li");
        item.textContent = source;
        list.append(item);
      });
      if (list.childElementCount > 0) {
        sourceSection.append(heading, list);
        bubble.append(sourceSection);
      }
    }

    row.append(avatar, bubble);
    messageList.append(row);
    row.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  function setLoading(isLoading) {
    loading = isLoading;
    input.disabled = isLoading;
    sendButton.disabled = isLoading;
    newChatButton.disabled = isLoading;
    suggestions.querySelectorAll("button").forEach((button) => {
      button.disabled = isLoading;
    });
    sendButton.setAttribute("aria-label", isLoading ? "Sending message" : "Send message");

    if (isLoading) {
      loadingElement = document.createElement("div");
      loadingElement.className = "message assistant";
      loadingElement.setAttribute("role", "status");
      loadingElement.setAttribute("aria-live", "polite");
      const indicator = document.createElement("span");
      indicator.className = "loading-indicator";
      const spinner = document.createElement("span");
      spinner.className = "spinner";
      spinner.setAttribute("aria-hidden", "true");
      const label = document.createElement("span");
      label.textContent = "Finding a helpful answer…";
      indicator.append(spinner, label);
      loadingElement.append(indicator);
      messageList.append(loadingElement);
      loadingElement.scrollIntoView({ behavior: "smooth", block: "nearest" });
    } else if (loadingElement) {
      loadingElement.remove();
      loadingElement = null;
    }
  }

  function showError(message) {
    errorMessage.textContent = message;
    errorBanner.hidden = false;
  }

  async function sendPendingMessage() {
    if (!pendingMessage || loading) return;
    const message = pendingMessage;
    errorBanner.hidden = true;
    setLoading(true);

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: message.content,
          conversation: message.history,
        }),
      });
      let payload;
      try {
        payload = await response.json();
      } catch {
        throw new Error("The server returned an unreadable response. Please retry.");
      }
      if (!response.ok) {
        throw new Error(
          typeof payload.error === "string"
            ? payload.error
            : "The message could not be sent. Please retry."
        );
      }
      if (typeof payload.answer !== "string") {
        throw new Error("The server response was incomplete. Please retry.");
      }

      addMessage("assistant", payload.answer, payload.sources);
      history.push(
        { role: "user", content: message.content },
        { role: "assistant", content: payload.answer }
      );
      if (history.length > 6) history.splice(0, history.length - 6);
      pendingMessage = null;
    } catch (error) {
      showError(error instanceof Error ? error.message : "Something went wrong. Please retry.");
    } finally {
      setLoading(false);
    }
  }

  function startMessage(rawMessage) {
    const content = rawMessage.trim();
    if (!content || loading) return;
    welcome.hidden = true;
    addMessage("user", content);
    pendingMessage = {
      content,
      history: history.slice(-6).map(({ role, content: itemContent }) => ({
        role,
        content: itemContent,
      })),
    };
    input.value = "";
    input.style.height = "";
    sendPendingMessage();
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    startMessage(input.value);
  });

  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      form.requestSubmit();
    }
  });

  input.addEventListener("input", () => {
    input.style.height = "auto";
    input.style.height = `${Math.min(input.scrollHeight, 160)}px`;
  });

  retryButton.addEventListener("click", sendPendingMessage);
  newChatButton.addEventListener("click", () => {
    if (loading) return;
    history.length = 0;
    pendingMessage = null;
    messageList.replaceChildren();
    errorBanner.hidden = true;
    welcome.hidden = false;
    input.value = "";
    input.focus();
  });

  suggestions.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-prompt]");
    if (button && suggestions.contains(button) && !loading) {
      startMessage(button.dataset.prompt || "");
    }
  });
})();
