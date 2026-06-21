import type { Metadata } from "next";
import "./globals.css";
import { QueryProvider } from "@/providers/QueryProvider";
import { ToastProvider } from "@/components/ui/ToastProvider";

export const metadata: Metadata = {
  title: "FoerderFlow",
  description: "Fördermittelverwaltung für soziale Träger",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="de">
      <body className="antialiased">
        <QueryProvider>
          <ToastProvider>{children}</ToastProvider>
        </QueryProvider>
      </body>
    </html>
  );
}
