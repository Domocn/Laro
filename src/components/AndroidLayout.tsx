import React, { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Home, 
  UtensilsCrossed, 
  CalendarDays, 
  ShoppingCart, 
  Refrigerator,
  Plus,
  ChevronLeft,
  User,
  Search,
  Bell
} from 'lucide-react';
import { Button } from './ui/button';
import { useIsMobile } from '../hooks/use-mobile';
import { cn } from '../lib/utils';

interface NavItem {
  path: string;
  label: string;
  icon: React.ElementType;
}

const navItems: NavItem[] = [
  { path: '/dashboard', label: 'Home', icon: Home },
  { path: '/recipes', label: 'Recipes', icon: UtensilsCrossed },
  { path: '/meal-planner', label: 'Plan', icon: CalendarDays },
  { path: '/shopping', label: 'Shop', icon: ShoppingCart },
  { path: '/fridge', label: 'Fridge', icon: Refrigerator },
];

export const AndroidLayout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const isMobile = useIsMobile();
  const location = useLocation();
  const navigate = useNavigate();
  const [isAndroid] = useState(() => /Android/i.test(navigator.userAgent));

  const currentPath = location.pathname;
  const isDetailPage = currentPath.includes('/recipes/') && !['/recipes', '/recipes/new', '/recipes/import', '/recipes/quick-add'].includes(currentPath);
  const isSettingsPage = currentPath.startsWith('/settings');
  
  const showBackButton = isDetailPage || isSettingsPage || currentPath === '/recipes/new';

  const getPageTitle = () => {
    if (isDetailPage) return 'Recipe Details';
    const item = navItems.find(i => i.path === currentPath);
    if (item) return item.label;
    if (isSettingsPage) return 'Settings';
    return 'Laro';
  };

  return (
    <div className={cn(
      "min-h-screen bg-background flex flex-col",
      isAndroid && "font-sans antialiased"
    )}>
      {/* Top App Bar (Material 3 Style) */}
      <header className="sticky top-0 z-50 bg-background/95 backdrop-blur-sm border-b border-border/10 h-16 flex items-center px-4">
        <div className="flex items-center w-full max-w-5xl mx-auto">
          {showBackButton ? (
            <Button
              variant="ghost"
              size="icon"
              className="mr-2 rounded-full"
              onClick={() => navigate(-1)}
            >
              <ChevronLeft className="w-6 h-6" />
            </Button>
          ) : (
            <div className="md:hidden mr-4">
               <img src="/mise-banner.svg" alt="Laro" className="h-8" />
            </div>
          )}
          
          <h1 className="text-xl font-medium flex-1 truncate">
            {getPageTitle()}
          </h1>

          <div className="flex items-center gap-1">
            <Button variant="ghost" size="icon" className="rounded-full">
              <Search className="w-5 h-5" />
            </Button>
            <Button variant="ghost" size="icon" className="rounded-full">
              <Bell className="w-5 h-5" />
            </Button>
            <Button 
              variant="ghost" 
              size="icon" 
              className="rounded-full ml-1"
              onClick={() => navigate('/settings')}
            >
              <User className="w-6 h-6" />
            </Button>
          </div>
        </div>
      </header>

      {/* Main Content with Native Transitions */}
      <main className="flex-1 overflow-x-hidden pb-20 md:pb-0">
        <div className="max-w-5xl mx-auto px-4 py-4">
          <AnimatePresence mode="wait">
            <motion.div
              key={location.pathname}
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              transition={{ duration: 0.2, ease: "easeOut" }}
            >
              {children}
            </motion.div>
          </AnimatePresence>
        </div>
      </main>

      {/* Bottom Navigation (Material 3 Style) */}
      {isMobile && (
        <nav className="fixed bottom-0 left-0 right-0 z-50 bg-surface-container border-t border-border/10 pb-safe">
          <div className="flex justify-around items-center h-16">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = currentPath === item.path;
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  className="relative flex flex-col items-center flex-1 py-1 group"
                  onClick={() => {
                    if (window.navigator.vibrate) window.navigator.vibrate(5);
                  }}
                >
                  <div className={cn(
                    "relative px-5 py-1 rounded-full transition-all duration-200",
                    isActive ? "bg-primary/20 text-primary" : "text-muted-foreground group-hover:bg-muted/50"
                  )}>
                    <Icon className={cn(
                      "w-6 h-6 transition-all",
                      isActive ? "scale-110" : "scale-100"
                    )} />
                  </div>
                  <span className={cn(
                    "text-[11px] mt-1 font-medium transition-colors",
                    isActive ? "text-primary" : "text-muted-foreground"
                  )}>
                    {item.label}
                  </span>
                </Link>
              );
            })}
          </div>
        </nav>
      )}

      {/* FAB for mobile - Material 3 standard for adding things */}
      {isMobile && currentPath === '/recipes' && (
        <Button
          className="fixed right-6 bottom-24 w-14 h-14 rounded-2xl shadow-lg bg-primary text-primary-foreground flex items-center justify-center hover:scale-110 active:scale-95 transition-transform"
          onClick={() => navigate('/recipes/new')}
        >
          <Plus className="w-8 h-8" />
        </Button>
      )}
    </div>
  );
};
