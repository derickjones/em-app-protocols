/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        title: ['var(--font-geist-sans)', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
};
