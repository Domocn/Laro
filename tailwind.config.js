/** @type {import('tailwindcss').Config} */
module.exports = {
    darkMode: ["class"],
    content: [
    "./src/**/*.{js,jsx,ts,tsx}",
    "./public/index.html"
  ],
  theme: {
        extend: {
                fontFamily: {
                        sans: ['Inter', 'sans-serif'],
                        heading: ['Manrope', 'sans-serif'],
                        accent: ['Caveat', 'cursive'],
                },
                borderRadius: {
                        lg: '1rem',
                        md: '0.75rem',
                        sm: '0.5rem',
                        xl: '1.25rem',
                        '2xl': '1.5rem',
                        '3xl': '2rem',
                },
                colors: {
                        background: 'hsl(var(--background))',
                        foreground: 'hsl(var(--foreground))',
                        card: {
                                DEFAULT: 'hsl(var(--card))',
                                foreground: 'hsl(var(--card-foreground))'
                        },
                        popover: {
                                DEFAULT: 'hsl(var(--popover))',
                                foreground: 'hsl(var(--popover-foreground))'
                        },
                        primary: {
                                DEFAULT: 'hsl(var(--primary))',
                                foreground: 'hsl(var(--primary-foreground))',
                                light: '#E8E4FF',
                        },
                        secondary: {
                                DEFAULT: 'hsl(var(--secondary))',
                                foreground: 'hsl(var(--secondary-foreground))',
                                light: '#FFE5E5',
                        },
                        muted: {
                                DEFAULT: 'hsl(var(--muted))',
                                foreground: 'hsl(var(--muted-foreground))'
                        },
                        accent: {
                                DEFAULT: 'hsl(var(--accent))',
                                foreground: 'hsl(var(--accent-foreground))'
                        },
                        destructive: {
                                DEFAULT: 'hsl(var(--destructive))',
                                foreground: 'hsl(var(--destructive-foreground))'
                        },
                        border: 'hsl(var(--border))',
                        input: 'hsl(var(--input))',
                        ring: 'hsl(var(--ring))',
                        chart: {
                                '1': 'hsl(var(--chart-1))',
                                '2': 'hsl(var(--chart-2))',
                                '3': 'hsl(var(--chart-3))',
                                '4': 'hsl(var(--chart-4))',
                                '5': 'hsl(var(--chart-5))'
                        },
                        // Laro Brand Colors - Sage Green
                        laro: {
                                DEFAULT: '#7BC89C',
                                light: '#D1FAE5',
                                dark: '#065F46',
                        },
                        // Vibrant yellow from logo ingredients
                        sunny: {
                                DEFAULT: '#FFD93D',
                                light: '#FFF4CC',
                                dark: '#E6C235',
                        },
                        // Coral/Red from logo ingredients
                        coral: {
                                DEFAULT: '#FF6B6B',
                                light: '#FFE5E5',
                                dark: '#E05656',
                        },
                        // Teal/Cyan from logo ingredients
                        teal: {
                                DEFAULT: '#00D2D3',
                                light: '#E0FAFA',
                                dark: '#00B8B9',
                        },
                        // Orange from logo ingredients
                        tangerine: {
                                DEFAULT: '#FF9F43',
                                light: '#FFECD9',
                                dark: '#E68A3A',
                        },
                        // Light purple/lavender from logo ingredients
                        lavender: {
                                DEFAULT: '#A29BFE',
                                light: '#F0EEFF',
                                dark: '#8B83E6',
                        },
                        cream: {
                                DEFAULT: '#F8F7FF',
                                paper: '#FFFFFF',
                                subtle: '#F0EFFF',
                        },
                },
                keyframes: {
                        'accordion-down': {
                                from: { height: '0' },
                                to: { height: 'var(--radix-accordion-content-height)' }
                        },
                        'accordion-up': {
                                from: { height: 'var(--radix-accordion-content-height)' },
                                to: { height: '0' }
                        },
                        'fade-in-up': {
                                '0%': { opacity: '0', transform: 'translateY(20px)' },
                                '100%': { opacity: '1', transform: 'translateY(0)' }
                        },
                        'scale-in': {
                                '0%': { opacity: '0', transform: 'scale(0.95)' },
                                '100%': { opacity: '1', transform: 'scale(1)' }
                        },
                        'shimmer': {
                                '0%': { backgroundPosition: '200% 0' },
                                '100%': { backgroundPosition: '-200% 0' }
                        },
                },
                animation: {
                        'accordion-down': 'accordion-down 0.2s ease-out',
                        'accordion-up': 'accordion-up 0.2s ease-out',
                        'fade-in-up': 'fade-in-up 0.5s ease-out',
                        'scale-in': 'scale-in 0.3s ease-out',
                        'shimmer': 'shimmer 1.5s infinite linear',
                },
                boxShadow: {
                        'soft': '0 2px 8px rgba(0,0,0,0.04)',
                        'hover': '0 8px 24px rgba(0,0,0,0.08)',
                        'card': '0 4px 12px rgba(108,92,231,0.08)',
                        'sunny': '0 4px 12px rgba(255,217,61,0.25)',
                        'coral': '0 4px 12px rgba(255,107,107,0.25)',
                        'teal': '0 4px 12px rgba(0,210,211,0.25)',
                        'tangerine': '0 4px 12px rgba(255,159,67,0.25)',
                }
        }
  },
  plugins: [require("tailwindcss-animate")],
};
