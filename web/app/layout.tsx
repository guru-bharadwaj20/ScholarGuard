import type { Metadata } from "next";
import { Inter, JetBrains_Mono, Space_Grotesk } from "next/font/google";
import "./globals.css";
import { FloatingNavbar } from "@/components/layout/FloatingNavbar";
import { FloatingPapersBackground } from "@/components/layout/FloatingPapersBackground";
import { CommandPalette } from "@/components/ui/command-palette";
import { SCREENING_DISCLAIMER } from "@/lib/constants";

const spaceGrotesk = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-space-grotesk",
  display: "swap",
});
const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});
const jetbrains = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-jetbrains",
  display: "swap",
});

export const metadata: Metadata = {
  title: "ScholarGuard — figure-integrity screening (research prototype)",
  description:
    "A research prototype that screens scientific figures for signals worth " +
    "a second look — with its real-world limitations measured and disclosed.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      className={`${spaceGrotesk.variable} ${inter.variable} ${jetbrains.variable}`}
    >
      <body>
        <FloatingPapersBackground />
        <FloatingNavbar />
        <CommandPalette />
        <main className="relative z-10 mx-auto min-h-screen max-w-6xl px-6 pt-10">
          {children}
        </main>
        <footer className="relative z-10 mx-auto max-w-6xl px-6 pb-28 pt-10">
          <p className="type-meta border-t border-ink-line pt-6">
            {SCREENING_DISCLAIMER}
          </p>
        </footer>
        <div className="noise-overlay" />
      </body>
    </html>
  );
}
