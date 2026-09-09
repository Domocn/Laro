import React, { useState, useEffect } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useAccessibility } from '../context/AccessibilityContext';
import { useTheme } from '../context/ThemeContext';
import { useLanguage } from '../context/LanguageContext';
import { SkipToContent } from './SkipToContent';
import { configApi } from '../lib/api';
import { Button } from './ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from './ui/dropdown-menu';
import {
  ChefHat,
  Home,
  UtensilsCrossed,
  CalendarDays,
  ShoppingCart,
  Refrigerator,
  LogOut,
  Plus,
  Link as LinkIcon,
  Settings,
  Sparkles,
  Moon,
  Sun,
  User,
  Shield,
  Heart,
  Eye,
  Focus,
  Type,
  Contrast,
  BookOpen,
  Package,
  Users,
  LifeBuoy,
} from 'lucide-react';

const NAV_ITEMS = [
  { path: '/dashboard', id: 'home', labelKey: 'navHome', icon: Home },
  { path: '/recipes', id: 'recipes', labelKey: 'navRecipes', icon: UtensilsCrossed },
  { path: '/fridge', id: 'my-fridge', labelKey: 'navMyFridge', icon: Refrigerator },
  { path: '/meal-planner', id: 'meal-plan', labelKey: 'navMealPlan', icon: CalendarDays },
  { path: '/shopping', id: 'shopping', labelKey: 'navShopping', icon: ShoppingCart },
];

