// send_prompts.js
// Bridge script: reads a prompt list from stdin, sends them to the builder agent via
// MindServer, and for each turn reports the latest action file (::ACTION_MAX_JS::) to stdout
// so Python can record eval data.

import { io } from "socket.io-client";
import fs from "fs";
import path from "path";

// --- Constants ---

const SERVER = "http://localhost:8080";
const RESPONSE_TIMEOUT_MS = 10 * 60 * 1000; // max wait per turn for completion keyword
const COMPLETION_KEYWORDS = [
  "complete", "finished", "done", "successfully", "built",
  "i've laid", "i've installed", "as requested", "is there anything else",
];
const TURN_DELAY_MS = 500;
const ACTION_FILE_POLL_MS = 200;
const STDIN_READ_TIMEOUT_MS = 100;
const PARENT_WATCH_INTERVAL_MS = 2000;
const COMMAND_COMPLETION_TIMEOUT_MS = 5000; // clearChat etc.
const SENTINEL = "::ACTION_MAX_JS::";

// When stdout is piped to Python, Node uses block buffering so lines can stay buffered and
// Python blocks on "next line" while Node has already written it. Force line-at-a-time delivery.
if (!process.stdout.isTTY && process.stdout._handle?.setBlocking) {
  process.stdout._handle.setBlocking(true);
}

// --- Agent name (from settings) ---

/**
 * Resolve agent name by reading the first profile from parent settings.js.
 * Used to know which bot to talk to and where action-code lives.
 * @returns {string | null} Profile name or null on any failure.
 */
function getAgentNameFromSettings() {
  try {
    const settingsPath = path.join(process.cwd(), "..", "settings.js");
    if (!fs.existsSync(settingsPath)) {
      console.error(`⚠️ settings.js not found at ${settingsPath}`);
      return null;
    }
    const settingsContent = fs.readFileSync(settingsPath, "utf8");
    const profileMatch = settingsContent.match(/"profiles"\s*:\s*\[\s*"([^"]+)"/);
    if (!profileMatch?.[1]) {
      console.error("⚠️ Could not find profiles array in settings.js");
      return null;
    }
    const profileFullPath = path.join(process.cwd(), "..", profileMatch[1]);
    if (!fs.existsSync(profileFullPath)) {
      console.error(`⚠️ Profile file not found: ${profileFullPath}`);
      return null;
    }
    const profile = JSON.parse(fs.readFileSync(profileFullPath, "utf8"));
    if (!profile.name) {
      console.error(`⚠️ No 'name' field in profile: ${profileMatch[1]}`);
      return null;
    }
    return profile.name;
  } catch (error) {
    console.error(`⚠️ Error reading agent name: ${error.message}`);
    return null;
  }
}

const agentName = getAgentNameFromSettings() || "builder";
if (!agentName) {
  console.error("❌ Failed to determine agent name. Exiting.");
  process.exit(1);
}
console.log(`ℹ️ Using agent name: ${agentName}`);

// --- Action-code directory (single source of path) ---

/** Path to bots/<agentName>/action-code where numbered .js action files are written. */
function getActionCodeDir() {
  return path.join(process.cwd(), "..", "bots", agentName, "action-code");
}

// --- Helpers ---

const delay = (ms) => new Promise((r) => setTimeout(r, ms));

/** Write one machine-readable line for Python (sentinel + JSON). */
function emitSentinel(obj) {
  console.log(`${SENTINEL}${JSON.stringify(obj)}`);
}

// --- Action-code: clear, scan, wait ---

const ACTION_CODE_RE = /^(\d+)\.js$/;

/**
 * Remove all files and subdirs under action-code so each run starts clean.
 * Called once at script startup.
 */
