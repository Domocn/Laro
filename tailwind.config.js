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
                        /* Manrope ≈ SoDoSans; Lora ≈ Lander Tall for brand moments */
                        sans: ['Manrope', 'Helvetica Neue', 'Helvetica', 'Arial', 'sans-serif'],
                        heading: ['Manrope', 'Helvetica Neue', 'Helvetica', 'Arial', 'sans-serif'],
                        accent: ['Lora', 'Iowan Old Style', 'Georgia', 'serif'],
                },
                borderRadius: {
                        lg: '0.75rem',   /* 12px cards */
                        md: '0.5rem',
                        sm: '0.25rem',
                        xl: '0.75rem',
                        '2xl': '0.75rem',
                        '3xl': '1.5rem',
                        pill: '50px',
                },
                letterSpacing: {
                        tight: '-0.01em',
                        tighter: '-0.16px',
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
                                light: '#d4e9e2',
                        },
                        secondary: {
                                DEFAULT: 'hsl(var(--secondary))',
                                foreground: 'hsl(var(--secondary-foreground))',
                                light: '#edebe9',
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
                        // Brand accent — RGB channels so opacity modifiers (bg-laro/20) work
                        laro: {
                                DEFAULT: 'rgb(var(--laro-accent-rgb) / <alpha-value>)',
                                light: 'rgb(var(--laro-accent-light-rgb) / <alpha-value>)',
                                dark: 'rgb(var(--laro-accent-dark-rgb) / <alpha-value>)',
                                brand: '#006241',
                                house: '#1E3932',
                                uplift: '#2b5148',
                                gold: '#cba258',
                        },
                        sunny: {
                                DEFAULT: '#cba258',
                                light: '#faf6ee',
                                dark: '#9A7D3A',
                        },
                        coral: {
                                DEFAULT: '#c82014',
                                light: '#F6E8E5',
                                dark: '#9A3F32',
                        },
                        teal: {
                                DEFAULT: '#00754A',
                                light: '#d4e9e2',
                                dark: '#1E3932',
                        },
                        tangerine: {
                                DEFAULT: '#C47A3A',
                                light: '#F6EBDD',
                                dark: '#9A5C28',
                        },
                        lavender: {
                                DEFAULT: '#2b5148',
                                light: '#d4e9e2',
                                dark: '#006241',
                        },
                        cream: {
                                DEFAULT: '#f2f0eb',
                                paper: '#ffffff',
                                subtle: '#edebe9',
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
                                '0%': { opacity: '0', transform: 'scale(0.98)' },
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
                        /* Whisper-soft layered shadows (DESIGN (1)) */
                        'soft': '0 0 0.5px rgba(0,0,0,0.14), 0 1px 1px rgba(0,0,0,0.24)',
                        'hover': '0 0 0.5px rgba(0,0,0,0.14), 0 2px 4px rgba(0,0,0,0.18)',
                        'card': '0 0 0.5px rgba(0,0,0,0.14), 0 1px 1px rgba(0,0,0,0.24)',
                        'nav': '0 1px 3px rgba(0,0,0,0.1), 0 2px 2px rgba(0,0,0,0.06), 0 0 2px rgba(0,0,0,0.07)',
                        'frap': '0 0 6px rgba(0,0,0,0.24), 0 8px 12px rgba(0,0,0,0.14)',
                        'sunny': '0 0 0.5px rgba(203,162,88,0.2), 0 1px 1px rgba(203,162,88,0.24)',
                        'coral': '0 0 0.5px rgba(200,32,20,0.14), 0 1px 1px rgba(200,32,20,0.2)',
                        'teal': '0 0 0.5px rgba(0,117,74,0.14), 0 1px 1px rgba(0,117,74,0.2)',
                        'tangerine': '0 0 0.5px rgba(196,122,58,0.14), 0 1px 1px rgba(196,122,58,0.2)',
                }
        }
  },
  plugins: [require("tailwindcss-animate")],
};
