import Link from "next/link";
import { redirect } from "next/navigation";
import { Mail } from "lucide-react";

/**
 * Dual-purpose, matching the magic-link target build_magic_link():
 *  - With ?token=...  → forward to the BFF callback (verifies + sets the cookie).
 *  - Without token    → the "check your inbox" confirmation screen.
 */
export default async function VerifyPage({
  searchParams,
}: {
  searchParams: Promise<{ token?: string; callbackUrl?: string }>;
}) {
  const { token, callbackUrl } = await searchParams;

  if (token) {
    const cb = callbackUrl ? `&callbackUrl=${encodeURIComponent(callbackUrl)}` : "";
    redirect(`/api/auth/callback?token=${encodeURIComponent(token)}${cb}`);
  }

  return (
    <main className="min-h-screen bg-soft-bg flex items-center justify-center px-4">
      <div className="bg-soft-surface rounded-soft-sm shadow-soft border border-soft-line p-8 w-full max-w-md text-center space-y-4">
        <div className="flex justify-center">
          <div className="rounded-full bg-soft-accentWash p-3">
            <Mail className="h-10 w-10 text-soft-accent" />
          </div>
        </div>
        <h1 className="text-xl font-bold text-soft-ink">Link wurde gesendet</h1>
        <p className="text-soft-ink3 text-sm leading-relaxed">
          Schau in dein Postfach — der Anmeldelink ist <strong>24 Stunden</strong> gültig.
          Schau auch im Spam-Ordner, falls du nichts findest.
        </p>
        <Link
          href="/login"
          className="inline-block text-sm text-soft-accent hover:text-soft-accentDark hover:underline"
        >
          Zurück zur Anmeldung
        </Link>
      </div>
    </main>
  );
}
