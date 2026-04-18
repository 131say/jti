import type { Metadata } from "next";

import { Providers } from "@/components/Providers";

import "./globals.css";

export const metadata: Metadata = {
  title: "AI-Forge — AI Mechanical Design Platform",
  description:
    "Параметрический CAD из промпта: STEP, BOM, PDF-инструкции и симуляция. От идеи до производства за минуты.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ru">
      <body className="antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
