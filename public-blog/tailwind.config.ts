import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      // Site-specific colors are CSS variables set per-request from the
      // Site.theme_config in the API. Tailwind references them so themes
      // can vary without rebuilding.
      colors: {
        brand: "var(--brand-color, #2563eb)",
        "brand-fg": "var(--brand-fg, #ffffff)",
      },
      fontFamily: {
        sans: ["var(--font-sans, system-ui)", "sans-serif"],
        display: ["var(--font-display, Georgia)", "serif"],
      },
    },
  },
  plugins: [],
};

export default config;
