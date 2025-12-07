import InterruptHandler from "./interruptHandler.mjs";
import {
  IGNORE_LIST,
  INTERRUPT_LIST,
  STT_VALIDATION_BUFFER_MS
} from "./config.mjs";

let agentSpeaking = false;

function isAgentSpeaking() {
  return agentSpeaking;
}

function handleInterrupt({ text, reason }) {
  console.log("\n?? INTERRUPT TRIGGERED ??");
  console.log("Reason:", reason);
  console.log("Text:", text);
}

function handleAcceptedAsUser({ text }) {
  console.log("\n?? ACCEPTED AS USER INPUT");
  console.log("User said:", text);
}

const handler = new InterruptHandler({
  isSpeakingFn: isAgentSpeaking,
  onInterrupt: handleInterrupt,
  onAcceptedAsUser: handleAcceptedAsUser
});

console.log("Ignore List:", IGNORE_LIST);
console.log("Interrupt List:", INTERRUPT_LIST);
console.log("STT Buffer:", STT_VALIDATION_BUFFER_MS, "ms");

export function agentStartSpeaking() {
  agentSpeaking = true;
  console.log("\n?? Agent started speaking...");
}

export function agentStopSpeaking() {
  agentSpeaking = false;
  console.log("\n?? Agent stopped speaking.");
}

export function onVADEvent() {
  console.log("\n[VAD Triggered]");
  handler.onVADTrigger();
}

export function onSTTPartial(text) {
  console.log("[STT Partial]:", text);
  handler.onSTTPartial(text);
}

export function onSTTFinal(text) {
  console.log("[STT Final]:", text);
  handler.onSTTFinal(text);
}

(async function runDemo() {
  agentStartSpeaking();

  onVADEvent();
  setTimeout(() => onSTTPartial("yeah"), 30);
  setTimeout(() => onSTTFinal("yeah"), 60);

  setTimeout(() => {
    onVADEvent();
    setTimeout(() => onSTTPartial("no stop"), 20);
    setTimeout(() => onSTTFinal("no stop"), 50);
  }, 500);

  setTimeout(() => agentStopSpeaking(), 700);

  setTimeout(() => {
    onVADEvent();
    setTimeout(() => onSTTFinal("yeah"), 30);
  }, 900);
})();