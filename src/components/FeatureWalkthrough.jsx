import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { Button } from './ui/button';
import {
  Flame,
  Refrigerator,
  Smartphone,
  Focus,
  ArrowRight,
  ArrowLeft,
  X,
  Sparkles,
} from 'lucide-react';

/** Laro-shaped tour: calm / neurodiversity first.
 *  Import, meal plan, shopping = product functions, not tour focus. */
const WALKTHROUGH_SLIDES = [
  {
    id: 'calm',
    icon: Focus,
    iconBg: 'bg-teal-light',
    iconColor: 'text-teal',
    title: 'Dinner without the noise',
    subtitle: 'Your recipes. Your kitchen.',
    description: 'You add the recipes. Laro keeps them calm to cook from. Focus mode and quieter screens help everyone, shaped with ADHD and neurospicy cooks in mind.',
    image: '/images/dish-plated.jpg',
    gradient: 'from-teal/20 to-laro/10',
  },
  {
    id: 'cook',
    icon: Flame,
    iconBg: 'bg-laro-light',
    iconColor: 'text-laro',
    title: 'One step at the hob',
    subtitle: 'When your hands are full',
    description: 'Cook Mode shows the next move only: big type and timers. Finish dinner first. Read the full recipe later if you want.',
    image: '/images/hero-kitchen.jpg',
    gradient: 'from-laro/20 to-teal/10',
  },
  {
    id: 'fridge',
    icon: Refrigerator,
    iconBg: 'bg-coral-light',
    iconColor: 'text-coral',
    title: 'Start from what’s home',
    subtitle: 'From your own recipe box',
    description: 'Tell Laro what’s in the fridge. It shortlists from recipes you added, meals you can cook tonight, not a random content feed.',
    image: '/images/produce-fresh.jpg',
    gradient: 'from-coral/20 to-sunny/10',
  },
  {
    id: 'android',
    icon: Smartphone,
    iconBg: 'bg-sunny-light',
    iconColor: 'text-sunny',
    title: 'Web and Android',
    subtitle: 'Same calm flow everywhere',
    description: 'Plan on the laptop, shop from your phone, cook at the hob. Native Android on Play Store, not a stretched website.',
    image: '/images/pantry-ingredients.jpg',
    gradient: 'from-sunny/20 to-coral/10',
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
                className={`w-14 h-14 ${slide.iconBg} rounded-2xl flex items-center justify-center mb-6 shadow-soft ring-1 ring-border/40`}
              >
                <Icon className={`w-7 h-7 ${slide.iconColor}`} />
              </motion.div>

              {/* Subtitle */}
              <motion.p
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.15 }}
                className={`text-xs font-semibold ${slide.iconColor} uppercase tracking-[0.14em] mb-2`}
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
