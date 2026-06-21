import { requireOrgSession } from "@/lib/session";
import { serverFetch } from "@/lib/serverApi";
import { PageShell } from "@/components/ui/PageShell";
import {
  KontenClient,
  type KontoForUi,
  type FiscalYearOption,
} from "@/components/forms/KontenClient";

export const dynamic = "force-dynamic";

type BankAccountRow = {
  id: string;
  code: string;
  bezeichnung: string;
  typ: "BANK" | "KASSE" | "ONLINE_WALLET";
  iban: string | null;
  bic: string | null;
  bankname: string | null;
  ist_aktiv: boolean;
  saldo_aktuell: number;
  _count: { transactions: number };
  opening_balances: Array<{
    id: string;
    fiscal_year_id: string;
    saldo_eroeffnung: number;
    datum: string;
    fiscal_year: { id: string; jahr: number };
  }>;
};

type FiscalYearRow = { id: string; jahr: number; status: string };

export default async function KontenPage() {
  await requireOrgSession();

  const [accounts, fiscalYears] = await Promise.all([
    serverFetch<BankAccountRow[]>("/protected/bank-accounts?includeInactive=true"),
    serverFetch<FiscalYearRow[]>("/protected/haushaltsjahre"),
  ]);

  const accountsUi: KontoForUi[] = accounts.map((a) => ({
    id: a.id,
    code: a.code,
    bezeichnung: a.bezeichnung,
    typ: a.typ,
    iban: a.iban,
    bic: a.bic,
    bankname: a.bankname,
    ist_aktiv: a.ist_aktiv,
    anzahl_transaktionen: a._count?.transactions ?? 0,
    saldo_aktuell: a.saldo_aktuell,
    opening_balances: a.opening_balances.map((o) => ({
      id: o.id,
      fiscal_year_id: o.fiscal_year_id,
      fiscal_year_jahr: o.fiscal_year.jahr,
      saldo_eroeffnung: o.saldo_eroeffnung,
      datum: o.datum,
    })),
  }));

  const fyOptions: FiscalYearOption[] = fiscalYears.map((f) => ({
    id: f.id,
    jahr: f.jahr,
    status: f.status,
  }));

  return (
    <PageShell width="wide">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-soft-ink">Bank- und Kassenkonten</h1>
        <p className="mt-1 text-sm text-soft-ink3">
          Jede Transaktion läuft über genau ein Konto. Eröffnungssalden pro Geschäftsjahr machen den
          Saldo-Abgleich gegen den Bankexport möglich.
        </p>
      </div>

      <KontenClient initialAccounts={accountsUi} fiscalYears={fyOptions} />
    </PageShell>
  );
}
