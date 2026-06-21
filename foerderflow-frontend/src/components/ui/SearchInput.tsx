"use client";

import { Search, X } from "lucide-react";

type SearchInputProps = {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  className?: string;
};

/** Reusable search input with a clear button. */
export function SearchInput({
  value,
  onChange,
  placeholder = "Suchen...",
  className = "",
}: SearchInputProps) {
  return (
    <div className={`relative ${className}`}>
      <Search
        className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-soft-ink3"
        aria-hidden="true"
      />
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full pl-9 pr-9 py-2.5 rounded-soft-xs border border-soft-line bg-soft-surface text-sm text-soft-ink placeholder-soft-ink3 focus:outline-none focus:ring-2 focus:ring-soft-accent transition-colors"
        aria-label="Suche"
      />
      {value && (
        <button
          onClick={() => onChange("")}
          className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 text-soft-ink3 hover:text-soft-ink hover:bg-soft-line2 rounded transition-colors"
          aria-label="Suche löschen"
          type="button"
        >
          <X className="h-4 w-4" />
        </button>
      )}
    </div>
  );
}
