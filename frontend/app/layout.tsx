import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "RootTrace — Agentic AI Incident Investigation",
  description: "Evidence-driven AI system for software incident root cause analysis",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
