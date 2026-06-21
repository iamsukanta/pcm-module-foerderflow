"use client";

import { useEffect } from "react";
import { CheckCircle, XCircle, X } from "lucide-react";
import { clsx } from "clsx";

export type ToastItem = {
  id: string;
  type: "success" | "error";
  message: string;
};

type ToastProps = {
  toast: ToastItem;
  onDismiss: (id: string) => void;
};

export function Toast({ toast, onDismiss }: ToastProps) {
  useEffect(() => {
    const timer = setTimeout(() => {
      onDismiss(toast.id);
    }, 4000);
    return () => clearTimeout(timer);
  }, [toast.id, onDismiss]);

  return (
    <div
      role="alert"
      aria-live="polite"
      className={clsx(
        "flex items-start gap-3 w-full max-w-sm rounded-soft-sm p-4 shadow-soft-lg border",
        "animate-in slide-in-from-right-5 fade-in duration-300",
        toast.type === "success"
          ? "bg-soft-surface border-soft-ok/20 text-soft-ink"
          : "bg-soft-surface border-soft-crit/20 text-soft-ink",
      )}
    >
      {toast.type === "success" ? (
        <CheckCircle className="h-5 w-5 text-soft-ok shrink-0 mt-0.5" aria-hidden="true" />
      ) : (
        <XCircle className="h-5 w-5 text-soft-crit shrink-0 mt-0.5" aria-hidden="true" />
      )}
      <p className="text-sm flex-1">{toast.message}</p>
      <button
        onClick={() => onDismiss(toast.id)}
        className="text-soft-ink3 hover:text-soft-ink focus:ring-2 focus:ring-soft-accent rounded shrink-0"
        aria-label="Schließen"
      >
        <X className="h-4 w-4" aria-hidden="true" />
      </button>
    </div>
  );
}
