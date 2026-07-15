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
          primary: '#013DED',
          'primary-dark': '#012FB8',
          'primary-light': '#2F63F5',
          accent: '#FF4500',
          success: '#22C55E',
        },
        surface: {
          DEFAULT: 'var(--surface)',
          elevated: 'var(--elevated)',
        },
      },
      fontFamily: {
        title: ['var(--font-title)', '-apple-system', 'system-ui', 'sans-serif'],
        body: ['var(--font-body)', 'Inter', 'sans-serif'],
        data: ['var(--font-mono)', 'Source Code Pro', 'monospace'],
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
