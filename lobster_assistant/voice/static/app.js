const messages = document.querySelector("#messages");
const form = document.querySelector("#composer");
const input = document.querySelector("#text");
const talk = document.querySelector("#talk");
const statusEl = document.querySelector("#status");

function addMessage(role, text) {
  const bubble = document.createElement("div");
  bubble.className = `bubble ${role}`;
  bubble.textContent = text;
  messages.appendChild(bubble);
  messages.scrollTop = messages.scrollHeight;
}

async function sendText(text) {
  addMessage("user", text);
  statusEl.textContent = "Thinking";
  const response = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, user: "phone" }),
  });
  const payload = await response.json();
  if (!response.ok || payload.error) {
    throw new Error(payload.error || "Assistant request failed");
  }
  addMessage("assistant", payload.reply);
  speak(payload.reply);
  statusEl.textContent = "Awake";
}

function speak(text) {
  if (!("speechSynthesis" in window)) return;
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.rate = 1;
  utterance.pitch = 0.95;
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(utterance);
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const text = input.value.trim();
  if (!text) return;
  input.value = "";
  try {
    await sendText(text);
  } catch (error) {
    statusEl.textContent = "Error";
    addMessage("assistant", String(error.message || error));
  }
});

talk.addEventListener("click", () => {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    addMessage("assistant", "Speech recognition is not available in this browser. Type to me here, or configure a local STT command.");
    return;
  }
  const recognition = new SpeechRecognition();
  recognition.lang = navigator.language || "en-US";
  recognition.interimResults = false;
  recognition.maxAlternatives = 1;
  statusEl.textContent = "Listening";
  recognition.onresult = async (event) => {
    const text = event.results[0][0].transcript;
    try {
      await sendText(text);
    } catch (error) {
      statusEl.textContent = "Error";
      addMessage("assistant", String(error.message || error));
    }
  };
  recognition.onerror = () => {
    statusEl.textContent = "Awake";
  };
  recognition.onend = () => {
    if (statusEl.textContent === "Listening") statusEl.textContent = "Awake";
  };
  recognition.start();
});

addMessage("assistant", "Claws online. Message me here or tap Mic.");
