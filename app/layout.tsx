import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { DailyGoalRoot } from "@/components/daily-goal";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "CV Generator",
  description: "Pega una vacante y genera un CV con tu perfil maestro.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="es"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <a href="#contenido" className="skip-link">
          Saltar al contenido
        </a>
        <DailyGoalRoot>
          <main id="contenido" className="flex min-h-0 flex-1 flex-col" tabIndex={-1}>
            {children}
          </main>
        </DailyGoalRoot>
      </body>
    </html>
  );
}
