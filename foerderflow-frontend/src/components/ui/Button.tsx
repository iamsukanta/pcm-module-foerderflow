"use client";

import type { ReactNode, ButtonHTMLAttributes, Ref } from "react";
import { clsx } from "clsx";

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
type ButtonSize = "sm" | "md" | "lg";

const variantClasses: Record<ButtonVariant, string> = {
  primary:
    "bg-soft-accent text-white hover:bg-soft-accentDark active:bg-soft-accentDark focus:ring-2 focus:ring-soft-accent focus:ring-offset-2 disabled:bg-soft-accentSoft disabled:text-soft-ink3",
  secondary:
    "bg-white text-soft-ink2 border border-soft-line hover:bg-soft-surfaceAlt active:bg-soft-line2 focus:ring-2 focus:ring-soft-accent focus:ring-offset-2 disabled:bg-soft-line2 disabled:text-soft-ink4",
  ghost:
    "text-soft-ink2 hover:bg-soft-line2 active:bg-soft-line focus:ring-2 focus:ring-soft-accent focus:ring-offset-2 disabled:text-soft-ink4",
  danger:
    "bg-soft-crit text-white hover:bg-soft-critDark active:bg-soft-critDark focus:ring-2 focus:ring-soft-crit focus:ring-offset-2 disabled:bg-soft-critSoft disabled:text-soft-ink3",
};

const sizeClasses: Record<ButtonSize, string> = {
  sm: "px-3 py-1.5 text-xs min-h-[36px] rounded-soft-sm",
  md: "px-4 py-2 text-sm min-h-[44px] rounded-soft-sm",
  lg: "px-6 py-3 text-base min-h-[44px] rounded-soft",
};

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  ref?: Ref<HTMLButtonElement>;
  children: ReactNode;
};

function Spinner() {
  return (
    <svg
      className="animate-spin -ml-1 mr-2 h-4 w-4"
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
      />
    </svg>
  );
}

export function Button({
  variant = "primary",
  size = "md",
  loading = false,
  disabled,
  children,
  className,
  type = "button",
  ref,
  ...props
}: ButtonProps) {
  const isDisabled = disabled || loading;

  return (
    <button
      ref={ref}
      type={type}
      disabled={isDisabled}
      aria-disabled={isDisabled}
      aria-busy={loading}
      className={clsx(
        "inline-flex items-center justify-center font-medium transition-colors duration-150 outline-none shadow-soft",
        "disabled:cursor-not-allowed",
        variantClasses[variant],
        sizeClasses[size],
        className,
      )}
      {...props}
    >
      {loading && <Spinner />}
      {children}
    </button>
  );
}
