/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#17211b',
        moss: {
          50: '#f1f7f2',
          100: '#dcecdf',
          200: '#bad9c1',
          300: '#8aba99',
          400: '#5d9870',
          500: '#3f7b57',
          600: '#306246',
          700: '#284f3a',
          800: '#223f30',
          900: '#1d3429',
          950: '#102119',
        },
        clay: '#d66b42',
      },
      boxShadow: {
        card: '0 1px 2px rgba(23,33,27,.06), 0 10px 30px rgba(23,33,27,.05)',
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        display: ['"DM Sans"', 'Inter', 'ui-sans-serif', 'system-ui'],
      },
    },
  },
  plugins: [],
}
