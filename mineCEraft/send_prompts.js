// send_prompts.js
// Send prompts to a Mindcraft agent and wait until the agent signals completion.
// Usage: node send_prompts.js
// Prerequisite: npm install socket.io-client

import { io } from "socket.io-client";

const SERVER = "http://localhost:8080";
const socket = io(SERVER, { transports: ["websocket", "polling"] });

const agentName = "andy"; // target agent name
const prompts = [
  "Build an arched bridge",
  "Build a simple house",
];

// Wait up to 10 minutes (ms) for completion keyword
const RESPONSE_TIMEOUT_MS = 10 * 60 * 1000; // 10 minutes

// Completion keywords (case-insensitive). We'll match whole words.
const COMPLETION_REGEX = /\b(complete)\b/i;

/**
 * Wait for a completion signal from the specified agent.
 * Resolves { ok: true, messages } when a message containing a completion keyword is seen.
 * Resolves { ok: false, reason } on timeout.
 */
function waitForCompletion(agent, timeoutMs = RESPONSE_TIMEOUT_MS) {
  return new Promise((resolve) => {
    const messages = [];
    let timeoutId = null;

    const handler = (fromAgent, message) => {
      if (fromAgent !== agent) return;
      const text = typeof message === "string" ? message : (message?.text ?? JSON.stringify(message));
      messages.push(text);
      console.log(`📨 [${fromAgent}] ${text}`);

      if (COMPLETION_REGEX.test(text)) {
        cleanup();
        resolve({ ok: true, messages });
      }
    };

    function cleanup() {
      socket.off("bot-output", handler);
      if (timeoutId) clearTimeout(timeoutId);
    }

    socket.on("bot-output", handler);

    timeoutId = setTimeout(() => {
      cleanup();
      resolve({ ok: false, reason: "timeout", messages });
    }, timeoutMs);
  });
}

socket.on("connect", async () => {
  console.log(`✅ Connected to MindServer at ${SERVER} (socket id=${socket.id})`);

  for (const p of prompts) {
    console.log(`\n➡️ Sending to ${agentName}: "${p}"`);
    socket.emit("send-message", agentName, { from: "ADMIN", message: p });

    console.log(`⏳ Waiting for completion keyword (timeout ${RESPONSE_TIMEOUT_MS / 60000} minutes)...`);
    const res = await waitForCompletion(agentName);

    if (res.ok) {
      console.log(`✅ Completion detected for "${p}". Collected messages:`);
      res.messages.forEach((m, i) => console.log(`  ${i + 1}. ${m}`));
    } else {
      console.log(`⚠️ Timeout waiting for completion of "${p}". Collected messages so far:`);
      res.messages.forEach((m, i) => console.log(`  ${i + 1}. ${m}`));
      // Decide policy: continue to next prompt or abort. Here we continue.
    }

    // small safe delay before next prompt
    await new Promise((r) => setTimeout(r, 500));
  }

  console.log("\n✅ All prompts processed. Disconnecting socket.");
  socket.disconnect();
  process.exit(0);
});

socket.on("connect_error", (err) => {
  console.error("❌ Socket connection error:", err && err.message ? err.message : err);
});
