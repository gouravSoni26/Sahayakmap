/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        // Severity color system from MASTERPLAN.md
        severity: {
          1: '#22c55e',   // normal — green
          2: '#eab308',   // advisory — yellow
          3: '#f97316',   // warning — orange
          4: '#ef4444',   // critical — red
          5: '#7c2d12',   // emergency — dark red
        },
      },
    },
  },
  plugins: [],
  safelist: [
    'bg-green-500', 'bg-yellow-500', 'bg-orange-500', 'bg-red-500', 'bg-red-900',
    'text-green-400', 'text-yellow-400', 'text-orange-400', 'text-red-400', 'text-red-900',
    'border-green-500', 'border-yellow-500', 'border-orange-500', 'border-red-500',
  ],
}
