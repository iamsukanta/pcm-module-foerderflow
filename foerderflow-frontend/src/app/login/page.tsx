"use client";

import { useState } from "react";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    const trimmed = email.trim();
    if (!trimmed || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmed)) {
      setError("Bitte eine gültige E-Mail-Adresse eingeben.");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const res = await fetch("/api/auth/magic-link", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: trimmed }),
      });

      if (!res.ok) {
        const data = (await res.json().catch(() => ({}))) as { error?: string };
        if (data?.error === "TooManyRequests") {
          setError("Zu viele Anmeldeversuche. Bitte warte eine Stunde.");
        } else {
          setError("Der Link konnte nicht gesendet werden. Bitte versuche es erneut.");
        }
        return;
      }

      setSent(true);
    } catch {
      setError("Netzwerkfehler — bitte prüfe deine Verbindung.");
    } finally {
      setLoading(false);
    }
  }

  if (sent) {
    return (
      <main className="min-h-screen bg-soft-bg flex items-center justify-center px-4">
        <div className="bg-soft-surface rounded-soft-sm shadow-soft border border-soft-line p-8 w-full max-w-md text-center space-y-3">
          <h1 className="text-xl font-bold text-soft-ink">Link wurde gesendet</h1>
          <p className="text-soft-ink2 text-sm">
            Wir haben einen Anmeldelink an <strong>{email}</strong> gesendet.
            Schau auch im Spam-Ordner.
          </p>
          <button
            onClick={() => {
              setSent(false);
              setEmail("");
            }}
            className="text-sm text-soft-accent hover:text-soft-accentDark hover:underline"
          >
            Andere E-Mail verwenden
          </button>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-soft-bg flex items-center justify-center px-4">
      <div className="bg-soft-surface rounded-soft-sm shadow-soft border border-soft-line p-8 w-full max-w-md space-y-6">
        <div className="text-center space-y-1">
          <h1 className="text-2xl font-bold text-soft-ink">FörderFlow</h1>
          <p className="text-soft-ink3 text-sm">
            Gib deine E-Mail-Adresse ein — wir schicken dir einen Anmeldelink.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="email" className="block text-sm font-medium text-soft-ink2 mb-1">
              E-Mail-Adresse
            </label>
            <input
              id="email"
              name="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              placeholder="name@organisation.de"
              className="w-full rounded-soft-xs border border-soft-line px-3 py-2 text-sm min-h-[44px] focus:outline-none focus:ring-2 focus:ring-soft-accent"
            />
          </div>

          {error && (
            <p className="text-sm text-soft-crit bg-soft-critSoft border border-soft-crit/20 rounded-soft-xs px-3 py-2">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-soft-accent text-white py-2.5 rounded-soft-sm font-medium hover:bg-soft-accentDark transition-colors text-sm min-h-[44px] shadow-soft disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {loading ? "Wird gesendet…" : "Magic Link senden"}
          </button>
        </form>
      </div>
    </main>
  );
}
