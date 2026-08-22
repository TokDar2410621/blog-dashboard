import type { Metadata } from "next";
import { Geist, Geist_Mono, Fraunces } from "next/font/google";
import { Toaster } from "sonner";
import { Providers } from "@/components/providers/Providers";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const fraunces = Fraunces({
  variable: "--font-fraunces",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  metadataBase: new URL("https://www.gridar.app"),
  title: {
    default: "Gridar - Le SEO en francais qui comprend le Quebec",
    template: "%s | Gridar",
  },
  description:
    "Audit SEO gratuit en 60 secondes pour PME quebecoises : vois ce qui t'empeche de ranker sur Google. Puis Gridar corrige (contenu FR-CA, suivi des positions). Arivex Studio.",
  applicationName: "Gridar",
  authors: [{ name: "Arivex Studio", url: "https://www.gridar.app" }],
  creator: "Arivex Studio",
  publisher: "Arivex Studio",
  openGraph: {
    type: "website",
    locale: "fr_CA",
    url: "https://www.gridar.app",
    siteName: "Gridar",
    title: "Gridar - Le SEO en francais qui comprend le Quebec",
    description:
      "Entre ton URL, recois ton audit SEO en 60 secondes. Puis Gridar corrige ce qui bloque : contenu en quebecois et suivi des positions Google.",
  },
  twitter: {
    card: "summary_large_image",
    title: "Gridar - SEO francais pour le Quebec",
    description:
      "Audit SEO gratuit en 60s pour PME quebecoises. Vois ce qui bloque, puis Gridar corrige et suit tes positions.",
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
      className={`${geistSans.variable} ${geistMono.variable} ${fraunces.variable} antialiased dark`}
    >
      <body className="min-h-screen bg-zinc-950 text-zinc-100">
        <Providers>{children}</Providers>
        <Toaster theme="dark" />
      </body>
    </html>
  );
}
