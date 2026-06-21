import Link from "next/link";

export default function HomePage() {
  return (
    <main className="min-h-screen bg-gradient-to-b from-soft-bg to-soft-line2 flex items-center justify-center">
      <div className="text-center space-y-6 px-4">
        <div className="space-y-2">
          <h1 className="text-4xl font-bold text-soft-ink">FörderFlow</h1>
          <p className="text-soft-ink2 text-lg max-w-md mx-auto">
            Fördermittelverwaltung für soziale Träger
          </p>
        </div>
        <Link
          href="/login"
          className="inline-block bg-soft-accent text-white px-6 py-3 rounded-soft-sm font-medium hover:bg-soft-accentDark transition-colors shadow-soft"
        >
          Anmelden
        </Link>
      </div>
    </main>
  );
}
