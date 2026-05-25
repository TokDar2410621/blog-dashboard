import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
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
  metadataBase: new URL("https://gridar.app"),
  title: {
    default: "Gridar - Le SEO en francais qui comprend le Quebec",
    template: "%s | Gridar",
  },
  description:
    "SaaS SEO concu pour les PME quebecoises. Generation d'articles en lexique FR-CA, audit SEO automatique, suivi des positions Google. Arivex Studio.",
  applicationName: "Gridar",
  authors: [{ name: "Arivex Studio", url: "https://gridar.app" }],
  creator: "Arivex Studio",
  publisher: "Arivex Studio",
  openGraph: {
    type: "website",
    locale: "fr_CA",
    url: "https://gridar.app",
    siteName: "Gridar",
    title: "Gridar - Le SEO en francais qui comprend le Quebec",
    description:
      "Generation d'articles SEO en lexique quebecois, audit IA et suivi des positions Google. Pour les PME qui veulent ranker.",
  },
  twitter: {
    card: "summary_large_image",
    title: "Gridar - SEO francais pour le Quebec",
    description:
      "Generation d'articles en quebecois, audit SEO IA, suivi positions Google. Pour les PME.",
  },
  alternates: {
    canonical: "/",
  },
  robots: {
    index: true,
    follow: true,
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="fr-CA"
      className={`${geistSans.variable} ${geistMono.variable} antialiased dark`}
    >
      <body className="min-h-screen bg-zinc-950 text-zinc-100">{children}</body>
    </html>
  );
}
