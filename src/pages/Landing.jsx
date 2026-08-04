import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Button } from '../components/ui/button';
import { FeatureWalkthrough } from '../components/FeatureWalkthrough';
import {
  ChefHat,
  UtensilsCrossed,
  CalendarDays,
  ShoppingCart,
  Refrigerator,
  Users,
  ArrowRight,
  Sparkles,
  WifiOff,
  Bell,
  Server,
  Shield,
  Github,
  Moon,
  Play
} from 'lucide-react';

const features = [
  {
    icon: UtensilsCrossed,
    title: 'Recipe Collection',
    description: 'Store and organize all your favorite recipes in one beautiful place.',
    color: 'coral',
    bgColor: 'bg-coral-light',
    iconColor: 'text-coral',
  },
  {
    icon: Sparkles,
    title: 'AI Import',
    description: 'Paste any recipe URL and let AI extract it automatically.',
    color: 'laro',
    bgColor: 'bg-laro-light',
    iconColor: 'text-laro',
  },
  {
    icon: CalendarDays,
    title: 'Meal Planning',
    description: 'Plan your weekly meals with our intuitive calendar view.',
    color: 'teal',
    bgColor: 'bg-teal-light',
    iconColor: 'text-teal',
  },
  {
    icon: ShoppingCart,
    title: 'Shopping Lists',
    description: 'Auto-generate shopping lists from your planned meals.',
    color: 'tangerine',
    bgColor: 'bg-tangerine-light',
    iconColor: 'text-tangerine',
  },
  {
    icon: Refrigerator,
    title: 'What\'s in My Fridge',
    description: 'Enter your ingredients and find matching recipes instantly.',
    color: 'sunny',
    bgColor: 'bg-sunny-light',
    iconColor: 'text-sunny',
  },
  {
    icon: Users,
    title: 'Family Sharing',
    description: 'Share recipes and meal plans with your household members.',
    color: 'lavender',
    bgColor: 'bg-lavender-light',
    iconColor: 'text-lavender',
  },
];

const selfHostFeatures = [
  {
    icon: Server,
    title: 'Self-Hosted',
    description: 'Run on your own server. Your data stays with you.',
    color: 'laro',
    bgColor: 'bg-laro-light',
    iconColor: 'text-laro',
  },
  {
    icon: WifiOff,
    title: '100% Offline AI',
    description: 'Embedded AI that works without internet connection.',
    color: 'teal',
    bgColor: 'bg-teal-light',
    iconColor: 'text-teal',
  },
  {
    icon: Shield,
    title: 'Privacy First',
    description: 'No tracking, no analytics, no data collection.',
    color: 'coral',
    bgColor: 'bg-coral-light',
    iconColor: 'text-coral',
  },
  {
    icon: Bell,
    title: 'Push Notifications',
    description: 'Get meal reminders and shopping alerts.',
    color: 'tangerine',
    bgColor: 'bg-tangerine-light',
    iconColor: 'text-tangerine',
  },
];

const fadeInUp = {
  initial: { opacity: 0, y: 20 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.5 }
};