function clearActionCodeDir() {
  const dirPath = getActionCodeDir();
  if (!fs.existsSync(dirPath)) {
    console.log(`ℹ️ Directory not found: ${dirPath}`);
    return;
  }
  for (const name of fs.readdirSync(dirPath)) {
    const fullPath = path.join(dirPath, name);
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
 * Scan action-code dir for numeric .js files and return the one with highest index.
 * @param {string} dirPath - Action-code directory path.
 * @returns {{ index: number, name: string } | null} Max file info, or null if none.
 */
function getMaxActionFile(dirPath) {
  if (!fs.existsSync(dirPath)) return null;
  let maxIndex = -1;
  let maxName = null;
  try {
    for (const name of fs.readdirSync(dirPath)) {
      const m = name.match(ACTION_CODE_RE);
      if (!m) continue;
      const n = Number(m[1]);
      if (Number.isFinite(n) && n > maxIndex) {
        maxIndex = n;
        maxName = name;
      }
    }
  } catch {
    return null;
  }
  return maxIndex >= 0 ? { index: maxIndex, name: maxName } : null;
}

/** Current max action index in dir, or -1 if no numeric .js files. */
function getMaxActionIndex(dirPath) {
  const info = getMaxActionFile(dirPath);
  return info ? info.index : -1;
}

/**
 * Poll until a new action file appears with index > afterIndex, or timeout.
 * Used so we report this turn's file, not a previous one.
 * @param {number} afterIndex - Ignore files with index <= this (-1 means any file).
 */
function waitForNewActionFile(dirPath, afterIndex, timeoutMs, pollIntervalMs = ACTION_FILE_POLL_MS) {
  return new Promise((resolve) => {
    const deadline = Date.now() + timeoutMs;
    const tick = () => {
      const current = getMaxActionIndex(dirPath);
      if (current > afterIndex) return resolve(true);
      if (Date.now() >= deadline) return resolve(false);
      setTimeout(tick, pollIntervalMs);
    };
    tick();
  });
}

/**
 * Report the highest-numbered action .js file to stdout as ::ACTION_MAX_JS::<json>.
 * Optionally waits for a new file (index > afterIndex) before scanning.
 * @param {{ waitForFileMs?: number, afterIndex?: number }} [options]
 */
async function reportMaxActionFile(options = {}) {
  const dirPath = getActionCodeDir();
  const waitMs = options.waitForFileMs ?? 0;
  const afterIndex = options.afterIndex ?? -1;

  if (waitMs > 0) {
    const found = await waitForNewActionFile(dirPath, afterIndex, waitMs);
    if (!found) {
      emitSentinel({ ok: false, reason: "no-js-files-after-wait", dirPath });
      return;
    }
  }

  const info = getMaxActionFile(dirPath);
  if (!info) {
    const reason = fs.existsSync(dirPath) ? "no-js-files" : "dir-not-found";
    emitSentinel({ ok: false, reason, dirPath });
    return;
  }

  emitSentinel({
    ok: true,
    index: info.index,
    name: info.name,
    path: path.join(dirPath, info.name),
  });
}

// --- Socket: wait for bot messages ---

/** True if text contains any completion keyword (case-insensitive). */
function hasCompletionKeyword(text) {
  if (!text) return false;
  const lower = String(text).toLowerCase();
  return COMPLETION_KEYWORDS.some((kw) => lower.includes(kw));
}

/**
 * Wait for one bot-output event that satisfies predicate(text), or until timeout.
 * Logs each message; on match or timeout, unsubscribes and resolves.
 * @param {string} agent - Agent name to filter by.
 * @param {{ predicate: (text: string) => boolean, timeoutMs: number }} options
 * @returns {Promise<{ ok: boolean, messages: string[] }>}
 */
function waitForBotOutput(agent, { predicate, timeoutMs }) {
  return new Promise((resolve) => {
    const messages = [];
    let timeoutId = null;

    const handler = (fromAgent, message) => {
      if (fromAgent !== agent) return;
      const text = typeof message === "string" ? message : message?.text ?? JSON.stringify(message);
      messages.push(text);
      console.log(`📨 [${fromAgent}] ${text}`);
      if (predicate(text)) {
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

const waitForCompletion = (agent, timeoutMs = RESPONSE_TIMEOUT_MS) =>
  waitForBotOutput(agent, { predicate: hasCompletionKeyword, timeoutMs });

const waitForCommandCompletion = (agent, timeoutMs = COMMAND_COMPLETION_TIMEOUT_MS) =>
  waitForBotOutput(agent, {
    predicate: (text) => text.includes("chat history was cleared") || text.includes("cleared"),
    timeoutMs,
  });

const waitForFirstResponse = (agent, timeoutMs = 60000) =>
  waitForBotOutput(agent, { predicate: () => true, timeoutMs });

// --- Parent process watchdog ---

/**
 * Return true if process pid is still running (Unix/Windows: signal 0 checks existence).
 */
function isProcessAlive(pid) {
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
}

/**
 * Start a periodic check; when the parent process (e.g. Python notebook kernel) dies,
 * disconnect socket and exit so this process does not stay alive as an orphan.
 * @param {number} parentPid - PID of the parent process.
 * @returns {() => void} Callback to stop the watchdog (e.g. on normal exit).
 */
function startParentWatchdog(parentPid) {
  const id = setInterval(() => {
    if (!isProcessAlive(parentPid)) {
      clearInterval(id);
      console.error("⚠️ Parent process gone, exiting.");
      socket.disconnect();
      process.exit(0);
    }
  }, PARENT_WATCH_INTERVAL_MS);
  return () => clearInterval(id);
}

// --- Stdin payload parsing ---

/**
 * Read one line from stdin and parse as JSON payload.
 * Supports: { prompts, run_lengths, clear_between, inter_prompt_command, inter_prompt_response_timeout_ms, action_file_wait_ms, parent_pid }
 * or legacy array (treated as prompts with run_lengths [1,1,...]).
 * parent_pid: if set, this process will exit when that PID disappears (avoids orphan on kernel death).
 * On empty stdin or parse error, returns defaults (and logs on parse error).
 */
async function parseStdinPayload() {
  const defaults = {
    prompts: [],
    run_lengths: [],
    clear_between: false,
    inter_prompt_command: null,
    inter_prompt_response_timeout_ms: 60000,
    action_file_wait_ms: 10000,
  };

  const stdin = await new Promise((resolve) => {
    const { stdin: inStream } = process;
    if (inStream.isTTY) return resolve("");
    let data = "";
    inStream.setEncoding("utf8");
    inStream.on("data", (chunk) => (data += chunk));
    inStream.on("end", () => resolve(data.trim()));
    setTimeout(() => resolve(data.trim()), STDIN_READ_TIMEOUT_MS);
  });

  if (!stdin) return { ...defaults };

  try {
    const j = JSON.parse(stdin);
    if (Array.isArray(j)) {
      return { ...defaults, prompts: j, run_lengths: j.map(() => 1) };
    }
    const prompts = j.prompts || [];
    const run_lengths = j.run_lengths?.length > 0 ? j.run_lengths : prompts.map(() => 1);
    return {
      ...defaults,
      prompts,
      run_lengths,
      clear_between: j.clear_between === true,
      inter_prompt_command: j.inter_prompt_command ?? null,
      inter_prompt_response_timeout_ms: j.inter_prompt_response_timeout_ms ?? defaults.inter_prompt_response_timeout_ms,
      action_file_wait_ms: j.action_file_wait_ms ?? defaults.action_file_wait_ms,
      parent_pid: typeof j.parent_pid === "number" ? j.parent_pid : undefined,
    };
  } catch (e) {
    console.error("⚠️ stdin parse failed, using defaults:", e?.message ?? e);
    return { ...defaults };
  }
}

// --- Main ---

clearActionCodeDir();

const socket = io(SERVER, { transports: ["websocket", "polling"] });

socket.on("connect", async () => {
  console.log(`✅ Connected to MindServer at ${SERVER} (socket id=${socket.id})`);

  const opts = await parseStdinPayload();
  if (!opts.prompts.length) {
    console.log("ℹ️ No prompts provided. Exiting.");
    socket.disconnect();
    process.exit(0);
  }

  const stopParentWatchdog = opts.parent_pid != null ? startParentWatchdog(opts.parent_pid) : () => {};

  const actionCodeDir = getActionCodeDir();
  let globalIndex = 0;

  // Outer loop: one run per entry in run_lengths (run = sequence of turns, chat cleared between runs).
  for (let runIdx = 0; runIdx < opts.run_lengths.length; runIdx++) {
    const runLen = opts.run_lengths[runIdx] || 0;
    if (runLen <= 0) continue;

    // Between runs: optional inter-prompt command, then optional clearChat.
    if (globalIndex > 0) {
      if (opts.inter_prompt_command) {
        console.log(`\n🔄 Sending inter-prompt command (not evaluated): "${opts.inter_prompt_command}"`);
        socket.emit("send-message", agentName, { from: "ADMIN", message: opts.inter_prompt_command });
        console.log(`⏳ Waiting for first LLM response (timeout ${Math.round(opts.inter_prompt_response_timeout_ms / 1000)}s)...`);
        const res = await waitForFirstResponse(agentName, opts.inter_prompt_response_timeout_ms);
        console.log(res.ok ? "✅ Inter-prompt response received." : "⚠️ Inter-prompt response timeout, proceeding anyway...");
      }
      if (opts.clear_between) {
        console.log(`\n🧹 Clearing history before run ${runIdx + 1}/${opts.run_lengths.length}...`);
        socket.emit("send-message", agentName, { from: "ADMIN", message: "!clearChat" });
        const clearRes = await waitForCommandCompletion(agentName);
        console.log(clearRes.ok ? "✅ History cleared." : "⚠️ ClearChat timeout, proceeding anyway...");
        await delay(TURN_DELAY_MS);
      }
    }

    // Inner loop: one turn per prompt in this run.
    for (let turnInRun = 0; turnInRun < runLen; turnInRun++) {
      const prompt = opts.prompts[globalIndex];
      globalIndex++;

      const maxIndexBeforeTurn = getMaxActionIndex(actionCodeDir);

      console.log(`\n➡️ Sending to ${agentName} (run ${runIdx + 1}, turn ${turnInRun + 1}/${runLen}): "${prompt}"`);
      socket.emit("send-message", agentName, { from: "ADMIN", message: prompt });

      console.log(`⏳ Waiting for completion keyword (timeout ${Math.round(RESPONSE_TIMEOUT_MS / 60000)} min)...`);
      const res = await waitForCompletion(agentName);
      console.log(res.ok ? `✅ Completion detected for "${prompt}".` : `⚠️ Timeout waiting for completion of "${prompt}".`);
      await reportMaxActionFile({ waitForFileMs: opts.action_file_wait_ms, afterIndex: maxIndexBeforeTurn });
      await delay(TURN_DELAY_MS);
    }
  }

  stopParentWatchdog();
  console.log("\n✅ All prompts processed. Disconnecting socket.");
  socket.disconnect();
  process.exit(0);
});

socket.on("connect_error", (err) => {
  console.error("❌ Socket connection error:", err?.message ?? err);
});
