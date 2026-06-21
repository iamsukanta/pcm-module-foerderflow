import Link from "next/link";
import { TransaktionImportForm } from "@/components/forms/TransaktionImportForm";
import { PageShell } from "@/components/ui/PageShell";

export default function TransaktionenImportPage() {
  return (
    <PageShell width="form">
      <div className="flex items-center gap-2 text-sm text-soft-ink3 mb-6">
        <Link href="/dashboard/transaktionen" className="hover:text-soft-accent">
          Transaktionen
        </Link>
        <span>/</span>
        <span className="text-soft-ink">Import</span>
      </div>

      <div className="mb-8">
        <h1 className="text-2xl font-bold text-soft-ink">Transaktionen importieren</h1>
        <p className="mt-1 text-sm text-soft-ink3">
          Lade deinen Kontoauszug als CSV-Datei hoch — das System erkennt Encoding, Spalten und
          Dezimalformat automatisch. Built-in-Profile für BFS-SozialBank, Finom, Sparkasse, DKB und
          PayPal werden anhand der Kopfzeile zugeordnet.
        </p>
      </div>

      <div className="bg-white rounded-soft-sm border border-soft-line p-6">
        <TransaktionImportForm />
      </div>

      <div className="mt-6 bg-soft-accentSoft rounded-soft-sm p-4 text-sm text-soft-accent">
        <p className="font-medium mb-1">Tipps für den Pilot-Import:</p>
        <ul className="list-disc list-inside space-y-1 text-soft-accent">
          <li>
            Vor dem ersten Upload Konten unter <em>Bank- und Kassenkonten</em> anlegen oder direkt
            aus IBAN auto-generieren lassen.
          </li>
          <li>
            Eröffnungssalden zum Jahreswechsel erfassen — der Saldo-Check vergleicht den CSV-Endsaldo
            mit der erwarteten Bewegungssumme.
          </li>
          <li>
            Buchungsregeln pflegen, damit häufige Auftraggeber automatisch auf Kostenstellen-Splits
            gemappt werden.
          </li>
        </ul>
      </div>
    </PageShell>
  );
}
