/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        risk: {
          low: "#16a34a",
          medium: "#d97706",
          high: "#dc2626",
          critical: "#991b1b",
        },
        primary: {
          50: "#f2f0fe",
          100: "#e6e2fd",
          200: "#c9c0fb",
          300: "#a99cf8",
          400: "#8b78f4",
          500: "#6d56ef",
          600: "#5b3ff0",
          700: "#4b31d1",
          800: "#3c27a6",
          900: "#2f2080",
        },
      },
      fontFamily: {
        sans: ["'Plus Jakarta Sans'", "ui-sans-serif", "system-ui", "-apple-system", "sans-serif"],
        display: ["'Poppins'", "'Plus Jakarta Sans'", "ui-sans-serif", "sans-serif"],
      },
      boxShadow: {
        card: "0 2px 10px 0 rgba(76, 60, 160, 0.06)",
        soft: "0 8px 24px -6px rgba(76, 60, 160, 0.18)",
      },
      borderRadius: {
        "2xl": "1rem",
        "3xl": "1.5rem",
      },
    },
  },
  plugins: [],
};
