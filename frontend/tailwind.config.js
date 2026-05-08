/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
        display: ['Outfit', 'sans-serif'],
      },
      animation: {
        'ripple': 'ripple 3s linear infinite',
        'border-spin': 'border-spin 4s linear infinite',
      },
      keyframes: {
        ripple: {
          '0%, 100%': { transform: 'scale(1)', opacity: '0.4' },
          '50%': { transform: 'scale(1.5)', opacity: '0' },
        },
        'border-spin': {
          '100%': {
            transform: 'rotate(1turn)',
          },
        },
      }
    },
  },
  plugins: [],
}
