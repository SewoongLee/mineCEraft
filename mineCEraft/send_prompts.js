// send_prompts.js
// Delete previous action files, then send prompts to the agent.

import { io } from "socket.io-client";
import fs from "fs";
import path from "path";

const SERVER = "http://localhost:8080";
const RESPONSE_TIMEOUT_MS = 10 * 60 * 1000;
const COMPLETION_KEYWORDS = ["complete", "finished", "done", "built", "I've laid", "accomplished"];

/**
 * Read agent name from settings.js by parsing the first profile.
 * Returns the agent name or null if not found.
 */
function getAgentNameFromSettings() {
  try {
    const settingsPath = path.join(process.cwd(), "..", "settings.js");
    if (!fs.existsSync(settingsPath)) {
      console.error(`⚠️ settings.js not found at ${settingsPath}`);
      return null;
    }

    // Read settings.js
    const settingsContent = fs.readFileSync(settingsPath, "utf8");
    
    // Extract first profile path using regex (more reliable than parsing JS)
    // Match: "profiles": [\n        "./builder.json",
    const profileMatch = settingsContent.match(/"profiles"\s*:\s*\[\s*"([^"]+)"/);
    if (!profileMatch || !profileMatch[1]) {
      console.error("⚠️ Could not find profiles array in settings.js");
      return null;
    }

    const firstProfilePath = profileMatch[1];
    const profileFullPath = path.join(process.cwd(), "..", firstProfilePath);
    
    if (!fs.existsSync(profileFullPath)) {
      console.error(`⚠️ Profile file not found: ${profileFullPath}`);
      return null;
    }

    // Read and parse profile JSON
    const profileContent = fs.readFileSync(profileFullPath, "utf8");
    const profile = JSON.parse(profileContent);
    
    if (!profile.name) {
      console.error(`⚠️ No 'name' field found in profile: ${firstProfilePath}`);
      return null;
    }

    return profile.name;
  } catch (error) {
    console.error(`⚠️ Error reading agent name from settings: ${error.message}`);
    return null;
  }
}

// Get agent name dynamically
const agentName = getAgentNameFromSettings() || "builder"; // fallback to "builder" if failed

if (!agentName) {
  console.error("❌ Failed to determine agent name. Exiting.");
  process.exit(1);
}

console.log(`ℹ️ Using agent name: ${agentName}`);

/** Return true if text contains any completion keyword (case-insensitive). */
function hasCompletionKeyword(text) {
  if (!text) return false;
  const lower = String(text).toLowerCase();
  return COMPLETION_KEYWORDS.some((kw) => lower.includes(kw));
}

/** Delete all files in bots/<agentName>/action-code. */
function clearActionCodeDir() {
  const dirPath = path.join(process.cwd(), "..", "bots", agentName, "action-code");
  if (!fs.existsSync(dirPath)) {
    console.log(`ℹ️ Directory not found: ${dirPath}`);
    return;
  }
  for (const file of fs.readdirSync(dirPath)) {
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
}

/**
 * Find the highest-numbered *.js file under bots/<agentName>/action-code
 * and print a single machine-readable line with a sentinel prefix.
 * Format: ::ACTION_MAX_JS::<json>
 */
function reportMaxActionFile() {
  const dirPath = path.join(process.cwd(), "..", "bots", agentName, "action-code");
  if (!fs.existsSync(dirPath)) {
    console.log(`::ACTION_MAX_JS::${JSON.stringify({ ok: false, reason: "dir-not-found", dirPath })}`);
    return;
  }

  const re = /^(\d+)\.js$/; // matches "123.js"
  let maxIndex = -1;
  let maxName = null;

  for (const name of fs.readdirSync(dirPath)) {
    const m = name.match(re);
    if (!m) continue;
    const n = Number(m[1]);
    if (Number.isFinite(n) && n > maxIndex) {
      maxIndex = n;
      maxName = name;
    }
  }

  if (maxIndex < 0) {
    console.log(`::ACTION_MAX_JS::${JSON.stringify({ ok: false, reason: "no-js-files", dirPath })}`);
    return;
  }

  const fullPath = path.join(dirPath, maxName);
  console.log(
    `::ACTION_MAX_JS::${JSON.stringify({
      ok: true,
      index: maxIndex,
      name: maxName,
      path: fullPath,
    })}`
  );
}

/** Wait for completion message from the agent. */
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

// === Main ===
clearActionCodeDir();

const socket = io(SERVER, { transports: ["websocket", "polling"] });

socket.on("connect", async () => {
  console.log(`✅ Connected to MindServer at ${SERVER} (socket id=${socket.id})`);

  // Read prompts once from stdin (expects {"prompts":[...]})
  const prompts = await (async function getPromptsFromStdin() {
    const stdin = await new Promise((resolve) => {
      const { stdin } = process;
      if (stdin.isTTY) return resolve("");
      let data = "";
      stdin.setEncoding("utf8");
      stdin.on("data", (chunk) => (data += chunk));
      stdin.on("end", () => resolve(data.trim()));
      setTimeout(() => resolve(data.trim()), 100); // safety timeout
    });
    if (!stdin) return [];
    try {
      const j = JSON.parse(stdin);
      return Array.isArray(j) ? j : j.prompts;
    } catch {
      return [];
    }
  })();

  if (!prompts.length) {
    console.log("ℹ️ No prompts provided. Exiting.");
    socket.disconnect();
    process.exit(0);
  }

  for (const p of prompts) {
    console.log(`\n➡️ Sending to ${agentName}: "${p}"`);
    socket.emit("send-message", agentName, { from: "ADMIN", message: p });

    console.log(
      `⏳ Waiting for completion keyword (timeout ${Math.round(RESPONSE_TIMEOUT_MS / 60000)} min)...`
    );
    const res = await waitForCompletion(agentName);

    if (res.ok) {
      console.log(`✅ Completion detected for "${p}".`);
      reportMaxActionFile(); // ← print the current max file
    } else {
      console.log(`⚠️ Timeout waiting for completion of "${p}".`);
      reportMaxActionFile(); // even on timeout, report what's there
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
