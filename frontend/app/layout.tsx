import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/components/AuthProvider";
import { ClientLayout } from "@/components/ClientLayout";

export const metadata: Metadata = {
  title: "Settlement Portfolio AI Agent",
  description: "Decision Intelligence for debt settlement portfolios",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="font-sans">
        <AuthProvider>
          <ClientLayout>{children}</ClientLayout>
        </AuthProvider>
      </body>
    </html>
  );
}
