import React, { useState, useEffect } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { useAuth } from '../context/AuthContext';
import { useAccessibility } from '../context/AccessibilityContext';
import { configApi } from '../lib/api';
import { Button } from './ui/button';
import { useIsMobile } from '../hooks/use-mobile';
import { cn } from '../lib/utils';
import {
  Home,
  UtensilsCrossed,
  CalendarDays,
  ShoppingCart,
  Refrigerator,
  Plus,
  Settings,
  User,
  Search,
  ChevronLeft,
  Bell,
  Menu,
  LogOut,
  Sparkles,
  Link as LinkIcon
} from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from './ui/dropdown-menu';

const navItems = [
  { path: '/dashboard', label: 'Home', icon: Home },
  { path: '/recipes', label: 'Recipes', icon: UtensilsCrossed },
  { path: '/meal-planner', label: 'Plan', icon: CalendarDays },
  { path: '/shopping', label: 'Shop', icon: ShoppingCart },
  { path: '/fridge', label: 'Fridge', icon: Refrigerator },
];

export const Layout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user, logout, isAdmin } = useAuth() as any;
  const location = useLocation();
  const navigate = useNavigate();
  const isMobile = useIsMobile();
  const [version, setVersion] = useState('1.0.0');
  
  const currentPath = location.pathname;
  const isDetailPage = currentPath.includes('/recipes/') && currentPath !== '/recipes';
  const showBackButton = isDetailPage || currentPath.startsWith('/settings/') || currentPath === '/recipes/new';

  useEffect(() => {
    configApi.getConfig().then(res => {
      if (res.data?.version) setVersion(res.data.version);
    }).catch(() => {});
  }, []);

  const getPageTitle = () => {
    if (currentPath === '/dashboard') return 'Laro';
    if (currentPath === '/recipes') return 'Recipes';
    if (currentPath === '/meal-planner') return 'Meal Plan';
    if (currentPath === '/shopping') return 'Shopping';
    if (currentPath === '/fridge') return 'Pantry';
    if (currentPath.startsWith('/settings')) return 'Settings';
    if (currentPath === '/recipes/new') return 'New Recipe';
    return 'Laro';
  };

  const handleLogout = async () => {
    await logout();
    navigate('/');
  };

  return (
    <div className="min-h-screen bg-background flex flex-col font-sans antialiased selection:bg-primary/30">
      {/* Desktop Navigation */}
      <header className="hidden md:flex sticky top-0 z-40 glass border-b border-border/40 h-16 items-center px-6">
        <div className="max-w-7xl mx-auto w-full flex items-center justify-between">
          <Link to="/dashboard" className="flex items-center gap-2">
            <img src="/mise-banner.svg" alt="Laro" className="h-10" />
          </Link>

          <nav className="flex items-center gap-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = currentPath === item.path;
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  className={cn(
                    "flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium transition-all duration-200",
                    isActive 
                      ? "bg-primary text-primary-foreground shadow-md" 
                      : "text-foreground/70 hover:text-foreground hover:bg-muted"
                  )}
                >
                  <Icon className="w-4 h-4" />
                  <span>{item.label}</span>
                </Link>
              );
            })}
          </nav>

          <div className="flex items-center gap-2">
            <Button 
              size="sm" 
              className="rounded-full bg-laro hover:bg-laro-dark"
              onClick={() => navigate('/recipes/new')}
            >
              <Plus className="w-4 h-4 mr-1" />
              Add
            </Button>
            
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon" className="rounded-full">
                  <User className="w-5 h-5" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56">
                <DropdownMenuItem onClick={() => navigate('/settings')}>Settings</DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={handleLogout} className="text-destructive">Logout</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </header>

      {/* Mobile Top App Bar (Material 3 Style) */}
      <header className="md:hidden sticky top-0 z-50 bg-background/95 backdrop-blur-sm h-16 flex items-center px-4 pt-safe">
        <div className="flex items-center w-full">
          {showBackButton ? (
            <Button
              variant="ghost"
              size="icon"
              className="mr-2 rounded-full active:bg-muted transition-colors ripple"
              onClick={() => navigate(-1)}
            >
              <ChevronLeft className="w-6 h-6" />
            </Button>
          ) : (
            <div className="mr-3">
               <img src="/laro-icon.png" alt="Laro" className="w-8 h-8 rounded-lg" />
            </div>
          )}
          
          <h1 className="text-xl font-medium flex-1 truncate">
            {getPageTitle()}
          </h1>

          <div className="flex items-center">
            <Button variant="ghost" size="icon" className="rounded-full ripple">
              <Search className="w-6 h-6" />
            </Button>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon" className="rounded-full ripple">
                  <Menu className="w-6 h-6" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56 rounded-2xl p-2 mt-2">
                <DropdownMenuItem onClick={() => navigate('/settings')} className="rounded-xl py-3">
                   <Settings className="w-5 h-5 mr-3" />
                   Settings
                </DropdownMenuItem>
                <DropdownMenuItem onClick={handleLogout} className="rounded-xl py-3 text-destructive">
                   <LogOut className="w-5 h-5 mr-3" />
                   Logout
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <div className="px-2 py-1.5 text-xs text-muted-foreground text-center">
                   v{version} Beta
                </div>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className={cn(
        "flex-1 w-full max-w-7xl mx-auto px-4 md:px-6 py-4 md:py-8",
        isMobile && "pb-24"
      )}>
        <AnimatePresence mode="wait">
          <motion.div
            key={location.pathname}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.2, ease: [0.4, 0, 0.2, 1] }}
          >
            {children}
          </motion.div>
        </AnimatePresence>
      </main>

      {/* Mobile Bottom Navigation (Material 3 Style) */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 z-50 bg-surface-container-low border-t border-border/10 pb-safe">
        <div className="flex justify-around items-center h-16">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = currentPath === item.path;
            return (
              <Link
                key={item.path}
                to={item.path}
                className="relative flex flex-col items-center flex-1 py-1"
                onClick={() => {
                  if (window.navigator.vibrate) window.navigator.vibrate(5);
                }}
              >
                <div className={cn(
                  "relative px-5 py-1 rounded-full transition-all duration-300",
                  isActive ? "bg-primary/20 text-primary" : "text-muted-foreground"
                )}>
                  <Icon className={cn(
                    "w-6 h-6 transition-transform duration-300",
                    isActive ? "scale-110" : "scale-100"
                  )} />
                </div>
                <span className={cn(
                  "text-[10px] mt-1 font-medium tracking-wide transition-colors duration-300",
                  isActive ? "text-primary" : "text-muted-foreground"
                )}>
                  {item.label}
                </span>
              </Link>
            );
          })}
        </div>
      </nav>

      {/* FAB (Floating Action Button) - Material 3 Standard */}
      <AnimatePresence>
        {isMobile && currentPath === '/recipes' && (
          <motion.button
            initial={{ scale: 0, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0, opacity: 0 }}
            whileTap={{ scale: 0.9 }}
            className="fixed right-6 bottom-24 w-14 h-14 rounded-2xl shadow-xl bg-primary text-primary-foreground flex items-center justify-center z-40 ripple"
            onClick={() => navigate('/recipes/new')}
          >
            <Plus className="w-8 h-8" />
          </motion.button>
        )}
      </AnimatePresence>
    </div>
  );
};
