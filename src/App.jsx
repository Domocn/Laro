import React, { lazy, Suspense } from 'react';
import { HashRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { MotionConfig } from 'framer-motion';
import { Toaster } from 'sonner';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ThemeProvider, useTheme } from './context/ThemeContext';
import { LanguageProvider } from './context/LanguageContext';
import { AccessibilityProvider } from './context/AccessibilityContext';
import { ChatProvider, useChat } from './context/ChatContext';
import { InstallPrompt } from './components/InstallPrompt';
import { ReadingRuler } from './components/ReadingRuler';
import { SkipToContent } from './components/SkipToContent';
import { UserOnboarding } from './components/UserOnboarding';
import { GuidedTour } from './components/GuidedTour';
import { ChatModal, ChatButton } from './components/ChatModal';
import { CookieConsent } from './components/CookieConsent';

// Lazy-loaded pages for code splitting
const Landing = lazy(() => import('./pages/Landing').then(m => ({ default: m.Landing })));
const Login = lazy(() => import('./pages/Auth').then(m => ({ default: m.Login })));
const Register = lazy(() => import('./pages/Auth').then(m => ({ default: m.Register })));
const Dashboard = lazy(() => import('./pages/Dashboard').then(m => ({ default: m.Dashboard })));
const RecipeFinder = lazy(() => import('./pages/RecipeFinder').then(m => ({ default: m.RecipeFinder })));
const Recipes = lazy(() => import('./pages/Recipes').then(m => ({ default: m.Recipes })));
const RecipeDetail = lazy(() => import('./pages/RecipeDetail').then(m => ({ default: m.RecipeDetail })));
const RecipeForm = lazy(() => import('./pages/RecipeForm').then(m => ({ default: m.RecipeForm })));
const ImportRecipe = lazy(() => import('./pages/ImportRecipe').then(m => ({ default: m.ImportRecipe })));
const MealPlanner = lazy(() => import('./pages/MealPlanner').then(m => ({ default: m.MealPlanner })));
const ShoppingLists = lazy(() => import('./pages/ShoppingLists').then(m => ({ default: m.ShoppingLists })));
const Household = lazy(() => import('./pages/Household').then(m => ({ default: m.Household })));
const Friends = lazy(() => import('./pages/Friends').then(m => ({ default: m.Friends })));
const Support = lazy(() => import('./pages/Support').then(m => ({ default: m.Support })));
const ServerConfig = lazy(() => import('./pages/ServerConfig').then(m => ({ default: m.ServerConfig })));
const Settings = lazy(() => import('./pages/Settings').then(m => ({ default: m.Settings })));
const QuickAddRecipe = lazy(() => import('./pages/QuickAddRecipe').then(m => ({ default: m.QuickAddRecipe })));
const RecreateStoreMeal = lazy(() => import('./pages/RecreateStoreMeal').then(m => ({ default: m.RecreateStoreMeal })));
const AddRecipe = lazy(() => import('./pages/AddRecipe').then(m => ({ default: m.AddRecipe })));
const SharedRecipe = lazy(() => import('./pages/SharedRecipe').then(m => ({ default: m.SharedRecipe })));
const ImportFromPlatform = lazy(() => import('./pages/ImportFromPlatform').then(m => ({ default: m.ImportFromPlatform })));
const MigrateRecipes = lazy(() => import('./pages/MigrateRecipes').then(m => ({ default: m.MigrateRecipes })));
const AdminDashboard = lazy(() => import('./pages/AdminDashboard').then(m => ({ default: m.AdminDashboard })));
const SecuritySettings = lazy(() => import('./pages/SecuritySettings').then(m => ({ default: m.SecuritySettings })));
const ImportsSettings = lazy(() => import('./pages/ImportsSettings').then(m => ({ default: m.ImportsSettings })));
const KitchenSettings = lazy(() => import('./pages/KitchenSettings').then(m => ({ default: m.KitchenSettings })));
const ForgotPassword = lazy(() => import('./pages/ForgotPassword').then(m => ({ default: m.ForgotPassword })));
const ResetPassword = lazy(() => import('./pages/ForgotPassword').then(m => ({ default: m.ResetPassword })));
const VerifyEmail = lazy(() => import('./pages/VerifyEmail').then(m => ({ default: m.VerifyEmail })));
const OAuthCallback = lazy(() => import('./pages/OAuthCallback').then(m => ({ default: m.OAuthCallback })));
const UserPreferences = lazy(() => import('./pages/UserPreferences').then(m => ({ default: m.UserPreferences })));
const SetupWizard = lazy(() => import('./pages/SetupWizard').then(m => ({ default: m.SetupWizard })));
const FeatureWalkthrough = lazy(() => import('./components/FeatureWalkthrough').then(m => ({ default: m.FeatureWalkthrough })));
const LegalRedirect = lazy(() => import('./pages/LegalRedirect').then(m => ({ default: m.LegalRedirect })));
const Cookbooks = lazy(() => import('./pages/Cookbooks').then(m => ({ default: m.Cookbooks })));
const CookbookDetail = lazy(() => import('./pages/CookbookDetail').then(m => ({ default: m.CookbookDetail })));
const Pantry = lazy(() => import('./pages/Pantry').then(m => ({ default: m.Pantry })));

