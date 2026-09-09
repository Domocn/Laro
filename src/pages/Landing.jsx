import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Button } from '../components/ui/button';
import { FeatureWalkthrough } from '../components/FeatureWalkthrough';
import { useLanguage } from '../context/LanguageContext';
import {
  ArrowRight,
  Github,
  Play,
  Focus,
  Flame,
  Refrigerator,
  Smartphone,
  Link2,
  CalendarDays,
  ShoppingCart,
  Home,
  Users,
  Server,
} from 'lucide-react';

export const Landing = () => {
  const { t } = useLanguage();
  const navigate = useNavigate();
  const [showWalkthrough, setShowWalkthrough] = useState(false);

  useEffect(() => {
    const hasSeenWalkthrough = localStorage.getItem('laro_walkthrough_seen');
    if (!hasSeenWalkthrough) {
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
      <header className="absolute top-0 inset-x-0 z-20">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 pt-4 sm:pt-5">
          <div className="flex items-center justify-between h-14 px-3 sm:px-4 rounded-[12px] bg-cream/80 backdrop-blur-md border border-black/[0.06] shadow-nav">
            <Link to="/" className="flex items-center shrink-0" aria-label={t('laroHome')}>
              <img
                src="/laro-banner.png"
                alt="Laro"
                className="h-8 sm:h-9"
              />
            </Link>
            <div className="flex items-center gap-1 sm:gap-2">
              <Link to="/login">
                <Button
                  variant="outline"
                  className="rounded-full h-9 px-3.5 text-sm border-foreground/87 text-foreground"
                  data-testid="login-btn"
                >
                  {t('signIn')}
                </Button>
              </Link>
              <Link to="/register">
                <Button
                  variant="black"
                  className="rounded-full h-9 px-4 text-sm"
                  data-testid="register-btn"
                >
                  {t('startFree')}
                </Button>
              </Link>
            </div>
          </div>
        </div>
      </header>

      {/* Hero: brand + one promise */}
      <section className="relative min-h-[100svh] flex items-end sm:items-center">
        {/* High-res photo (was 400px and pixelated on retina — especially the iPad in the old stock) */}
        <img
          src="/images/hero-kitchen.jpg"
          alt=""
          aria-hidden="true"
          fetchPriority="high"
          decoding="async"
          className="absolute inset-0 h-full w-full object-cover object-center scale-[1.02]"
        />
        <div
          className="absolute inset-0"
          style={{
            background:
              'linear-gradient(115deg, rgba(242,240,235,0.97) 0%, rgba(242,240,235,0.90) 38%, rgba(242,240,235,0.35) 68%, rgba(30,57,50,0.22) 100%)',
          }}
          aria-hidden="true"
        />

        <div className="relative z-10 w-full max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 pt-28 pb-16 sm:py-28">
          <motion.div
            initial={{ opacity: 0, y: 18 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.65, ease: [0.22, 1, 0.36, 1] }}
            className="max-w-xl"
          >
            <p className="font-accent text-laro-brand text-2xl sm:text-3xl font-semibold tracking-tighter mb-4">
              {t('brandName')}
            </p>
            <h1 className="font-heading text-4xl sm:text-5xl lg:text-[3.65rem] font-semibold text-laro-brand leading-[1.15] tracking-tighter">
              {t('heroHeadline')}
            </h1>
            <p className="mt-5 text-lg text-foreground/70 max-w-md leading-relaxed tracking-tight">
              {t('heroSubcopy')}
            </p>
            <div className="mt-9 flex flex-wrap items-center gap-3">
              <Link to="/register">
                <Button
                  size="lg"
                  className="rounded-full px-8 h-12 text-[15px]"
                  data-testid="hero-get-started"
                >
                  {t('startCookingCalmer')}
                  <ArrowRight className="w-4 h-4 ml-2" />
                </Button>
              </Link>
              <button
                type="button"
                onClick={() => setShowWalkthrough(true)}
                className="inline-flex items-center gap-2 px-4 py-2.5 text-sm font-semibold text-laro tracking-tight hover:text-laro-dark transition-colors"
              >
                <Play className="w-4 h-4" />
                {t('seeHowItWorks')}
              </button>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Trust strip: ceramic band */}
      <section className="relative bg-cream-subtle border-y border-black/[0.06]">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-10">
          <ul className="grid grid-cols-1 sm:grid-cols-3">
            <li className="px-0 sm:px-8 sm:pl-0 py-5 sm:py-1 text-center sm:text-left border-b sm:border-b-0 sm:border-r border-[#cfd8d2]">
              <p className="font-heading text-[13px] font-semibold text-laro-dark tracking-[0.08em] uppercase">
                {t('trustYourRecipes')}
              </p>
              <p className="mt-2.5 text-sm text-foreground/65 leading-relaxed">
                {t('trustYourRecipesDesc')}
              </p>
            </li>
            <li className="px-0 sm:px-8 py-5 sm:py-1 text-center sm:text-left border-b sm:border-b-0 sm:border-r border-[#cfd8d2]">
              <p className="font-heading text-[13px] font-semibold text-laro-dark tracking-[0.08em] uppercase">
                {t('trustPrivate')}
              </p>
              <p className="mt-2.5 text-sm text-foreground/65 leading-relaxed">
                {t('trustPrivateDesc')}
              </p>
            </li>
            <li className="px-0 sm:px-8 sm:pr-0 py-5 sm:py-1 text-center sm:text-left">
              <p className="font-heading text-[13px] font-semibold text-laro-dark tracking-[0.08em] uppercase">
                {t('trustOpen')}
              </p>
              <p className="mt-2.5 text-sm text-foreground/65 leading-relaxed">
                {t('trustOpenDesc')}
              </p>
            </li>
          </ul>
        </div>
      </section>

      {/* Why it feels different */}
      <section className="relative py-20 sm:py-28">
        <div className="absolute inset-0 bg-gradient-to-b from-cream via-background to-background pointer-events-none" />
        <div className="relative max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid lg:grid-cols-2 gap-12 lg:gap-16 items-center">
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-80px' }}
              transition={{ duration: 0.45 }}
            >
              <Focus className="w-8 h-8 text-teal mb-4" aria-hidden="true" />
              <h2 className="font-heading text-3xl sm:text-4xl font-semibold text-foreground tracking-tighter leading-tight">
                {t('designedForWeeknights')}
              </h2>
              <p className="mt-4 text-muted-foreground text-lg leading-relaxed max-w-md">
                {t('designedForWeeknightsBody')}
              </p>
            </motion.div>
            <motion.div
              initial={{ opacity: 0, scale: 0.98 }}
              whileInView={{ opacity: 1, scale: 1 }}
              viewport={{ once: true, margin: '-80px' }}
              transition={{ duration: 0.5 }}
              className="relative aspect-[4/3] overflow-hidden"
            >
              <img
                src="/images/dish-plated.jpg"
                alt="A calm finished home-cooked dish"
                className="w-full h-full object-cover"
                loading="lazy"
                decoding="async"
              />
            </motion.div>
          </div>
        </div>
      </section>

      {/* How: Cook Mode — House Green feature band */}
      <section className="py-20 sm:py-28 bg-laro-house text-white">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid lg:grid-cols-2 gap-12 lg:gap-16 items-center">
            <motion.div
              initial={{ opacity: 0, scale: 0.98 }}
              whileInView={{ opacity: 1, scale: 1 }}
              viewport={{ once: true, margin: '-80px' }}
              transition={{ duration: 0.5 }}
              className="relative aspect-[4/3] overflow-hidden order-2 lg:order-1 rounded-[12px]"
            >
              <img
                src="/images/hero-kitchen.jpg"
                alt="Cooking at the hob with focus"
                className="w-full h-full object-cover"
                loading="lazy"
                decoding="async"
              />
            </motion.div>
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-80px' }}
              transition={{ duration: 0.45 }}
              className="order-1 lg:order-2"
            >
              <Flame className="w-8 h-8 text-laro-gold mb-4" aria-hidden="true" />
              <h2 className="font-heading text-3xl sm:text-4xl font-semibold leading-tight tracking-tighter text-white">
                {t('cookModeHandsFull')}
              </h2>
              <p className="mt-4 text-white/70 text-lg leading-relaxed max-w-md tracking-tight">
                {t('cookModeHandsFullBody')}
              </p>
            </motion.div>
          </div>
        </div>
      </section>

      {/* When: fridge decides for you */}
      <section className="py-20 sm:py-28">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid lg:grid-cols-2 gap-12 lg:gap-16 items-center">
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-80px' }}
              transition={{ duration: 0.45 }}
            >
              <Refrigerator className="w-8 h-8 text-coral mb-4" aria-hidden="true" />
              <h2 className="font-heading text-3xl sm:text-4xl font-bold text-foreground leading-tight">
                {t('startFromFridge')}
              </h2>
              <p className="mt-4 text-muted-foreground text-lg leading-relaxed max-w-md">
                {t('startFromFridgeBody')}
              </p>
            </motion.div>
            <motion.div
              initial={{ opacity: 0, scale: 0.98 }}
              whileInView={{ opacity: 1, scale: 1 }}
              viewport={{ once: true, margin: '-80px' }}
              transition={{ duration: 0.5 }}
              className="relative aspect-[4/3] overflow-hidden"
            >
              <img
                src="/images/produce-fresh.jpg"
                alt="Simple ingredients already at home"
                className="w-full h-full object-cover"
                loading="lazy"
                decoding="async"
              />
            </motion.div>
          </div>
        </div>
      </section>

      {/* Where: Android */}
      <section className="py-20 sm:py-28 bg-cream">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid lg:grid-cols-2 gap-12 lg:gap-16 items-center">
            <motion.div
              initial={{ opacity: 0, scale: 0.98 }}
              whileInView={{ opacity: 1, scale: 1 }}
              viewport={{ once: true, margin: '-80px' }}
              transition={{ duration: 0.5 }}
              className="relative aspect-[4/3] overflow-hidden order-2 lg:order-1"
            >
              <img
                src="/images/pantry-ingredients.jpg"
                alt="Phone-ready kitchen ingredients"
                className="w-full h-full object-cover"
                loading="lazy"
                decoding="async"
              />
            </motion.div>
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-80px' }}
              transition={{ duration: 0.45 }}
              className="order-1 lg:order-2"
            >
              <Smartphone className="w-8 h-8 text-teal mb-4" aria-hidden="true" />
              <h2 className="font-heading text-3xl sm:text-4xl font-bold text-foreground leading-tight">
                {t('webAndPhone')}
              </h2>
              <p className="mt-4 text-muted-foreground text-lg leading-relaxed max-w-md">
                {t('webAndPhoneBody')}
              </p>
              <a
                href="https://play.google.com/store/apps/details?id=com.laro.app"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center mt-6 text-laro font-medium hover:text-laro-dark transition-colors"
              >
                {t('getOnGooglePlay')}
                <ArrowRight className="w-4 h-4 ml-1" />
              </a>
            </motion.div>
          </div>
        </div>
      </section>

      {/* How: get food in + plan the week */}
      <section className="py-20 sm:py-28">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid lg:grid-cols-2 gap-12 lg:gap-16 items-center">
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-80px' }}
              transition={{ duration: 0.45 }}
            >
              <Link2 className="w-8 h-8 text-laro mb-4" aria-hidden="true" />
              <h2 className="font-heading text-3xl sm:text-4xl font-bold text-foreground leading-tight">
                {t('youAddRecipes')}
              </h2>
              <p className="mt-4 text-muted-foreground text-lg leading-relaxed max-w-md">
                {t('youAddRecipesBody')}
              </p>
            </motion.div>
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-80px' }}
              transition={{ duration: 0.45, delay: 0.05 }}
              className="space-y-8"
            >
              <div>
                <CalendarDays className="w-7 h-7 text-tangerine mb-3" aria-hidden="true" />
                <h3 className="font-heading text-xl font-semibold text-foreground">
                  {t('planOnceCoast')}
                </h3>
                <p className="mt-2 text-muted-foreground leading-relaxed max-w-md">
                  {t('planOnceCoastBody')}
                </p>
              </div>
              <div>
                <ShoppingCart className="w-7 h-7 text-coral mb-3" aria-hidden="true" />
                <h3 className="font-heading text-xl font-semibold text-foreground">
                  {t('oneShoppingList')}
                </h3>
                <p className="mt-2 text-muted-foreground leading-relaxed max-w-md">
                  {t('oneShoppingListBody')}
                </p>
              </div>
            </motion.div>
          </div>
        </div>
      </section>

      {/* Who with you + smart home — House Green band */}
      <section className="py-20 sm:py-28 bg-laro-house text-white">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid lg:grid-cols-2 gap-12 lg:gap-16">
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-80px' }}
              transition={{ duration: 0.45 }}
            >
              <Users className="w-8 h-8 text-laro-gold mb-4" aria-hidden="true" />
              <h2 className="font-heading text-3xl sm:text-4xl font-semibold leading-tight tracking-tighter text-white">
                {t('oneHousehold')}
              </h2>
              <p className="mt-4 text-white/70 text-lg leading-relaxed max-w-md tracking-tight">
                {t('oneHouseholdBody')}
              </p>
            </motion.div>
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-80px' }}
              transition={{ duration: 0.45, delay: 0.05 }}
            >
              <Home className="w-8 h-8 text-white/80 mb-4" aria-hidden="true" />
              <h2 className="font-heading text-3xl sm:text-4xl font-semibold leading-tight tracking-tighter text-white">
                {t('optionalHomeAssistant')}
              </h2>
              <p className="mt-4 text-white/70 text-lg leading-relaxed max-w-md tracking-tight">
                {t('optionalHomeAssistantBody')}
              </p>
            </motion.div>
          </div>
        </div>
      </section>

      {/* Offer / close the sale */}
      <section className="py-20 sm:py-24 border-t border-black/[0.06] bg-cream">
        <div className="max-w-2xl mx-auto px-4 sm:px-6 text-center">
          <Server className="w-7 h-7 text-laro mx-auto mb-5" aria-hidden="true" />
          <h2 className="font-heading text-2xl sm:text-3xl font-semibold text-laro-brand tracking-tighter">
            {t('freeToStart')}
          </h2>
          <p className="mt-4 text-muted-foreground leading-relaxed tracking-tight">
            {t('freeToStartBody')}
          </p>
          <div className="mt-9 flex flex-wrap justify-center gap-3">
            <Link to="/register">
              <Button className="rounded-full px-7 h-11" data-testid="cta-get-started">
                {t('createFreeKitchen')}
              </Button>
            </Link>
            <a
              href="https://github.com/Domocn/Laro"
              target="_blank"
              rel="noopener noreferrer"
            >
              <Button variant="outline" className="rounded-full px-7 h-11">
                <Github className="w-4 h-4 mr-2" />
                {t('selfHostOnGithub')}
              </Button>
            </a>
          </div>
        </div>
      </section>

      <footer className="bg-laro-house text-white/70">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-10 sm:py-12">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-6">
            <div className="flex items-center gap-3 justify-center sm:justify-start">
              <img src="/laro-icon.png" alt="" className="w-7 h-7 rounded-md" />
              <div>
                <p className="font-heading text-[#f4f6f4] font-semibold tracking-tight leading-none">{t('brandName')}</p>
                <p className="mt-1 text-xs text-[#8fa898]">{t('brandPromise')}</p>
              </div>
            </div>
            <nav className="flex flex-wrap items-center justify-center sm:justify-end gap-x-6 gap-y-2 text-sm">
              <Link to="/privacy-policy" className="hover:text-[#f4f6f4] transition-colors">
                {t('privacy')}
              </Link>
              <a
                href="https://play.google.com/store/apps/details?id=com.laro.app"
                target="_blank"
                rel="noopener noreferrer"
                className="hover:text-[#f4f6f4] transition-colors"
              >
                {t('android')}
              </a>
              <a
                href="https://github.com/Domocn/Laro"
                target="_blank"
                rel="noopener noreferrer"
                className="hover:text-[#f4f6f4] transition-colors"
              >
                {t('github')}
              </a>
              <Link to="/login" className="hover:text-[#f4f6f4] transition-colors">
                {t('signIn')}
              </Link>
            </nav>
          </div>
          <div className="mt-8 pt-6 border-t border-white/10 flex flex-col sm:flex-row items-center justify-between gap-2 text-xs text-[#7a9182]">
            <p>© {new Date().getFullYear()} {t('brandName')}</p>
            <p>{t('mitLicensedFooter')}</p>
          </div>
        </div>
      </footer>
    </div>
  );
};
