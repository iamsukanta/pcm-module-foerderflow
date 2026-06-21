import Link from "next/link";
import { AlertTriangle } from "lucide-react";

const ERROR_MESSAGES: Record<string, string> = {
  Configuration: "Server-Konfigurationsfehler. Bitte den Administrator kontaktieren.",
  AccessDenied: "Zugriff verweigert.",
  Verification:
    "Der Magic Link ist abgelaufen oder wurde bereits verwendet. Bitte erneut anmelden.",
  EMAIL_SEND_FAILED:
    "Der Anmeldelink konnte nicht gesendet werden. Bitte versuche es später erneut.",
  TooManyRequests:
    "Zu viele Anmeldeversuche. Bitte warte eine Stunde und versuche es dann erneut.",
  Default: "Ein unbekannter Fehler ist aufgetreten.",
};

export default async function LoginErrorPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string }>;
}) {
  const { error } = await searchParams;
  const message = ERROR_MESSAGES[error ?? "Default"] ?? ERROR_MESSAGES.Default;

  return (
    <main className="min-h-screen bg-soft-bg flex items-center justify-center px-4">
      <div className="bg-soft-critSoft rounded-soft-sm border border-soft-crit/20 p-8 max-w-md w-full text-center space-y-4 shadow-soft">
        <div className="flex justify-center">
          <div className="rounded-full bg-soft-surface p-3">
            <AlertTriangle className="h-10 w-10 text-soft-crit" />
          </div>
        </div>
        <h1 className="text-xl font-bold text-soft-ink">Anmeldung fehlgeschlagen</h1>
        <p className="text-sm text-soft-ink2">{message}</p>
        <Link
          href="/login"
          className="inline-block mt-2 px-4 py-2 bg-soft-accent text-white text-sm font-medium rounded-soft-sm hover:bg-soft-accentDark transition-colors shadow-soft"
        >
          Zurück zur Anmeldung
        </Link>
      </div>
    </main>
  );
}