export const Layout = ({ children, wide = false, reading = false }) => {
  const { user, household, logout, isAdmin } = useAuth();
  const accessibility = useAccessibility();
  const { theme, setThemeMode } = useTheme();
  const { t } = useLanguage();
  const darkMode = theme === 'dark';
  const navItems = NAV_ITEMS.map((item) => ({ ...item, label: t(item.labelKey) }));
  const location = useLocation();
  const navigate = useNavigate();
  const [version, setVersion] = useState('1.0.0');

  useEffect(() => {
    configApi.getConfig().then(res => {
      if (res.data?.version) setVersion(res.data.version);
    }).catch(() => {});
  }, []);

  const toggleDarkMode = () => {
    setThemeMode(darkMode ? 'light' : 'dark');
  };

  const handleLogout = async () => {
    await logout();
    navigate('/');
  };

  // Get user initials for avatar
  const getInitials = (name) => {
    if (!name) return 'U';
    return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
  };

  return (
    <div className="min-h-screen bg-cream">
      <SkipToContent />
      {/* Header — café nav with whisper triple-layer shadow */}
      <header className="sticky top-0 z-40 bg-white/95 backdrop-blur-md border-b border-black/[0.06] shadow-nav dark:bg-[hsl(160_28%_14%/0.95)] dark:border-white/10">
        <div className="max-w-5xl mx-auto px-4 sm:px-6">
          <div className="flex items-center justify-between h-16 md:h-[72px]">
            {/* Logo */}
            <Link to="/dashboard" className="flex items-center group" data-testid="logo-link">
              <img
                src="/laro-banner.png"
                alt="Laro"
                className="h-11 sm:h-12 transition-opacity duration-200 group-hover:opacity-90"
              />
            </Link>

            {/* Navigation */}
            <nav className="hidden md:flex items-center gap-1" data-a11y-nav>
              {navItems.map((item) => {
                const Icon = item.icon;
                const isActive = location.pathname === item.path;
                return (
                  <Link
                    key={item.path}
                    to={item.path}
                    data-testid={`nav-${item.id}`}
                    data-tour={`nav-${item.id}`}
                    className={`icon-with-label flex items-center gap-1.5 px-3.5 py-2 rounded-full text-[13px] font-medium tracking-wide transition-all duration-200 ${
                      isActive
                        ? 'nav-pill-active'
                        : 'text-foreground/55 hover:text-foreground hover:bg-muted/80'
                    }`}
                  >
                    <Icon className="w-4 h-4" strokeWidth={isActive ? 2.25 : 1.75} />
                    <span className={`icon-label ${accessibility.iconLabels ? 'inline' : 'hidden lg:inline'}`}>
                      {item.label}
                    </span>
                  </Link>
                );
              })}
            </nav>

            {/* Actions */}
            <div className="flex items-center gap-1.5 sm:gap-2">
              {/* Add Recipe Dropdown */}
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button 
                    size="sm" 
                    className="rounded-full bg-laro hover:bg-laro-dark border border-laro shadow-soft icon-with-label h-9 px-4 active:scale-[0.95] transition-transform duration-200"
                    data-testid="add-recipe-trigger"
                  >
                    <Plus className="w-4 h-4" />
                    <span className={`icon-label ml-1 ${accessibility.iconLabels ? 'inline' : 'hidden sm:inline'}`}>
                      {t('add')}
                    </span>
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-48">
                  <DropdownMenuItem onClick={() => navigate('/recipes/quick-add')} data-testid="add-recipe-quick">
                    <Sparkles className="w-4 h-4 mr-2" />
                    {t('pasteAndGo')}
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => navigate('/recipes/new')} data-testid="add-recipe-manual">
                    <Plus className="w-4 h-4 mr-2" />
                    {t('createManually')}
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => navigate('/recipes/import')} data-testid="add-recipe-import">
                    <LinkIcon className="w-4 h-4 mr-2" />
                    {t('importFromUrl')}
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>

              {/* Accessibility Quick Toggle */}
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    variant="ghost"
                    size={accessibility.iconLabels ? 'sm' : 'icon'}
                    className={`rounded-full ${accessibility.iconLabels ? 'h-11 px-3 icon-with-label' : 'w-11 h-11'}`}
                    data-testid="accessibility-menu-trigger"
                    title={t('accessibilitySettings')}
                  >
                    <Heart className="w-5 h-5" />
                    {accessibility.iconLabels && (
                      <span className="icon-label ml-1.5 text-sm">{t('accessShort')}</span>
                    )}
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-64">
                  <div className="px-4 py-3 border-b border-border/60">
                    <p className="font-semibold text-sm flex items-center gap-2">
                      <Heart className="w-4 h-4 text-laro" />
                      {t('accessibility')}
                    </p>
                    <p className="text-xs text-muted-foreground mt-0.5">{t('quickToggles')}</p>
                  </div>

                  <div className="py-1">
                    {/* Focus Mode */}
                    <DropdownMenuItem
                      onClick={() => accessibility.setFocusMode(!accessibility.focusMode)}
                      className="py-2.5 px-4 cursor-pointer"
                    >
                      <Focus className="w-4 h-4 mr-3 text-muted-foreground" />
                      <div className="flex-1">
                        <p className="text-sm">{t('focusMode')}</p>
                        <p className="text-xs text-muted-foreground">{t('reduceDistractions')}</p>
                      </div>
                      <div className={`w-2 h-2 rounded-full ${accessibility.focusMode ? 'bg-laro' : 'bg-muted'}`} />
                    </DropdownMenuItem>

                    {/* Dyslexic Font */}
                    <DropdownMenuItem
                      onClick={() => accessibility.setDyslexicFont(!accessibility.dyslexicFont)}
                      className="py-2.5 px-4 cursor-pointer"
                    >
                      <Type className="w-4 h-4 mr-3 text-muted-foreground" />
                      <div className="flex-1">
                        <p className="text-sm">{t('dyslexicFont')}</p>
                        <p className="text-xs text-muted-foreground">{t('readingSupport')}</p>
                      </div>
                      <div className={`w-2 h-2 rounded-full ${accessibility.dyslexicFont ? 'bg-laro' : 'bg-muted'}`} />
                    </DropdownMenuItem>

                    {/* Reading Ruler */}
                    <DropdownMenuItem
                      onClick={() => accessibility.setReadingRuler(!accessibility.readingRuler)}
                      className="py-2.5 px-4 cursor-pointer"
                    >
                      <Eye className="w-4 h-4 mr-3 text-muted-foreground" />
                      <div className="flex-1">
                        <p className="text-sm">{t('readingRuler')}</p>
                        <p className="text-xs text-muted-foreground">{t('highlightCurrentLine')}</p>
                      </div>
                      <div className={`w-2 h-2 rounded-full ${accessibility.readingRuler ? 'bg-laro' : 'bg-muted'}`} />
                    </DropdownMenuItem>

                    {/* Simplified Mode */}
                    <DropdownMenuItem
                      onClick={() => accessibility.setSimplifiedMode(!accessibility.simplifiedMode)}
                      className="py-2.5 px-4 cursor-pointer"
                    >
                      <Sparkles className="w-4 h-4 mr-3 text-muted-foreground" />
                      <div className="flex-1">
                        <p className="text-sm">{t('simplifiedUi')}</p>
                        <p className="text-xs text-muted-foreground">{t('cleanInterface')}</p>
                      </div>
                      <div className={`w-2 h-2 rounded-full ${accessibility.simplifiedMode ? 'bg-laro' : 'bg-muted'}`} />
                    </DropdownMenuItem>

                    {/* High Contrast */}
                    <DropdownMenuItem
                      onClick={() => {
                        const levels = ['normal', 'high', 'maximum'];
                        const currentIndex = levels.indexOf(accessibility.contrastLevel);
                        const nextIndex = (currentIndex + 1) % levels.length;
                        accessibility.setContrastLevel(levels[nextIndex]);
                      }}
                      className="py-2.5 px-4 cursor-pointer"
                    >
                      <Contrast className="w-4 h-4 mr-3 text-muted-foreground" />
                      <div className="flex-1">
                        <p className="text-sm">{t('contrast')}</p>
                        <p className="text-xs text-muted-foreground">{t(accessibility.contrastLevel)}</p>
                      </div>
                      <div className={`w-2 h-2 rounded-full ${accessibility.contrastLevel !== 'normal' ? 'bg-laro' : 'bg-muted'}`} />
                    </DropdownMenuItem>
                  </div>

                  <DropdownMenuSeparator className="my-0" />

                  {/* Link to full settings */}
                  <DropdownMenuItem
                    onClick={() => navigate('/settings/preferences')}
                    className="py-2.5 px-4 cursor-pointer"
                  >
                    <Settings className="w-4 h-4 mr-3 text-muted-foreground" />
                    <span className="text-sm">{t('allAccessibilitySettings')}</span>
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>

              {/* User Menu */}
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button 
                    variant="ghost" 
                    size="icon" 
                    className="rounded-full w-10 h-10 bg-laro-light/80 ring-1 ring-laro/15 hover:bg-laro-light"
                    data-testid="user-menu-trigger"
                    data-tour="nav-settings"
                  >
                    <User className="w-5 h-5 text-laro-dark" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-64 p-0">
                  {/* User Profile Header */}
                  <div className="px-4 py-3 border-b border-border/60">
                    <p className="font-semibold text-sm">{user?.name}</p>
                    <p className="text-xs text-muted-foreground">{user?.email}</p>
                    {household && (
                      <p className="text-xs text-laro mt-1">{household.name}</p>
                    )}
                  </div>

                  <div className="py-1">
                    {/* Theme — quick toggle stays in the menu */}
                    <DropdownMenuItem onClick={toggleDarkMode} className="py-2.5 px-4 cursor-pointer" data-testid="menu-theme">
                      {darkMode ? (
                        <Sun className="w-4 h-4 mr-3 text-muted-foreground" />
                      ) : (
                        <Moon className="w-4 h-4 mr-3 text-muted-foreground" />
                      )}
                      <div>
                        <p className="text-sm">{t('theme')}</p>
                        <p className="text-xs text-muted-foreground">{darkMode ? t('dark') : t('light')}</p>
                      </div>
                    </DropdownMenuItem>

                    <DropdownMenuItem onClick={() => navigate('/friends')} className="py-2.5 px-4 cursor-pointer" data-testid="menu-friends">
                      <Users className="w-4 h-4 mr-3 text-muted-foreground" />
                      <div>
                        <p className="text-sm">{t('friends')}</p>
                        <p className="text-xs text-muted-foreground">{t('friendsDesc')}</p>
                      </div>
                    </DropdownMenuItem>

                    {/* Single Settings hub — prefs/security live inside */}
                    <DropdownMenuItem
                      onClick={() => navigate('/settings')}
                      className="py-2.5 px-4 cursor-pointer"
                      data-testid="menu-settings"
                    >
                      <Settings className="w-4 h-4 mr-3 text-muted-foreground" />
                      <div>
                        <p className="text-sm">{t('settings')}</p>
                        <p className="text-xs text-muted-foreground">{t('settingsDesc')}</p>
                      </div>
                    </DropdownMenuItem>

                    <DropdownMenuItem
                      onClick={() => navigate('/support')}
                      className="py-2.5 px-4 cursor-pointer"
                      data-testid="menu-support"
                    >
                      <LifeBuoy className="w-4 h-4 mr-3 text-muted-foreground" />
                      <div>
                        <p className="text-sm">{t('helpSupport')}</p>
                        <p className="text-xs text-muted-foreground">{t('helpSupportDesc')}</p>
                      </div>
                    </DropdownMenuItem>

                    {isAdmin && (
                      <DropdownMenuItem onClick={() => navigate('/admin')} className="py-2.5 px-4 cursor-pointer" data-testid="menu-admin">
                        <Shield className="w-4 h-4 mr-3 text-laro" />
                        <div>
                          <p className="text-sm text-laro font-medium">{t('admin')}</p>
                          <p className="text-xs text-muted-foreground">{t('adminDesc')}</p>
                        </div>
                      </DropdownMenuItem>
                    )}
                  </div>

                  <DropdownMenuSeparator className="my-0" />

                  {/* Logout */}
                  <DropdownMenuItem onClick={handleLogout} className="py-2.5 px-4 cursor-pointer text-coral hover:text-coral" data-testid="menu-logout">
                    <LogOut className="w-4 h-4 mr-3" />
                    <span className="text-sm">{t('logout')}</span>
                  </DropdownMenuItem>

                  {/* Version Footer */}
                  <div className="px-4 py-2 border-t border-border/60">
                    <p className="text-xs text-muted-foreground text-right">v{version}</p>
                  </div>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </div>
        </div>

        {/* Mobile Navigation */}
        <div className="md:hidden border-t border-border/40 overflow-x-auto" data-a11y-nav>
          <div className="flex justify-around py-1 min-w-0">
            {navItems.slice(0, 5).map((item) => {
              const Icon = item.icon;
              const isActive = location.pathname === item.path;
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  data-testid={`nav-mobile-${item.id}`}
                  data-tour={`nav-${item.id}`}
                  className={`flex flex-col items-center justify-center min-w-[44px] min-h-[44px] px-1.5 py-1.5 rounded-xl transition-colors shrink-0 ${
                    isActive ? 'text-laro-dark bg-laro-light/70' : 'text-muted-foreground'
                  }`}
                >
                  <Icon className="w-5 h-5" strokeWidth={isActive ? 2.25 : 1.75} />
                  <span className="text-[10px] font-medium mt-0.5 tracking-wide">{item.label}</span>
                </Link>
              );
            })}
          </div>
        </div>
      </header>

      {/* Main Content — pages can opt into wider (boards) or reading (agenda) width */}
      <main
        id="main-content"
        className={`${
          reading ? 'max-w-3xl' : wide ? 'max-w-7xl' : 'max-w-5xl'
        } mx-auto px-4 sm:px-6 py-8 min-w-0 max-w-full overflow-x-hidden`}
        tabIndex={-1}
      >
        {children}
      </main>
    </div>
  );
};
