import React, { useState, useEffect } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useAccessibility } from '../context/AccessibilityContext';
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
  Globe,
  Moon,
  Sun,
  User,
  Shield,
  Lock,
  Heart,
  Eye,
  Focus,
  Type,
  Contrast,
  BookOpen,
  Package
} from 'lucide-react';

const navItems = [
  { path: '/dashboard', label: 'Home', icon: Home, activeColor: 'text-laro', activeBg: 'bg-laro-light' },
  { path: '/recipes', label: 'Recipes', icon: UtensilsCrossed, activeColor: 'text-coral', activeBg: 'bg-coral-light' },
  { path: '/fridge', label: 'My Fridge', icon: Refrigerator, activeColor: 'text-emerald-600', activeBg: 'bg-emerald-100' },
  { path: '/meal-planner', label: 'Meal Plan', icon: CalendarDays, activeColor: 'text-teal', activeBg: 'bg-teal-light' },
  { path: '/shopping', label: 'Shopping', icon: ShoppingCart, activeColor: 'text-tangerine', activeBg: 'bg-tangerine-light' },
];

export const Layout = ({ children }) => {
  const { user, household, logout, isAdmin } = useAuth();
  const accessibility = useAccessibility();
  const location = useLocation();
  const navigate = useNavigate();
  const [version, setVersion] = useState('1.0.0');
  const [darkMode, setDarkMode] = useState(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('laro_dark_mode');
      if (saved !== null) return saved === 'true';
      return window.matchMedia('(prefers-color-scheme: dark)').matches;
    }
    return false;
  });

  useEffect(() => {
    configApi.getConfig().then(res => {
      if (res.data?.version) setVersion(res.data.version);
    }).catch(() => {});
  }, []);

  const toggleDarkMode = () => {
    const newMode = !darkMode;
    setDarkMode(newMode);
    localStorage.setItem('laro_dark_mode', String(newMode));
    if (newMode) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
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
    <div className="min-h-screen bg-background">
      <SkipToContent />
      {/* Header */}
      <header className="sticky top-0 z-40 glass border-b border-border/40">
        <div className="max-w-5xl mx-auto px-4 sm:px-6">
          <div className="flex items-center justify-between h-14">
            {/* Logo */}
            <Link to="/dashboard" className="flex items-center group" data-testid="logo-link">
              <img
                src="/laro-banner.png"
                alt="Laro"
                className="h-14 group-hover:scale-105 transition-transform"
              />
            </Link>

            {/* Navigation */}
            <nav className="hidden md:flex items-center gap-0.5">
              {navItems.map((item) => {
                const Icon = item.icon;
                const isActive = location.pathname === item.path;
                return (
                  <Link
                    key={item.path}
                    to={item.path}
                    data-testid={`nav-${item.label.toLowerCase().replace(' ', '-')}`}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium transition-all duration-200 ${
                      isActive
                        ? `${item.activeBg} ${item.activeColor} shadow-sm`
                        : 'text-foreground/70 hover:text-foreground hover:bg-muted'
                    }`}
                  >
                    <Icon className="w-4 h-4" />
                    <span className="hidden lg:inline">{item.label}</span>
                  </Link>
                );
              })}
            </nav>

            {/* Actions */}
            <div className="flex items-center gap-2">
              {/* Add Recipe Dropdown */}
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button 
                    size="sm" 
                    className="rounded-full bg-laro hover:bg-laro-dark shadow-sm"
                    data-testid="add-recipe-trigger"
                  >
                    <Plus className="w-4 h-4" />
                    <span className="hidden sm:inline ml-1">Add</span>
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-48">
                  <DropdownMenuItem onClick={() => navigate('/recipes/quick-add')} data-testid="add-recipe-quick">
                    <Sparkles className="w-4 h-4 mr-2" />
                    Paste & Go
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => navigate('/recipes/new')} data-testid="add-recipe-manual">
                    <Plus className="w-4 h-4 mr-2" />
                    Create Manually
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => navigate('/recipes/import')} data-testid="add-recipe-import">
                    <LinkIcon className="w-4 h-4 mr-2" />
                    Import from URL
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>

              {/* Accessibility Quick Toggle */}
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="rounded-full w-11 h-11"
                    data-testid="accessibility-menu-trigger"
                    title="Accessibility Settings"
                  >
                    <Heart className="w-5 h-5" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-64">
                  <div className="px-4 py-3 border-b border-border/60">
                    <p className="font-semibold text-sm flex items-center gap-2">
                      <Heart className="w-4 h-4 text-laro" />
                      Accessibility
                    </p>
                    <p className="text-xs text-muted-foreground mt-0.5">Quick toggles</p>
                  </div>

                  <div className="py-1">
                    {/* Focus Mode */}
                    <DropdownMenuItem
                      onClick={() => accessibility.setFocusMode(!accessibility.focusMode)}
                      className="py-2.5 px-4 cursor-pointer"
                    >
                      <Focus className="w-4 h-4 mr-3 text-muted-foreground" />
                      <div className="flex-1">
                        <p className="text-sm">Focus Mode</p>
                        <p className="text-xs text-muted-foreground">Reduce distractions</p>
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
                        <p className="text-sm">Dyslexic Font</p>
                        <p className="text-xs text-muted-foreground">Reading support</p>
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
                        <p className="text-sm">Reading Ruler</p>
                        <p className="text-xs text-muted-foreground">Highlight current line</p>
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
                        <p className="text-sm">Simplified UI</p>
                        <p className="text-xs text-muted-foreground">Clean interface</p>
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
                        <p className="text-sm">Contrast</p>
                        <p className="text-xs text-muted-foreground capitalize">{accessibility.contrastLevel}</p>
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
                    <span className="text-sm">All accessibility settings</span>
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>

              {/* User Menu */}
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button 
                    variant="ghost" 
                    size="icon" 
                    className="rounded-full w-11 h-11 bg-laro-light"
                    data-testid="user-menu-trigger"
                  >
                    <User className="w-5 h-5 text-laro" />
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
                    {/* Language (placeholder for future) */}
                    <DropdownMenuItem className="py-2.5 px-4 cursor-pointer">
                      <Globe className="w-4 h-4 mr-3 text-muted-foreground" />
                      <div>
                        <p className="text-sm">Language</p>
                        <p className="text-xs text-muted-foreground">English</p>
                      </div>
                    </DropdownMenuItem>

                    {/* Theme Toggle */}
                    <DropdownMenuItem onClick={toggleDarkMode} className="py-2.5 px-4 cursor-pointer">
                      {darkMode ? (
                        <Sun className="w-4 h-4 mr-3 text-muted-foreground" />
                      ) : (
                        <Moon className="w-4 h-4 mr-3 text-muted-foreground" />
                      )}
                      <div>
                        <p className="text-sm">Theme</p>
                        <p className="text-xs text-muted-foreground">{darkMode ? 'Dark' : 'Light'}</p>
                      </div>
                    </DropdownMenuItem>

                    {/* Settings */}
                    <DropdownMenuItem onClick={() => navigate('/settings')} className="py-2.5 px-4 cursor-pointer" data-testid="menu-settings">
                      <Settings className="w-4 h-4 mr-3 text-muted-foreground" />
                      <div>
                        <p className="text-sm">Settings</p>
                        <p className="text-xs text-muted-foreground">Manage your account</p>
                      </div>
                    </DropdownMenuItem>

                    {/* Preferences */}
                    <DropdownMenuItem onClick={() => navigate('/settings/preferences')} className="py-2.5 px-4 cursor-pointer" data-testid="menu-preferences">
                      <Sparkles className="w-4 h-4 mr-3 text-muted-foreground" />
                      <div>
                        <p className="text-sm">Preferences</p>
                        <p className="text-xs text-muted-foreground">Customize your experience</p>
                      </div>
                    </DropdownMenuItem>

                    {/* Security Settings */}
                    <DropdownMenuItem onClick={() => navigate('/settings/security')} className="py-2.5 px-4 cursor-pointer" data-testid="menu-security">
                      <Lock className="w-4 h-4 mr-3 text-muted-foreground" />
                      <div>
                        <p className="text-sm">Security</p>
                        <p className="text-xs text-muted-foreground">Password, 2FA, sessions</p>
                      </div>
                    </DropdownMenuItem>

                    {/* Admin Dashboard - Only for admins */}
                    {isAdmin && (
                      <DropdownMenuItem onClick={() => navigate('/admin')} className="py-2.5 px-4 cursor-pointer" data-testid="menu-admin">
                        <Shield className="w-4 h-4 mr-3 text-laro" />
                        <div>
                          <p className="text-sm text-laro font-medium">Admin Dashboard</p>
                          <p className="text-xs text-muted-foreground">Manage users & settings</p>
                        </div>
                      </DropdownMenuItem>
                    )}
                  </div>

                  <DropdownMenuSeparator className="my-0" />

                  {/* Logout */}
                  <DropdownMenuItem onClick={handleLogout} className="py-2.5 px-4 cursor-pointer text-coral hover:text-coral" data-testid="menu-logout">
                    <LogOut className="w-4 h-4 mr-3" />
                    <span className="text-sm">Logout</span>
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
        <div className="md:hidden border-t border-border/40">
          <div className="flex justify-around py-1.5">
            {navItems.slice(0, 5).map((item) => {
              const Icon = item.icon;
              const isActive = location.pathname === item.path;
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`flex flex-col items-center justify-center min-w-[44px] min-h-[44px] p-2 rounded-lg transition-colors ${
                    isActive ? item.activeColor : 'text-muted-foreground'
                  }`}
                >
                  <Icon className="w-5 h-5" />
                  <span className="text-xs mt-0.5">{item.label}</span>
                </Link>
              );
            })}
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main id="main-content" className="max-w-5xl mx-auto px-4 sm:px-6 py-6" tabIndex={-1}>
        {children}
      </main>
    </div>
  );
};
