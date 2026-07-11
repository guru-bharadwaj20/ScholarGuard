"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import { Home, Microscope, Upload } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Bottom floating dock — transparent glass, three destinations, nothing else.
 * No logo, no wordmark, no status pill; the brand lives in the hero.
 */

const LINKS = [
  { href: "/", label: "Home", icon: Home },
  { href: "/analyze", label: "Analyze", icon: Upload },
  { href: "/methodology", label: "Methodology", icon: Microscope },
];

export function FloatingNavbar() {
  const pathname = usePathname();

  return (
    <motion.nav
      initial={{ y: 40, opacity: 0, x: "-50%" }}
      animate={{ y: 0, opacity: 1, x: "-50%" }}
      transition={{ duration: 0.5, ease: "easeOut", delay: 0.2 }}
      className="fixed bottom-6 left-1/2 z-50 flex items-center gap-1 rounded-full border border-ink-line bg-slate-900/30 p-1.5 shadow-glass backdrop-blur-xl"
      aria-label="Primary"
    >
      {LINKS.map(({ href, label, icon: Icon }) => {
        const active = pathname === href;
        return (
          <Link
            key={href}
            href={href}
            className={cn(
              "flex items-center gap-2 rounded-full px-4 py-2.5 font-body text-sm transition-colors",
              active
                ? "bg-accent/15 text-accent"
                : "text-slate-400 hover:bg-white/5 hover:text-slate-100",
            )}
          >
            <Icon size={15} />
            <span className={cn(!active && "hidden sm:inline")}>{label}</span>
          </Link>
        );
      })}
    </motion.nav>
  );
}