import { NameUpdateModal } from './components/NameUpdateModal';
import { PasswordChangeModal } from './components/PasswordChangeModal';
import { WhatsNewModal } from './components/WhatsNewModal';
import { LiveRefreshProvider } from './hooks/useLiveRefresh';

import './App.css';

/** Only open the household websocket when a user is logged in. */
const AuthLiveRefresh = ({ children }) => {
  const { isAuthenticated } = useAuth();
  return (
    <LiveRefreshProvider autoConnect={!!isAuthenticated}>
      {children}
    </LiveRefreshProvider>
  );
};

// Loading fallback component
const PageLoader = () => (
  <div className="min-h-screen bg-cream flex items-center justify-center">
    <div className="w-8 h-8 border-4 border-laro border-t-transparent rounded-full animate-spin" />
  </div>
);

// Global Chat Component - only shows when authenticated
const GlobalChat = () => {
  const { isAuthenticated } = useAuth();
  const { isChatOpen, openChat, closeChat } = useChat();

  if (!isAuthenticated) return null;

  return (
    <>
      {!isChatOpen && <ChatButton onClick={openChat} />}
      <ChatModal isOpen={isChatOpen} onClose={closeChat} />
    </>
  );
};

// Protected Route Component
const ProtectedRoute = ({ children }) => {
  const { isAuthenticated, loading } = useAuth();
  const location = useLocation();
  
  if (loading) {
    return (
      <div className="min-h-screen bg-cream flex items-center justify-center">
        <div className="w-8 h-8 border-4 border-laro border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }
  
  if (!isAuthenticated) {
    const next = `${location.pathname}${location.search || ''}`;
    const q = next.startsWith('/') && !next.startsWith('//')
      ? `?next=${encodeURIComponent(next)}`
      : '';
    return <Navigate to={`/login${q}`} replace />;
  }
  
  return children;
};

// Public Route - redirects to dashboard if logged in
const PublicRoute = ({ children }) => {
  const { isAuthenticated, loading } = useAuth();
  
  if (loading) {
    return (
      <div className="min-h-screen bg-cream flex items-center justify-center">
        <div className="w-8 h-8 border-4 border-laro border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }
  
  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  }
  
  return children;
};

function AppRoutes() {
  return (
    <Suspense fallback={<PageLoader />}>
      <Routes>
        {/* Public Routes */}
        <Route path="/" element={<PublicRoute><Landing /></PublicRoute>} />
        <Route path="/tour" element={<PublicRoute><FeatureWalkthrough /></PublicRoute>} />
        <Route path="/login" element={<PublicRoute><Login /></PublicRoute>} />
        <Route path="/register" element={<PublicRoute><Register /></PublicRoute>} />
        <Route path="/forgot-password" element={<ForgotPassword />} />
        <Route path="/reset-password" element={<ResetPassword />} />
        <Route path="/verify-email" element={<VerifyEmail />} />
        <Route path="/server" element={<ServerConfig />} />
        <Route path="/recipe/:shareCode" element={<SharedRecipe />} />
        <Route path="/r/:shareCode" element={<SharedRecipe />} />
        <Route path="/shared/:shareCode" element={<SharedRecipe />} />
        <Route path="/oauth/callback/:provider" element={<OAuthCallback />} />
        <Route path="/privacy-policy" element={<LegalRedirect href="/privacy-policy" />} />
        <Route path="/terms" element={<LegalRedirect href="/terms" />} />
        <Route path="/terms-of-service" element={<LegalRedirect href="/terms" />} />

        {/* Protected Routes */}
        <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
        <Route path="/recipes" element={<ProtectedRoute><Recipes /></ProtectedRoute>} />
        <Route path="/recipe-finder" element={<ProtectedRoute><RecipeFinder /></ProtectedRoute>} />
        <Route path="/recipes/add" element={<ProtectedRoute><AddRecipe /></ProtectedRoute>} />
        <Route path="/recipes/new" element={<ProtectedRoute><RecipeForm /></ProtectedRoute>} />
        <Route path="/recipes/quick-add" element={<ProtectedRoute><QuickAddRecipe /></ProtectedRoute>} />
        <Route path="/recipes/store-meal" element={<ProtectedRoute><RecreateStoreMeal /></ProtectedRoute>} />
        <Route path="/recipes/import" element={<ProtectedRoute><ImportRecipe /></ProtectedRoute>} />
        <Route path="/recipes/import-batch" element={<ProtectedRoute><ImportFromPlatform /></ProtectedRoute>} />
        <Route path="/recipes/migrate" element={<ProtectedRoute><MigrateRecipes /></ProtectedRoute>} />
        {/* More specific /edit must be declared before /:id so client navigations resolve correctly */}
        <Route path="/recipes/:id/edit" element={<ProtectedRoute><RecipeForm /></ProtectedRoute>} />
        <Route path="/recipes/:id" element={<ProtectedRoute><RecipeDetail /></ProtectedRoute>} />
        <Route path="/meal-planner" element={<ProtectedRoute><MealPlanner /></ProtectedRoute>} />
        <Route path="/shopping" element={<ProtectedRoute><ShoppingLists /></ProtectedRoute>} />
        <Route path="/cookbooks" element={<ProtectedRoute><Cookbooks /></ProtectedRoute>} />
        <Route path="/cookbooks/:id" element={<ProtectedRoute><CookbookDetail /></ProtectedRoute>} />
        <Route path="/fridge" element={<ProtectedRoute><Pantry /></ProtectedRoute>} />
        <Route path="/pantry" element={<Navigate to="/fridge" replace />} />
        <Route path="/household" element={<ProtectedRoute><Household /></ProtectedRoute>} />
        <Route path="/friends" element={<ProtectedRoute><Friends /></ProtectedRoute>} />
        <Route path="/support" element={<ProtectedRoute><Support /></ProtectedRoute>} />
        <Route path="/settings" element={<ProtectedRoute><Settings /></ProtectedRoute>} />
        <Route path="/settings/security" element={<ProtectedRoute><SecuritySettings /></ProtectedRoute>} />
        <Route path="/settings/preferences" element={<ProtectedRoute><UserPreferences /></ProtectedRoute>} />
        <Route path="/settings/imports" element={<ProtectedRoute><ImportsSettings /></ProtectedRoute>} />
        <Route path="/settings/kitchen" element={<ProtectedRoute><KitchenSettings /></ProtectedRoute>} />
        <Route path="/admin" element={<ProtectedRoute><AdminDashboard /></ProtectedRoute>} />
        <Route path="/setup" element={<ProtectedRoute><SetupWizard /></ProtectedRoute>} />

        {/* Fallback */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}

// Toasts follow the real theme. The previous version hardcoded a white
// background, so in dark mode the inherited light text sat on white and the
// messages were unreadable. Sonner only needs the mode; the colours come
// from the token-driven CSS in index.css.
function AppToaster() {
  const { theme } = useTheme();
  const isDark =
    theme === 'dark' ||
    (theme !== 'light' && window.matchMedia('(prefers-color-scheme: dark)').matches);

  return (
    <Toaster
      position="top-right"
      theme={isDark ? 'dark' : 'light'}
      closeButton
      richColors={false}
      toastOptions={{ className: 'laro-toast' }}
    />
  );
}

// `.reduce-motion` in CSS only stops CSS transitions. Framer Motion animates
// in JS, so the landing and card animations kept playing for users who had
// turned reduced motion on. Honour the in-app preference for every animation.
function ReducedMotion({ children }) {
  const { reducedMotion } = useTheme();
  return (
    <MotionConfig reducedMotion={reducedMotion ? 'always' : 'user'}>
      {children}
    </MotionConfig>
  );
}

function App() {
  return (
    <HashRouter>
      <ThemeProvider>
        <ReducedMotion>
        <LanguageProvider>
          <AuthProvider>
            <AuthLiveRefresh>
              <AccessibilityProvider>
                <ChatProvider>
                  <SkipToContent />
                  <ReadingRuler />
                  <UserOnboarding />
                  <GuidedTour />
                  <NameUpdateModal />
                  <PasswordChangeModal />
                  <WhatsNewModal />
                  <AppRoutes />
                  <GlobalChat />
                  <CookieConsent />
                  <InstallPrompt />
                  <AppToaster />
                </ChatProvider>
              </AccessibilityProvider>
            </AuthLiveRefresh>
          </AuthProvider>
        </LanguageProvider>
        </ReducedMotion>
      </ThemeProvider>
    </HashRouter>
  );
}

export default App;
