import type { Config } from "tailwindcss";

/**
 * ScholarGuard design tokens — "research lab at night".
 *
 * HARD CONSTRAINT (see README + lib/constants.ts): severity colors are muted
 * by design. No saturated alarm red anywhere; no pulsing/blinking treatments.
 */
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          DEFAULT: "#0a0e14", // page background
          raised: "#0e131b",
          line: "rgba(255,255,255,0.10)", // hairline borders on glass
        },
        accent: {
          DEFAULT: "#8b93f8", // the ONE accent — cool electric periwinkle
          soft: "#a5abfa",
          dim: "#5a61c9",
        },
        // Muted severity/reliability system — never saturated alarm colors.
        reliable: "#4fae9b",   // calm muted teal — "comparatively reliable"
        caution: "#d4a054",    // soft amber — "use caution / over-triggers"
        neutralsev: "#8b95a7", // neutral slate — "unvalidated"
        elevated: "#c0764a",   // muted copper — high zone (not red)
        severe: "#a85d6e",     // muted rose — critical zone (not alarm red)
      },
      fontFamily: {
        display: ["var(--font-space-grotesk)", "system-ui", "sans-serif"],
        body: ["var(--font-inter)", "system-ui", "sans-serif"],
        mono: ["var(--font-jetbrains)", "ui-monospace", "monospace"],
      },
      borderRadius: {
        card: "1rem", // rounded-2xl equivalent, single source for all cards
      },
      boxShadow: {
        glass: "0 8px 32px rgba(0,0,0,0.35), inset 0 1px 0 rgba(255,255,255,0.04)",
        lift: "0 12px 40px rgba(0,0,0,0.45), 0 0 24px rgba(139,147,248,0.08)",
      },
      backgroundImage: {
        vignette:
          "radial-gradient(ellipse 120% 80% at 50% -10%, rgba(139,147,248,0.07), transparent 60%), radial-gradient(ellipse 100% 100% at 50% 120%, rgba(20,26,38,0.9), transparent 70%)",
      },
    },
  },
  plugins: [],
};

export default config;
