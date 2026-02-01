/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ["class"],
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
  	extend: {
  		colors: {
  			border: 'hsl(var(--border))',
  			input: 'hsl(var(--input))',
  			ring: 'hsl(var(--ring))',
  			background: 'hsl(var(--background))',
  			foreground: 'hsl(var(--foreground))',
        'surface-container': 'hsl(var(--surface-container))',
        'surface-container-low': 'hsl(var(--surface-container-low))',
        'surface-container-high': 'hsl(var(--surface-container-high))',
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
  			destructive: {
  				DEFAULT: 'hsl(var(--destructive))',
  				foreground: 'hsl(var(--destructive-foreground))'
  			},
  			muted: {
  				DEFAULT: 'hsl(var(--muted))',
  				foreground: 'hsl(var(--muted-foreground))'
  			},
  			accent: {
  				DEFAULT: 'hsl(var(--accent))',
  				foreground: 'hsl(var(--accent-foreground))'
  			},
  			popover: {
  				DEFAULT: 'hsl(var(--popover))',
  				foreground: 'hsl(var(--popover-foreground))'
  			},
  			card: {
  				DEFAULT: 'hsl(var(--card))',
  				foreground: 'hsl(var(--card-foreground))'
  			},
        // Legacy alias - use 'laro' instead
        mise: {
          DEFAULT: '#7BC89C',
          light: '#DCF5E7',
          dark: '#5BB080',
        },
        // Laro brand colors - friendly cooking companion
        laro: {
          DEFAULT: '#7BC89C',  // Sage green
          light: '#DCF5E7',
          dark: '#5BB080',
          sage: '#7BC89C',
          cream: '#FAF7F2',
          charcoal: '#1F2937',
        },
        sunny: {
          DEFAULT: '#FFD93D',
          light: '#FFF4CC',
          dark: '#E6C235',
        },
        coral: {
          DEFAULT: '#FF6B6B',
          light: '#FFE5E5',
          dark: '#E05656',
        },
        teal: {
          DEFAULT: '#00D2D3',
          light: '#E0FAFA',
          dark: '#00B8B9',
        },
        tangerine: {
          DEFAULT: '#FF9F43',
          light: '#FFECD9',
          dark: '#E68A3A',
        },
        lavender: {
          DEFAULT: '#C7B7F7',  // AI suggestions color
          light: '#F5F3FF',
          dark: '#8B5CF6',
        },
        cream: {
          DEFAULT: '#FAF7F2',  // Laro warm cream
          paper: '#FFFFFF',
          subtle: '#FBF9F6',
        },
  			sidebar: {
  				DEFAULT: 'hsl(var(--sidebar-background))',
  				foreground: 'hsl(var(--sidebar-foreground))',
  				primary: 'hsl(var(--sidebar-primary))',
  				'primary-foreground': 'hsl(var(--sidebar-primary-foreground))',
  				accent: 'hsl(var(--sidebar-accent))',
  				'accent-foreground': 'hsl(var(--sidebar-accent-foreground))',
  				border: 'hsl(var(--sidebar-border))',
  				ring: 'hsl(var(--sidebar-ring))'
  			},
  			chart: {
  				'1': 'hsl(var(--chart-1))',
  				'2': 'hsl(var(--chart-2))',
  				'3': 'hsl(var(--chart-3))',
  				'4': 'hsl(var(--chart-4))',
  				'5': 'hsl(var(--chart-5))'
  			}
  		},
  		borderRadius: {
  			lg: 'var(--radius)',
  			md: 'calc(var(--radius) - 2px)',
  			sm: 'calc(var(--radius) - 4px)'
  		},
  		fontFamily: {
  			sans: [
  				'Roboto', 'Inter', 'sans-serif'
  			],
  			heading: [
  				'Manrope', 'sans-serif'
  			],
  			accent: [
  				'Caveat', 'cursive'
  			],
  			mono: [
  				'var(--font-mono)'
  			]
  		},
  		animation: {
  			'fade-in': 'fade-in 0.5s ease-out',
  			'slide-up': 'slide-up 0.5s ease-out',
  			'accordion-down': 'accordion-down 0.2s ease-out',
  			'accordion-up': 'accordion-up 0.2s ease-out'
  		},
  		keyframes: {
  			'fade-in': {
  				'0%': {
  					opacity: '0'
  				},
  				'100%': {
  					opacity: '1'
  				}
  			},
  			'slide-up': {
  				'0%': {
  					transform: 'translateY(10px)',
  					opacity: '0'
  				},
  				'100%': {
  					transform: 'translateY(0)',
  					opacity: '1'
  				}
  			},
  			'accordion-down': {
  				from: {
  					height: '0'
  				},
  				to: {
  					height: 'var(--radix-accordion-content-height)'
  				}
  			},
  			'accordion-up': {
  				from: {
  					height: 'var(--radix-accordion-content-height)'
  				},
  				to: {
  					height: '0'
  				}
  			}
  		}
  	}
  },
  plugins: [require("tailwindcss-animate")],
} 