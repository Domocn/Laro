import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { Button } from './ui/button';
import {
  Sparkles,
  CalendarDays,
  ShoppingCart,
  Refrigerator,
  Users,
  ChefHat,
  ArrowRight,
  ArrowLeft,
  X,
} from 'lucide-react';

const WALKTHROUGH_SLIDES = [
  {
    id: 'welcome',
    icon: ChefHat,
    iconBg: 'bg-laro-light',
    iconColor: 'text-laro',
    title: 'Welcome to Laro',
    subtitle: 'Your Kitchen Sidekick',
    description: 'The self-hostable recipe app that helps you organize recipes, plan meals, and cook with confidence.',
    image: 'https://images.unsplash.com/photo-1556909114-f6e7ad7d3136?auto=format&fit=crop&w=800&q=80',
    gradient: 'from-laro/20 to-teal/10',
  },
  {
    id: 'import',
    icon: Sparkles,
    iconBg: 'bg-tangerine-light',
    iconColor: 'text-tangerine',
    title: 'AI-Powered Import',
    subtitle: 'Paste any URL',
    description: 'Simply paste a recipe URL and let our AI extract the ingredients, steps, and photos automatically. No more copy-pasting!',
    image: 'https://images.unsplash.com/photo-1466637574441-749b8f19452f?auto=format&fit=crop&w=800&q=80',
    gradient: 'from-tangerine/20 to-sunny/10',
  },
  {
    id: 'mealplan',
    icon: CalendarDays,
    iconBg: 'bg-teal-light',
    iconColor: 'text-teal',
    title: 'Meal Planning',
    subtitle: 'Plan your week',
    description: 'Drag and drop recipes onto your calendar. See your whole week at a glance and never wonder "what\'s for dinner" again.',
    image: 'https://images.unsplash.com/photo-1490645935967-10de6ba17061?auto=format&fit=crop&w=800&q=80',
    gradient: 'from-teal/20 to-laro/10',
  },
  {
    id: 'shopping',
    icon: ShoppingCart,
    iconBg: 'bg-coral-light',
    iconColor: 'text-coral',
    title: 'Smart Shopping Lists',
    subtitle: 'Auto-generated',
    description: 'One tap generates a shopping list from your meal plan. Ingredients are combined and organized by aisle.',
    image: 'https://images.unsplash.com/photo-1542838132-92c53300491e?auto=format&fit=crop&w=800&q=80',
    gradient: 'from-coral/20 to-tangerine/10',
  },
  {
    id: 'fridge',
    icon: Refrigerator,
    iconBg: 'bg-sunny-light',
    iconColor: 'text-sunny',
    title: "What's in My Fridge?",
    subtitle: 'Cook what you have',
    description: 'Enter the ingredients you have on hand and discover recipes you can make right now. Reduce waste and save money.',
    image: 'https://images.unsplash.com/photo-1584568694244-14fbdf83bd30?auto=format&fit=crop&w=800&q=80',
    gradient: 'from-sunny/20 to-teal/10',
  },
  {
    id: 'family',
    icon: Users,
    iconBg: 'bg-lavender-light',
    iconColor: 'text-lavender',
    title: 'Family Sharing',
    subtitle: 'Cook together',
    description: 'Share recipes and meal plans with your household. Everyone can add favorites, plan meals, and contribute to shopping lists.',
    image: 'https://images.unsplash.com/photo-1556911220-bff31c812dba?auto=format&fit=crop&w=800&q=80',
    gradient: 'from-lavender/20 to-laro/10',
  },
];

const slideVariants = {
  enter: (direction) => ({
    x: direction > 0 ? 1000 : -1000,
    opacity: 0,
  }),
  center: {
    zIndex: 1,
    x: 0,
    opacity: 1,
  },
  exit: (direction) => ({
    zIndex: 0,
    x: direction < 0 ? 1000 : -1000,
    opacity: 0,
  }),
};

