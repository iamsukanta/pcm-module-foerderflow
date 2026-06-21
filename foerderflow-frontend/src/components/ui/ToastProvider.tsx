"use client";

import {
  createContext,
  useCallback,
  useContext,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { Toast, type ToastItem } from "./Toast";

type ToastContextValue = {
  success: (message: string) => void;
  error: (message: string) => void;
};

const ToastContext = createContext<ToastContextValue | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const counterRef = useRef(0);

  const addToast = useCallback((type: "success" | "error", message: string) => {
    const id = `toast-${Date.now()}-${counterRef.current++}`;
    setToasts((prev) => [...prev, { id, type, message }]);
  }, []);

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const value: ToastContextValue = {
    success: (msg) => addToast("success", msg),
    error: (msg) => addToast("error", msg),
  };

  return (
    <ToastContext.Provider value={value}>
      {children}
      {/* Toast container — top right */}
      <div
        aria-live="polite"
        className="fixed top-4 right-4 z-50 flex flex-col gap-2 w-full max-w-sm pointer-events-none"
      >
        {toasts.map((t) => (
          <div key={t.id} className="pointer-events-auto">
            <Toast toast={t} onDismiss={dismiss} />
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error("useToast muss innerhalb eines ToastProviders verwendet werden");
  }
  return ctx;
}
