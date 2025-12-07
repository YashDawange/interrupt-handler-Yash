import dotenv from "dotenv";
dotenv.config();

export const IGNORE_LIST = (process.env.IGNORE_LIST || "yeah,ok,hmm,right,uh-huh,uhhuh")
  .split(",")
  .map(s => s.trim().toLowerCase())
  .filter(Boolean);

export const INTERRUPT_LIST = (process.env.INTERRUPT_LIST || "stop,wait,hold,interrupt,no")
  .split(",")
  .map(s => s.trim().toLowerCase())
  .filter(Boolean);

export const STT_VALIDATION_BUFFER_MS = Number(
  process.env.STT_VALIDATION_BUFFER_MS || 120
);

export default {
  IGNORE_LIST,
  INTERRUPT_LIST,
  STT_VALIDATION_BUFFER_MS
};