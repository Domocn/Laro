import React, { lazy, Suspense } from 'react';
import { HashRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'sonner';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ThemeProvider } from './context/ThemeContext';
import { LanguageProvider } from './context/LanguageContext';
import { AccessibilityProvider } from './context/AccessibilityContext';
import { ChatProvider, useChat } from './context/ChatContext';
import { InstallPrompt } from './components/InstallPrompt';
import { ReadingRuler } from './components/ReadingRuler';
import { SkipToContent } from './components/SkipToContent';
import { UserOnboarding } from './components/UserOnboarding';
import { ChatModal, ChatButton } from './components/ChatModal';
import { CookieConsent } from './components/CookieConsent';

// Lazy-loaded pages for code splitting
const Landing = lazy(() => import('./pages/Landing').then(m => ({ default: m.Landing })));
const Login = lazy(() => import('./pages/Auth').then(m => ({ default: m.Login })));
const Register = lazy(() => import('./pages/Auth').then(m => ({ default: m.Register })));
const Dashboard = lazy(() => import('./pages/Dashboard').then(m => ({ default: m.Dashboard })));
const Recipes = lazy(() => import('./pages/Recipes').then(m => ({ default: m.Recipes })));
const RecipeDetail = lazy(() => import('./pages/RecipeDetail').then(m => ({ default: m.RecipeDetail })));
const RecipeForm = lazy(() => import('./pages/RecipeForm').then(m => ({ default: m.RecipeForm })));
const ImportRecipe = lazy(() => import('./pages/ImportRecipe').then(m => ({ default: m.ImportRecipe })));
const MealPlanner = lazy(() => import('./pages/MealPlanner').then(m => ({ default: m.MealPlanner })));
const ShoppingLists = lazy(() => import('./pages/ShoppingLists').then(m => ({ default: m.ShoppingLists })));
const Household = lazy(() => import('./pages/Household').then(m => ({ default: m.Household })));
const ServerConfig = lazy(() => import('./pages/ServerConfig').then(m => ({ default: m.ServerConfig })));
const Settings = lazy(() => import('./pages/Settings').then(m => ({ default: m.Settings })));
const QuickAddRecipe = lazy(() => import('./pages/QuickAddRecipe').then(m => ({ default: m.QuickAddRecipe })));
const SharedRecipe = lazy(() => import('./pages/SharedRecipe').then(m => ({ default: m.SharedRecipe })));
const ImportFromPlatform = lazy(() => import('./pages/ImportFromPlatform').then(m => ({ default: m.ImportFromPlatform })));
const AdminDashboard = lazy(() => import('./pages/AdminDashboard').then(m => ({ default: m.AdminDashboard })));
const SecuritySettings = lazy(() => import('./pages/SecuritySettings').then(m => ({ default: m.SecuritySettings })));
const ForgotPassword = lazy(() => import('./pages/ForgotPassword').then(m => ({ default: m.ForgotPassword })));
const ResetPassword = lazy(() => import('./pages/ForgotPassword').then(m => ({ default: m.ResetPassword })));
const VerifyEmail = lazy(() => import('./pages/VerifyEmail').then(m => ({ default: m.VerifyEmail })));
const OAuthCallback = lazy(() => import('./pages/OAuthCallback').then(m => ({ default: m.OAuthCallback })));
const UserPreferences = lazy(() => import('./pages/UserPreferences').then(m => ({ default: m.UserPreferences })));
const SetupWizard = lazy(() => import('./pages/SetupWizard').then(m => ({ default: m.SetupWizard })));
const FeatureWalkthrough = lazy(() => import('./components/FeatureWalkthrough').then(m => ({ default: m.FeatureWalkthrough })));
const PrivacyPolicy = lazy(() => import('./pages/PrivacyPolicy').then(m => ({ default: m.PrivacyPolicy })));
const Cookbooks = lazy(() => import('./pages/Cookbooks').then(m => ({ default: m.Cookbooks })));
const Pantry = lazy(() => import('./pages/Pantry').then(m => ({ default: m.Pantry })));

import { NameUpdateModal } from './components/NameUpdateModal';
import { PasswordChangeModal } from './components/PasswordChangeModal';

import './App.css';

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
  
  if (loading) {
    return (
      <div className="min-h-screen bg-cream flex items-center justify-center">
        <div className="w-8 h-8 border-4 border-laro border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }
  
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
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
        <Route path="/r/:shareCode" element={<SharedRecipe />} />
        <Route path="/shared/:shareCode" element={<SharedRecipe />} />
        <Route path="/oauth/callback/:provider" element={<OAuthCallback />} />
        <Route path="/privacy-policy" element={<PrivacyPolicy />} />

        {/* Protected Routes */}
        <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
        <Route path="/recipes" element={<ProtectedRoute><Recipes /></ProtectedRoute>} />
        <Route path="/recipes/new" element={<ProtectedRoute><RecipeForm /></ProtectedRoute>} />
        <Route path="/recipes/quick-add" element={<ProtectedRoute><QuickAddRecipe /></ProtectedRoute>} />
        <Route path="/recipes/import" element={<ProtectedRoute><ImportRecipe /></ProtectedRoute>} />
        <Route path="/recipes/import-batch" element={<ProtectedRoute><ImportFromPlatform /></ProtectedRoute>} />
        <Route path="/recipes/:id" element={<ProtectedRoute><RecipeDetail /></ProtectedRoute>} />
        <Route path="/recipes/:id/edit" element={<ProtectedRoute><RecipeForm /></ProtectedRoute>} />
        <Route path="/meal-planner" element={<ProtectedRoute><MealPlanner /></ProtectedRoute>} />
        <Route path="/shopping" element={<ProtectedRoute><ShoppingLists /></ProtectedRoute>} />
        <Route path="/cookbooks" element={<ProtectedRoute><Cookbooks /></ProtectedRoute>} />
        <Route path="/fridge" element={<ProtectedRoute><Pantry /></ProtectedRoute>} />
        <Route path="/pantry" element={<Navigate to="/fridge" replace />} />
        <Route path="/household" element={<ProtectedRoute><Household /></ProtectedRoute>} />
        <Route path="/settings" element={<ProtectedRoute><Settings /></ProtectedRoute>} />
        <Route path="/settings/security" element={<ProtectedRoute><SecuritySettings /></ProtectedRoute>} />
        <Route path="/settings/preferences" element={<ProtectedRoute><UserPreferences /></ProtectedRoute>} />
        <Route path="/admin" element={<ProtectedRoute><AdminDashboard /></ProtectedRoute>} />
        <Route path="/setup" element={<ProtectedRoute><SetupWizard /></ProtectedRoute>} />

        {/* Fallback */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}

function App() {
  return (
    <HashRouter>
      <ThemeProvider>
        <LanguageProvider>
          <AuthProvider>
            <AccessibilityProvider>
              <ChatProvider>
                <SkipToContent />
                <ReadingRuler />
                <UserOnboarding />
                <NameUpdateModal />
                <PasswordChangeModal />
                <AppRoutes />
                <GlobalChat />
                <CookieConsent />
                <InstallPrompt />
                <Toaster
                  position="top-right"
                  toastOptions={{
                    style: {
                      background: '#FFFFFF',
                      border: '1px solid #E6E2D6',
                      borderRadius: '1rem',
                    },
                    className: 'font-sans',
                  }}
                />
              </ChatProvider>
            </AccessibilityProvider>
          </AuthProvider>
        </LanguageProvider>
      </ThemeProvider>
    </HashRouter>
  );
}

export default App;
