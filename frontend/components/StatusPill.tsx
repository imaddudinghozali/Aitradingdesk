import { idText } from "@/lib/i18n";

type Tone = "ok" | "warn" | "err" | "info" | "muted";

const TONE_TO_CLASS: Record<Tone, string> = {
  ok: "pill-ok",
  warn: "pill-warn",
  err: "pill-err",
  info: "pill-info",
  muted: "pill-muted",
};

const OK_VALUES = new Set([
  "active",
  "Active",
  "Expansion Active",
  "Expansion Ready",
  "Shift Confirmed",
  "aligned",
  "Valid Setup",
  "valid_bullish",
  "valid_bearish",
  "ok",
  "completed",
  "running",
]);

const WARN_VALUES = new Set([
  "Weakening",
  "Shift Pending",
  "Forming",
  "Manipulation Phase",
  "partial",
  "waiting",
  "Waiting Confirmation",
  "Late Entry",
  "pre_news_accumulation",
  "post_news_repricing",
  "waiting_dol",
  "magneto_invalidated",
]);

const ERR_VALUES = new Set([
  "Invalidated",
  "Failure Risk",
  "Closed",
  "Closed / Late Entry",
  "No Trade",
  "conflict",
  "failed",
  "invalidated",
  "noise",
  "error",
  "provider_error",
]);

function classify(value: string): Tone {
  if (!value) return "muted";
  if (OK_VALUES.has(value)) return "ok";
  if (WARN_VALUES.has(value)) return "warn";
  if (ERR_VALUES.has(value)) return "err";
  if (value.toLowerCase().includes("aligned")) return "ok";
  if (value.toLowerCase().includes("no trade")) return "err";
  return "info";
}

export default function StatusPill({
  value,
  tone,
}: {
  value: string | null | undefined;
  tone?: Tone;
}) {
  const display = value ?? "—";
  const chosen = tone ?? classify(String(display));
  return <span className={TONE_TO_CLASS[chosen]}>{idText(display)}</span>;
}
