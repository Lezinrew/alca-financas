/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Brand colors - Alça Finanças
        brand: {
          50: '#eff6ff',
          100: '#dbeafe',
          200: '#bfdbfe',
          300: '#93c5fd',
          400: '#60a5fa',
          500: '#3b82f6', // primary
          600: '#2563eb',
          700: '#1d4ed8',
          800: '#1e40af',
          900: '#1e3a8a',
        },
        // Surface & borders - Light mode
        surface: {
          DEFAULT: '#ffffff',
          subtle: '#f8fafc',
          hover: '#f1f5f9',
        },
        // Surface & borders - Dark mode (Mobills-like)
        dark: {
          surface: {
            DEFAULT: '#1a1d29', // Card background
            elevated: '#252836', // Elevated cards, table headers
            base: '#0f172a', // Page background
            hover: '#2d3142', // Hover states
          },
          border: {
            DEFAULT: 'rgba(148, 163, 184, 0.2)', // #94a3b8 with 20% opacity
            subtle: 'rgba(148, 163, 184, 0.1)', // #94a3b8 with 10% opacity
            strong: 'rgba(148, 163, 184, 0.3)', // #94a3b8 with 30% opacity
          },
          text: {
            primary: '#ffffff', // Main text
            secondary: '#e2e8f0', // Secondary text
            tertiary: '#cbd5e1', // Tertiary text
            muted: '#94a3b8', // Muted text
          },
        },
        border: {
          DEFAULT: '#e2e8f0',
          light: '#f1f5f9',
          dark: '#cbd5e1',
        },
        // Semantic colors
        success: {
          DEFAULT: '#10b981',
          light: '#d1fae5',
          dark: '#059669',
        },
        error: {
          DEFAULT: '#ef4444',
          light: '#fee2e2',
          dark: '#dc2626',
        },
        warning: {
          DEFAULT: '#f59e0b',
          light: '#fef3c7',
          dark: '#d97706',
        },
        // Text colors
        muted: {
          DEFAULT: '#64748b',
          foreground: '#94a3b8',
        },
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', '-apple-system', 'sans-serif'],
      },
      fontSize: {
        // Page titles
        'page-title': ['1.5rem', { lineHeight: '2rem', fontWeight: '700' }],
        // Section titles
        'section-title': ['1.125rem', { lineHeight: '1.75rem', fontWeight: '600' }],
        // Financial values
        'value-lg': ['2rem', { lineHeight: '2.5rem', fontWeight: '700' }],
        'value-md': ['1.5rem', { lineHeight: '2rem', fontWeight: '600' }],
        'value-sm': ['1.125rem', { lineHeight: '1.75rem', fontWeight: '600' }],
      },
      borderRadius: {
        'card': '0.75rem', // 12px - padrão Alça Finanças
        'button': '0.5rem', // 8px
        'input': '0.5rem', // 8px
      },
      boxShadow: {
        'card': '0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)',
        'card-hover': '0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)',
        'modal': '0 20px 25px -5px rgb(0 0 0 / 0.1), 0 8px 10px -6px rgb(0 0 0 / 0.1)',
      },
      spacing: {
        'card': '1.5rem', // 24px padding padrão
        'section': '1.5rem', // 24px gap entre seções
      },
      animation: {
        'fade-in': 'fadeIn 0.3s ease-in-out',
        'slide-up': 'slideUp 0.3s ease-out',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { transform: 'translateY(10px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
      },
    },
  },
  plugins: [],
}
