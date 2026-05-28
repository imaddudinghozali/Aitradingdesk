import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        shadow: {
          bg: "#0b0f14",
          panel: "#111821",
          border: "#1f2937",
          ink: "#e5e7eb",
          muted: "#94a3b8",
          accent: "#fbbf24",
          ok: "#10b981",
          warn: "#f59e0b",
          err: "#ef4444",
          info: "#3b82f6",
        },
      },
      fontFamily: {
        mono: [
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "Monaco",
          "Consolas",
          "monospace",
        ],
      },
    },
  },
  plugins: [],
};

export default config;
