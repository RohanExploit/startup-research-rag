import type { Metadata } from "next";
import "./globals.css";
import StatusStrip from "@/components/StatusStrip";
import Sidebar from "@/components/Sidebar";

export const metadata: Metadata = {
  title: "Company Brain — Admin",
  description: "Admin dashboard for Company Brain multi-tenant RAG system",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body suppressHydrationWarning>
        <div className="app-shell">
          <StatusStrip />
          <Sidebar />
          <main className="main-content">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
