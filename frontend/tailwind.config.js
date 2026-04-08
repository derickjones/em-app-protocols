/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          primary: '#2563EB',
          'primary-dark': '#1D4ED8',
          'primary-light': '#3B82F6',
          accent: '#FF4500',
          success: '#22C55E',
        },
        surface: {
          DEFAULT: 'var(--surface)',
          elevated: 'var(--elevated)',
        },
      },
      fontFamily: {
        title: ['var(--font-title)', 'Space Grotesk', 'sans-serif'],
        body: ['var(--font-body)', 'Inter', 'sans-serif'],
        data: ['var(--font-mono)', 'JetBrains Mono', 'monospace'],
      },
      borderColor: {
        DEFAULT: 'var(--border)',
      },
    },
  },
  plugins: [
    require("@tailwindcss/typography"),
  ],
};
