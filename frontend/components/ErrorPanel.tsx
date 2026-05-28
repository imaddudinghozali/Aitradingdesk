import { idText } from "@/lib/i18n";

export default function ErrorPanel({
  message,
  hint,
}: {
  message: string;
  hint?: string;
}) {
  return (
    <div className="rounded border border-shadow-err/40 bg-shadow-err/10 p-4 text-sm text-shadow-err">
      <div className="font-medium">Backend tidak terjangkau atau mengembalikan error</div>
      <div className="mt-1 font-mono text-xs">{idText(message)}</div>
      {hint && <div className="mt-2 text-xs text-shadow-muted">{idText(hint)}</div>}
    </div>
  );
}
