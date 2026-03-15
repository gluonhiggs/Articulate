import type { Config } from 'tailwindcss'

const config: Config = {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        background: '#0B0F19',
        sidebar: '#111827',
        card: '#1F2937',
        cardBorder: '#374151',
        accent: '#06B6D4',
        textPrimary: '#F3F4F6',
        textSecondary: '#9CA3AF',
      },
    },
  },
  plugins: [],
}

export default config
