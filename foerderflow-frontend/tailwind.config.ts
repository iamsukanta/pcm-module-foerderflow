import type { Config } from "tailwindcss";

// Soft-Depth design system — ported verbatim from the monolith (BRAND.md is the
// source of truth). Do NOT alter token values; UI parity depends on them.
const config: Config = {
  content: [
    "./src/app/**/*.{ts,tsx}",
    "./src/components/**/*.{ts,tsx}",
    "./src/features/**/*.{ts,tsx}",
    "./src/layouts/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        soft: {
          bg: "#fafaf9",
          sidebarBg: "#f3f1ee",
          surface: "#ffffff",
          surfaceAlt: "#f7f5f2",
          ink: "#1b1a22",
          ink2: "#4a4753",
          ink3: "#7a7684",
          ink4: "#a8a4b2",
          line: "#ebe8e3",
          line2: "#f2efea",
          accent: "#6b5ce0",
          accentDark: "#4b3fb3",
          accentSoft: "#ece9f9",
          accentWash: "#f7f5fd",
          warn: "#b47a2c",
          warnSoft: "#fbf2e0",
          crit: "#b5453d",
          critDark: "#8b342e",
          critSoft: "#fbe4e1",
          ok: "#4a8064",
          okSoft: "#e4efe7",
          gold: "#c47a3d",
          goldSoft: "#f8ecdc",
        },
        primary: {
          DEFAULT: "#6b5ce0",
          50: "#f7f5fd",
          100: "#ece9f9",
          500: "#6b5ce0",
          600: "#4b3fb3",
        },
      },
      fontFamily: {
        sans: ["'IBM Plex Sans'", "system-ui", "sans-serif"],
        mono: ["'IBM Plex Mono'", "monospace"],
      },
      borderRadius: {
        soft: "14px",
        "soft-sm": "10px",
        "soft-xs": "8px",
      },
      boxShadow: {
        soft: "0 1px 2px rgba(27,26,34,0.04), 0 2px 8px rgba(27,26,34,0.04)",
        "soft-lg": "0 2px 4px rgba(27,26,34,0.04), 0 8px 24px rgba(27,26,34,0.06)",
      },
    },
  },
  plugins: [require("@tailwindcss/forms")],
};

export default config;
