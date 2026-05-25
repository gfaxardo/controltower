/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        ct: {
          'bg':        '#f5f3f0',
          'surface':   '#fafaf8',
          'card':      '#ffffff',
          'border':    '#e7e5e2',
          'border-hi': '#d6d3d0',
          'text':      '#292524',
          'text2':     '#78716c',
          'text3':     '#a8a29e',
          'accent':    '#2563eb',
          'accent-hi': '#1d4ed8',
          'accent-lo': '#dbeafe',
          'nav':       '#1c1917',
          'nav-text':  '#e7e5e2',
          'nav-hover': '#292524',
          'good':      '#059669',
          'good-lo':   '#d1fae5',
          'warn':      '#d97706',
          'warn-lo':   '#fef3c7',
          'bad':       '#dc2626',
          'bad-lo':    '#fee2e2',
          'info':      '#6366f1',
          'info-lo':   '#e0e7ff',
        },
      },
      fontSize: {
        '2xs': ['0.6875rem', { lineHeight: '0.875rem' }],  /* 11px — minimum operational */
        inherit: 'inherit',
      },
    },
  },
  plugins: [],
}
