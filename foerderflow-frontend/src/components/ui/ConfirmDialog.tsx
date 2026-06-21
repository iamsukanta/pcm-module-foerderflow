"use client";

import { useEffect, useRef } from "react";
import { Button } from "./Button";
import { clsx } from "clsx";

type ConfirmDialogProps = {
  open: boolean;
  title: string;
  description: string;
  confirmLabel: string;
  onConfirm: () => void;
  onCancel: () => void;
  variant?: "danger" | "default";
  loading?: boolean;
};

export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel,
  onConfirm,
  onCancel,
  variant = "default",
  loading = false,
}: ConfirmDialogProps) {
  const cancelRef = useRef<HTMLButtonElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);

  // Focus trap + ESC handler
  useEffect(() => {
    if (!open) return;

    cancelRef.current?.focus();

    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        onCancel();
        return;
      }

      if (e.key !== "Tab") return;
      const focusable = dialogRef.current?.querySelectorAll<HTMLElement>(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
      );
      if (!focusable || focusable.length === 0) return;

      const first = focusable[0];
      const last = focusable[focusable.length - 1];

      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [open, onCancel]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-dialog-title"
      aria-describedby="confirm-dialog-description"
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/40" onClick={onCancel} aria-hidden="true" />

      {/* Dialog */}
      <div
        ref={dialogRef}
        className={clsx(
          "relative z-10 w-full max-w-md rounded-soft bg-soft-surface shadow-soft-lg p-6",
          "animate-in fade-in zoom-in-95 duration-150",
        )}
      >
        <h2 id="confirm-dialog-title" className="text-lg font-semibold text-soft-ink mb-2">
          {title}
        </h2>
        <p id="confirm-dialog-description" className="text-sm text-soft-ink2 mb-6">
          {description}
        </p>

        <div className="flex flex-col-reverse sm:flex-row sm:justify-end gap-3">
          <Button ref={cancelRef} variant="secondary" onClick={onCancel} disabled={loading}>
            Abbrechen
          </Button>
          <Button
            variant={variant === "danger" ? "danger" : "primary"}
            onClick={onConfirm}
            loading={loading}
          >
            {confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}
