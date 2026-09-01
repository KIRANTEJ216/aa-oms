import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CAOMS — Aarav Advisors",
  description: "CA Office Management SaaS — Firm Pilot (TENANT_MODE=single)",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-background text-foreground">{children}</body>
    </html>
  );
}
