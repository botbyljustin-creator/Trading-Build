import type { Metadata } from "next";
import "./globals.css";
import { AppAuthProvider } from "@/components/AuthProvider";
import { Header } from "@/components/Header";

export const metadata: Metadata = {
  title: "StrategyForge AI",
  description: "Turns educational trading content into structured, testable trading systems.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-base-950 font-sans text-slate-200">
        <AppAuthProvider>
          <Header />
          <main className="mx-auto max-w-7xl px-6 py-8">{children}</main>
        </AppAuthProvider>
      </body>
    </html>
  );
}
