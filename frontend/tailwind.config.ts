import type { Config } from "tailwindcss";

// StrategyForge AI design tokens: dense, dark, institutional register —
// closer to a trading terminal than a consumer SaaS palette, matching the
// Linear/Stripe/TradingView-quality bar the product spec asks for.
const config: Config = {
  darkMode: "class",
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        base: {
          950: "#05070a",
          900: "#0a0e14",
          850: "#0f141c",
          800: "#141a24",
          700: "#1c2430",
          600: "#2a3444",
          500: "#3d4a5e",
        },
        accent: {
          long: "#16c784",
          short: "#ef4c54",
          info: "#3b82f6",
          warn: "#f5a623",
        },
      },
      fontFamily: {
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "monospace"],
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
