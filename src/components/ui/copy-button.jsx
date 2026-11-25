import * as React from "react";
import { Copy, Check } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

/**
 * Small, reusable copy-to-clipboard control.
 * Usage: <CopyButton value={ticketNumber} label="ticket number" />
 * Works over HTTPS (navigator.clipboard) with an execCommand fallback.
 */
export function CopyButton({ value, label, className, size = 14, showToast = true, stopPropagation = true }) {
  const [copied, setCopied] = React.useState(false);

  const handleCopy = async (e) => {
    if (stopPropagation) {
      e?.preventDefault?.();
      e?.stopPropagation?.();
    }
    const text = String(value ?? "").trim();
    if (!text) return;
    let ok = false;
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text);
        ok = true;
      } else {
        const ta = document.createElement("textarea");
        ta.value = text;
        ta.style.position = "fixed";
        ta.style.opacity = "0";
        document.body.appendChild(ta);
        ta.select();
        ok = document.execCommand("copy");
        document.body.removeChild(ta);
      }
    } catch (err) {
      ok = false;
    }
    if (ok) {
      setCopied(true);
      if (showToast) toast.success(`Copied${label ? ` ${label}` : ""}`);
      setTimeout(() => setCopied(false), 1500);
    } else if (showToast) {
      toast.error("Couldn't copy to clipboard");
    }
  };

  const aria = `Copy${label ? ` ${label}` : ""}`;
  return (
    <button
      type="button"
      onClick={handleCopy}
      aria-label={aria}
      title={aria}
      className={cn(
        "inline-flex items-center justify-center rounded-md p-1 align-middle text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
        className
      )}
    >
      {copied ? <Check size={size} className="text-laro" /> : <Copy size={size} />}
    </button>
  );
}

/**
 * Inline text followed by a copy control.
 * Usage: <CopyableText value={ticketNumber} label="ticket number" className="font-mono" />
 */
export function CopyableText({ value, label, className, children, size = 14 }) {
  return (
    <span className={cn("inline-flex items-center gap-1", className)}>
      <span>{children ?? value}</span>
      <CopyButton value={value} label={label} size={size} />
    </span>
  );
}

export default CopyButton;
