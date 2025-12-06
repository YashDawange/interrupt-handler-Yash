import { IGNORE_LIST, INTERRUPT_LIST, STT_VALIDATION_BUFFER_MS } from "./config.mjs";

export class InterruptHandler {
  constructor({ isSpeakingFn, onInterrupt, onAcceptedAsUser }) {
    if (typeof isSpeakingFn !== "function") {
      throw new Error("isSpeakingFn is required");
    }

    this.isSpeakingFn = isSpeakingFn;
    this.onInterrupt = typeof onInterrupt === "function" ? onInterrupt : () => {};
    this.onAcceptedAsUser =
      typeof onAcceptedAsUser === "function" ? onAcceptedAsUser : () => {};

    this._pending = null;
  }

  onVADTrigger() {
    if (this._pending) return;

    const speakingAtVAD = this.isSpeakingFn();

    this._pending = {
      speakingAtVAD,
      timer: setTimeout(() => {
        this._fallbackOnNoSTT(speakingAtVAD);
        this._clearPending();
      }, STT_VALIDATION_BUFFER_MS)
    };
  }

  async onSTTPartial(text) {
    if (!this._pending) return this._handleSTT(text, false);
    return this._handleSTT(text, true);
  }

  async onSTTFinal(text) {
    if (this._pending) {
      await this._handleSTT(text, true);
      this._clearPending();
      return;
    }
    return this._handleSTT(text, false);
  }

  _handleSTT(text, wasPending) {
    const normalized = (text || "").trim().toLowerCase();
    const words = normalized.split(/\s+/).filter(Boolean);

    const containsInterrupt = words.some((w) => INTERRUPT_LIST.includes(w));
    const containsIgnoreOnly =
      words.length > 0 && words.every((w) => IGNORE_LIST.includes(w));

    const speaking = this.isSpeakingFn();

    if (containsInterrupt) {
      this.onInterrupt({ text, reason: "contains_interrupt" });
      return { action: "interrupt" };
    }

    if (speaking && containsIgnoreOnly) {
      return { action: "swallow" };
    }

    if (speaking && !containsIgnoreOnly) {
      this.onInterrupt({ text, reason: "spoken_during_speech_nonignore" });
      return { action: "interrupt" };
    }

    if (!speaking) {
      this.onAcceptedAsUser({ text });
      return { action: "accept" };
    }

    return { action: "noop" };
  }

  _fallbackOnNoSTT(speakingAtVAD) {
    if (speakingAtVAD) return { action: "swallow" };
    this.onAcceptedAsUser({ text: "" });
    return { action: "accept_no_stt" };
  }

  _clearPending() {
    if (!this._pending) return;
    clearTimeout(this._pending.timer);
    this._pending = null;
  }
}

export default InterruptHandler;