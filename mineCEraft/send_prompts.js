// send_prompts.js
// Delete previous action files, then send prompts to the agent.

import { io } from "socket.io-client";
import fs from "fs";
import path from "path";

const SERVER = "http://localhost:8080";
const socket = io(SERVER, { transports: ["websocket", "polling"] });

const agentName = "andy";
const prompts = [
  "Lay the foundation for a 15x20 block rectangular building.",
  "Build an arched bridge.",
  "Build a simple house.",
];

const RESPONSE_TIMEOUT_MS = 20 * 60 * 1000; // 20 minutes

const COMPLETION_KEYWORDS = [
  "complete!",
  "completed",
  "finished",
  "done",
  "built",
];

// ✅ ① Delete all files in bots/andy/action-code
function clearActionCodeDir() {
  // go up one level first, then into bots/andy/action-code
  const dirPath = path.join(process.cwd(), "..", "bots", agentName, "action-code");

  if (fs.existsSync(dirPath)) {
    const files = fs.readdirSync(dirPath);
    for (const file of files) {
      const fullPath = path.join(dirPath, file);
      try {
        const stat = fs.statSync(fullPath);
        if (stat.isFile()) fs.unlinkSync(fullPath);
        else if (stat.isDirectory()) fs.rmSync(fullPath, { recursive: true, force: true });
      } catch (err) {
        console.error("⚠️ Failed to delete:", fullPath, err.message);
      }
    }
    console.log(`🧹 Cleared all files under ${dirPath}`);
  } else {
    console.log(`ℹ️ Directory not found: ${dirPath}`);
  }
}

// ✅ ② Run cleanup before connecting to MindServer
clearActionCodeDir();

/** Return true if message text contains any completion keyword (case-insensitive). */
function hasCompletionKeyword(text) {
  if (!text) return false;
  const lower = String(text).toLowerCase();
  return COMPLETION_KEYWORDS.some((kw) => lower.includes(kw));
}

/**
 * Wait for completion message from agent
 */
function waitForCompletion(agent, timeoutMs = RESPONSE_TIMEOUT_MS) {
  return new Promise((resolve) => {
    const messages = [];
    let timeoutId = null;

    const handler = (fromAgent, message) => {
      if (fromAgent !== agent) return;
      const text =
        typeof message === "string" ? message : message?.text ?? JSON.stringify(message);
      messages.push(text);
      console.log(`📨 [${fromAgent}] ${text}`);

      if (hasCompletionKeyword(text)) {
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

    console.log(
      `⏳ Waiting for completion keyword (timeout ${Math.round(RESPONSE_TIMEOUT_MS / 60000)} min)...`
    );
    const res = await waitForCompletion(agentName);

    if (res.ok) {
      console.log(`✅ Completion detected for "${p}".`);
    } else {
      console.log(`⚠️ Timeout waiting for completion of "${p}".`);
    }

    await new Promise((r) => setTimeout(r, 500));
  }

  console.log("\n✅ All prompts processed. Disconnecting socket.");
  socket.disconnect();
  process.exit(0);
});

socket.on("connect_error", (err) => {
  console.error("❌ Socket connection error:", err?.message ?? err);
});