export const FeatureWalkthrough = ({ onComplete, onSkip }) => {
  const navigate = useNavigate();
  const [[currentSlide, direction], setSlide] = useState([0, 0]);
  const [autoProgress, setAutoProgress] = useState(true);

  const slide = WALKTHROUGH_SLIDES[currentSlide];

  useEffect(() => {
    if (!autoProgress) return;

    const timer = setTimeout(() => {
      if (currentSlide < WALKTHROUGH_SLIDES.length - 1) {
        setSlide([currentSlide + 1, 1]);
      }
    }, 5000);

    return () => clearTimeout(timer);
  }, [currentSlide, autoProgress]);

  const handleNext = () => {
    setAutoProgress(false);
    if (currentSlide < WALKTHROUGH_SLIDES.length - 1) {
      setSlide([currentSlide + 1, 1]);
    } else {
      handleComplete();
    }
  };

  const handlePrev = () => {
    setAutoProgress(false);
    if (currentSlide > 0) {
      setSlide([currentSlide - 1, -1]);
    }
  };

  const handleComplete = () => {
    localStorage.setItem('laro_walkthrough_seen', 'true');
    if (onComplete) {
      onComplete();
    } else {
      navigate('/register');
    }
  };

  const handleSkip = () => {
    localStorage.setItem('laro_walkthrough_seen', 'true');
    if (onSkip) {
      onSkip();
    } else {
      navigate('/');
    }
  };

  const goToSlide = (index) => {
    setAutoProgress(false);
    setSlide([index, index > currentSlide ? 1 : -1]);
  };

  const Icon = slide.icon;

  return (
    <div className="fixed inset-0 z-50 bg-background overflow-hidden">
      {/* Background Gradient */}
      <div className={`absolute inset-0 bg-gradient-to-br ${slide.gradient} transition-all duration-700`} />

      {/* Skip Button */}
      <button
        onClick={handleSkip}
        className="absolute top-6 right-6 z-20 p-2 rounded-full bg-background/80 backdrop-blur-sm border border-border/60 text-muted-foreground hover:text-foreground transition-colors"
      >
        <X className="w-5 h-5" />
      </button>

      {/* Main Content */}
      <div className="relative h-full flex flex-col lg:flex-row">
        {/* Left Side - Image */}
        <div className="relative w-full lg:w-1/2 h-[40vh] lg:h-full overflow-hidden">
          <AnimatePresence initial={false} custom={direction}>
            <motion.div
              key={slide.id}
              custom={direction}
              variants={slideVariants}
              initial="enter"
              animate="center"
              exit="exit"
              transition={{
                x: { type: 'spring', stiffness: 300, damping: 30 },
                opacity: { duration: 0.2 },
              }}
              className="absolute inset-0"
            >
              <img
                src={slide.image}
                alt={slide.title}
                className="w-full h-full object-cover"
              />
              <div className="absolute inset-0 bg-gradient-to-t lg:bg-gradient-to-r from-background via-background/50 to-transparent" />
            </motion.div>
          </AnimatePresence>
        </div>

        {/* Right Side - Content */}
        <div className="flex-1 flex flex-col justify-center px-6 sm:px-12 lg:px-16 py-8 lg:py-0">
          <AnimatePresence mode="wait">
            <motion.div
              key={slide.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              transition={{ duration: 0.3 }}
              className="max-w-lg"
            >
              {/* Icon Badge */}
              <motion.div
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ type: 'spring', delay: 0.1 }}
                className={`w-16 h-16 ${slide.iconBg} rounded-2xl flex items-center justify-center mb-6 shadow-lg`}
              >
                <Icon className={`w-8 h-8 ${slide.iconColor}`} />
              </motion.div>

              {/* Subtitle */}
              <motion.p
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.15 }}
                className={`text-sm font-semibold ${slide.iconColor} uppercase tracking-wider mb-2`}
              >
                {slide.subtitle}
              </motion.p>

              {/* Title */}
              <motion.h1
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.2 }}
                className="font-heading text-3xl sm:text-4xl lg:text-5xl font-bold text-foreground mb-4"
              >
                {slide.title}
              </motion.h1>

              {/* Description */}
              <motion.p
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.25 }}
                className="text-lg text-muted-foreground leading-relaxed"
              >
                {slide.description}
              </motion.p>
            </motion.div>
          </AnimatePresence>

          {/* Navigation */}
          <div className="mt-8 lg:mt-12 max-w-lg">
            {/* Progress Dots */}
            <div className="flex justify-center lg:justify-start gap-2 mb-6">
              {WALKTHROUGH_SLIDES.map((s, index) => (
                <button
                  key={s.id}
                  onClick={() => goToSlide(index)}
                  className={`h-2 rounded-full transition-all duration-300 ${
                    index === currentSlide
                      ? 'w-8 bg-laro'
                      : index < currentSlide
                      ? 'w-2 bg-laro/50 hover:bg-laro/70'
                      : 'w-2 bg-border hover:bg-laro/30'
                  }`}
                />
              ))}
            </div>

            {/* Buttons */}
            <div className="flex items-center gap-4">
              {currentSlide > 0 && (
                <Button
                  variant="outline"
                  onClick={handlePrev}
                  className="rounded-full px-6"
                >
                  <ArrowLeft className="w-4 h-4 mr-2" />
                  Back
                </Button>
              )}

              <Button
                onClick={handleNext}
                className="rounded-full bg-laro hover:bg-laro-dark px-8 flex-1 sm:flex-none"
              >
                {currentSlide === WALKTHROUGH_SLIDES.length - 1 ? (
                  <>
                    Get Started
                    <Sparkles className="w-4 h-4 ml-2" />
                  </>
                ) : (
                  <>
                    Next
                    <ArrowRight className="w-4 h-4 ml-2" />
                  </>
                )}
              </Button>
            </div>

            {/* Auto-progress indicator */}
            {autoProgress && currentSlide < WALKTHROUGH_SLIDES.length - 1 && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="mt-4 text-xs text-muted-foreground text-center lg:text-left"
              >
                Auto-advancing... tap anywhere to control manually
              </motion.div>
            )}
          </div>
        </div>
      </div>

      {/* Progress Bar */}
      {autoProgress && (
        <div className="absolute bottom-0 left-0 right-0 h-1 bg-border/30">
          <motion.div
            key={currentSlide}
            className="h-full bg-laro"
            initial={{ width: '0%' }}
            animate={{ width: '100%' }}
            transition={{ duration: 5, ease: 'linear' }}
          />
        </div>
      )}
    </div>
  );
};

export default FeatureWalkthrough;
