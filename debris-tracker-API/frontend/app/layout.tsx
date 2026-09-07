import type { Metadata } from "next";
import "./globals.css";
import { Sidebar } from "@/components/Sidebar";

export const metadata: Metadata = {
  title: "ORBITGUARD",
  description:
    "AI-assisted space debris monitoring, collision prediction and mitigation decision-support platform.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full">
      <body className="min-h-full">
        <Sidebar />
        <main className="ml-56 min-h-screen px-8 py-6">{children}</main>
      </body>
    </html>
  );
}
