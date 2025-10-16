import { io } from "socket.io-client";

const socket = io("http://localhost:8080");

const agentName = "andy"; 
const prompts = [
  "build an arched bridge.",
];

socket.on("connect", async () => {
  console.log("Connected to MindServer");

  for (const p of prompts) {
    socket.emit("send-message", agentName, { from: "ADMIN", message: p });
    console.log("Sent:", p);
    await new Promise((r) => setTimeout(r, 1000));
  }

  setTimeout(() => {
    console.log("Done sending prompts. Disconnecting...");
    socket.disconnect();
  }, 2000);
});

socket.on("connect_error", (err) => {
  console.error("Connection error:", err.message);
});
