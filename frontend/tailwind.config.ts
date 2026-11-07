import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Moroccan legal palette: deep zellige green, sand, terracotta accents.
        zellige: {
          50: "#f2f7f4",
          100: "#e0ede5",
          200: "#c2dbc9",
          300: "#97c1a4",
          400: "#67a27b",
          500: "#44855d",
          600: "#326a48",
          700: "#29553b",
          800: "#234531",
          900: "#1d392a",
          950: "#0f2017",
        },
        sand: {
          50: "#faf7f0",
          100: "#f3ecdc",
          200: "#e6d7b8",
          300: "#d6bd8b",
          400: "#c6a062",
          500: "#ba8c4b",
          600: "#a87940",
          700: "#8c6038",
          800: "#724f33",
          900: "#5e422d",
          950: "#332216",
        },
      },
      fontFamily: {
        arabic: ["var(--font-naskh)", "serif"],
        latin: ["var(--font-inter)", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