export const Landing = () => {
  const navigate = useNavigate();
  const [showWalkthrough, setShowWalkthrough] = useState(false);

  // Check if first-time visitor (haven't seen walkthrough)
  useEffect(() => {
    const hasSeenWalkthrough = localStorage.getItem('laro_walkthrough_seen');
    if (!hasSeenWalkthrough) {
      // Auto-show walkthrough for first-time visitors after a brief delay
      const timer = setTimeout(() => setShowWalkthrough(true), 500);
      return () => clearTimeout(timer);
    }
  }, []);

  const handleWalkthroughComplete = () => {
    setShowWalkthrough(false);
    navigate('/register');
  };

  const handleWalkthroughSkip = () => {
    setShowWalkthrough(false);
  };

  if (showWalkthrough) {
    return (
      <FeatureWalkthrough
        onComplete={handleWalkthroughComplete}
        onSkip={handleWalkthroughSkip}
      />
    );
  }

  return (
    <div className="min-h-screen bg-background overflow-hidden">
      {/* Header */}
      <header className="relative z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex items-center justify-between">
            <img
              src="/laro-banner.png"
              alt="Laro - Your Kitchen Sidekick"
              className="h-16"
            />
            <div className="flex items-center gap-3">
              <Link to="/login">
                <Button variant="ghost" className="rounded-full" data-testid="login-btn">
                  Sign In
                </Button>
              </Link>
              <Link to="/register">
                <Button className="rounded-full bg-laro hover:bg-laro-dark shadow-sm" data-testid="register-btn">
                  Get Started
                </Button>
              </Link>
            </div>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="relative pt-12 pb-24 lg:pt-20 lg:pb-32">
        {/* Background Pattern */}
        <div className="absolute inset-0 hero-pattern pointer-events-none" />
        
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid lg:grid-cols-2 gap-12 items-center">
            {/* Left: Text */}
            <motion.div 
              className="text-left"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.6 }}
            >
              <span className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-laro-light text-laro text-sm font-medium mb-6">
                <Sparkles className="w-4 h-4" />
                Self-Hostable Recipe App
              </span>
              
              <h1 className="font-heading text-4xl sm:text-5xl lg:text-6xl font-bold text-foreground leading-tight">
                Your Family's
                <br />
                <span className="text-laro">Recipe Haven</span>
              </h1>
              
              <p className="mt-6 text-lg text-muted-foreground max-w-lg leading-relaxed">
                Organize recipes, plan meals, and share with your household. 
                Import recipes with AI, search by ingredients, and never wonder 
                "what's for dinner" again.
              </p>
              
              <div className="mt-8 flex flex-wrap gap-4">
                <Link to="/register">
                  <Button
                    size="lg"
                    className="rounded-full bg-laro hover:bg-laro-dark shadow-md hover:shadow-lg transition-all px-8"
                    data-testid="hero-get-started"
                  >
                    Start Cooking
                    <ArrowRight className="w-4 h-4 ml-2" />
                  </Button>
                </Link>
                <Link to="/login">
                  <Button
                    size="lg"
                    variant="outline"
                    className="rounded-full border-laro text-laro hover:bg-laro-light"
                  >
                    Sign In
                  </Button>
                </Link>
              </div>

              {/* Tour button */}
              <button
                onClick={() => setShowWalkthrough(true)}
                className="mt-4 inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-laro transition-colors"
              >
                <Play className="w-4 h-4" />
                Take the tour
              </button>
            </motion.div>

            {/* Right: Image Grid */}
            <motion.div 
              className="relative"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.6, delay: 0.2 }}
            >
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-4">
                  <div className="rounded-2xl overflow-hidden shadow-card aspect-square">
                    <img
                      src="/images/vegetables.jpg"
                      alt="Fresh vegetables"
                      loading="lazy" decoding="async" className="w-full h-full object-cover"
                    />
                  </div>
                  <div className="rounded-2xl overflow-hidden shadow-card aspect-[4/3]">
                    <img
                      src="/images/cooking.jpg"
                      alt="Cooking"
                      loading="lazy" decoding="async" className="w-full h-full object-cover"
                    />
                  </div>
                </div>
                <div className="space-y-4 pt-8">
                  <div className="rounded-2xl overflow-hidden shadow-card aspect-[4/3]">
                    <img
                      src="/images/healthy-dish.jpg"
                      alt="Healthy dish"
                      loading="lazy" decoding="async" className="w-full h-full object-cover"
                    />
                  </div>
                  <div className="rounded-2xl overflow-hidden shadow-card aspect-square">
                    <img
                      src="/images/ingredients.jpg"
                      alt="Recipe ingredients"
                      loading="lazy" decoding="async" className="w-full h-full object-cover"
                    />
                  </div>
                </div>
              </div>
              
              {/* Floating Card */}
              <motion.div 
                className="absolute -bottom-4 -left-4 bg-white rounded-xl shadow-hover p-4 border border-border/60"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, delay: 0.5 }}
              >
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 rounded-lg bg-coral-light flex items-center justify-center">
                    <Refrigerator className="w-6 h-6 text-coral" />
                  </div>
                  <div>
                    <p className="font-medium text-sm">What's in my fridge?</p>
                    <p className="text-xs text-muted-foreground">Find recipes by ingredients</p>
                  </div>
                </div>
              </motion.div>
            </motion.div>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="py-20 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <motion.div 
            className="text-center mb-16"
            {...fadeInUp}
          >
            <h2 className="font-heading text-3xl sm:text-4xl font-bold text-foreground">
              Everything You Need
            </h2>
            <p className="mt-4 text-muted-foreground max-w-2xl mx-auto">
              A complete recipe management system designed for home cooks and families.
            </p>
          </motion.div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
            {features.map((feature, index) => {
              const Icon = feature.icon;
              return (
                <motion.div
                  key={feature.title}
                  className="group p-6 rounded-2xl bg-cream hover:bg-white border border-transparent hover:border-border/60 hover:shadow-card transition-all duration-300"
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.5, delay: index * 0.1 }}
                >
                  <div className={`w-12 h-12 rounded-xl ${feature.bgColor} flex items-center justify-center mb-4 transition-colors`}>
                    <Icon className={`w-6 h-6 ${feature.iconColor} transition-colors`} />
                  </div>
                  <h3 className="font-heading font-semibold text-lg mb-2">{feature.title}</h3>
                  <p className="text-muted-foreground text-sm leading-relaxed">{feature.description}</p>
                </motion.div>
              );
            })}
          </div>
        </div>
      </section>

      {/* Self-Hosting Section */}
      <section className="py-20 bg-cream">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <motion.div 
            className="text-center mb-16"
            {...fadeInUp}
          >
            <span className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-laro-light text-laro text-sm font-medium mb-4">
              <Server className="w-4 h-4" />
              Self-Hosted
            </span>
            <h2 className="font-heading text-3xl sm:text-4xl font-bold text-foreground">
              Your Data, Your Server
            </h2>
            <p className="mt-4 text-muted-foreground max-w-2xl mx-auto">
              Run Laro on your own hardware. No cloud required, no subscriptions, complete privacy.
            </p>
          </motion.div>

          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
            {selfHostFeatures.map((feature, index) => {
              const Icon = feature.icon;
              return (
                <motion.div
                  key={feature.title}
                  className="text-center p-6"
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.5, delay: index * 0.1 }}
                >
                  <div className={`w-14 h-14 rounded-2xl ${feature.bgColor} flex items-center justify-center mx-auto mb-4`}>
                    <Icon className={`w-7 h-7 ${feature.iconColor}`} />
                  </div>
                  <h3 className="font-heading font-semibold mb-2">{feature.title}</h3>
                  <p className="text-muted-foreground text-sm">{feature.description}</p>
                </motion.div>
              );
            })}
          </div>

          {/* Tech Stack */}
          <motion.div 
            className="mt-16 text-center"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.5 }}
          >
            <p className="text-sm text-muted-foreground mb-4">Built with modern, reliable technology</p>
            <div className="flex flex-wrap justify-center gap-3">
              {['React', 'FastAPI', 'PostgreSQL', 'Docker', 'GPT4All'].map((tech) => (
                <span 
                  key={tech}
                  className="px-4 py-2 rounded-full bg-white border border-border/60 text-sm font-medium"
                >
                  {tech}
                </span>
              ))}
            </div>
          </motion.div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-20 bg-laro">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <motion.div {...fadeInUp}>
            <h2 className="font-heading text-3xl sm:text-4xl font-bold text-white mb-6">
              Ready to Organize Your Recipes?
            </h2>
            <p className="text-laro-light text-lg mb-8 max-w-2xl mx-auto">
              Deploy in minutes with Docker. No account required, no data collected.
            </p>
            <div className="flex flex-wrap justify-center gap-4">
              <Link to="/register">
                <Button 
                  size="lg" 
                  className="rounded-full bg-white text-laro hover:bg-cream shadow-md px-8"
                  data-testid="cta-get-started"
                >
                  Get Started Free
                  <ArrowRight className="w-4 h-4 ml-2" />
                </Button>
              </Link>
              <a 
                href="https://github.com/Domocn/Laro" 
                target="_blank" 
                rel="noopener noreferrer"
              >
                <Button 
                  size="lg" 
                  variant="outline"
                  className="rounded-full border-white/30 text-white hover:bg-white/10 px-8"
                >
                  <Github className="w-4 h-4 mr-2" />
                  View on GitHub
                </Button>
              </a>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-8 bg-cream border-t border-border/40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <img src="/laro-icon.png" alt="Laro" className="w-10 h-10 rounded-lg" />
              <span className="font-heading font-semibold text-lg">Laro</span>
            </div>
            <div className="flex items-center gap-6">
              <Link to="/privacy-policy" className="text-sm text-muted-foreground hover:text-laro transition-colors">
                Privacy Policy
              </Link>
              <a
                href="https://github.com/Domocn/Laro"
                target="_blank"
                rel="noopener noreferrer"
                className="text-muted-foreground hover:text-laro transition-colors"
              >
                <Github className="w-5 h-5" />
              </a>
              <p className="text-sm text-muted-foreground">
                Open source • MIT License
              </p>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
};
