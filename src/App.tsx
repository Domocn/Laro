import React, { lazy, Suspense } from 'react';
import { HashRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'sonner';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ThemeProvider } from './context/ThemeContext';
import { LanguageProvider } from './context/LanguageContext';
import { AccessibilityProvider } from './context/AccessibilityContext';
import { ChatProvider, useChat } from './context/ChatContext';
import { LiveRefreshProvider } from './hooks/useLiveRefresh';
import { InstallPrompt } from './components/InstallPrompt';
import { ReadingRuler } from './components/ReadingRuler';
import { SkipToContent } from './components/SkipToContent';
import { UserOnboarding } from './components/UserOnboarding';
import { AndroidLayout } from './components/AndroidLayout';
import { ChatModal, ChatButton } from './components/ChatModal';

// Lazy-loaded pages for code splitting
const Landing = lazy(() => import('./pages/Landing').then(m => ({ default: (m as any).Landing })));
const Login = lazy(() => import('./pages/Auth').then(m => ({ default: (m as any).Login })));
const Register = lazy(() => import('./pages/Auth').then(m => ({ default: (m as any).Register })));
const Dashboard = lazy(() => import('./pages/Dashboard').then(m => ({ default: (m as any).Dashboard })));
const Recipes = lazy(() => import('./pages/Recipes').then(m => ({ default: (m as any).Recipes })));
const RecipeDetail = lazy(() => import('./pages/RecipeDetail').then(m => ({ default: (m as any).RecipeDetail })));
const RecipeForm = lazy(() => import('./pages/RecipeForm').then(m => ({ default: (m as any).RecipeForm })));
const ImportRecipe = lazy(() => import('./pages/ImportRecipe').then(m => ({ default: (m as any).ImportRecipe })));
const MealPlanner = lazy(() => import('./pages/MealPlanner').then(m => ({ default: (m as any).MealPlanner })));
const ShoppingLists = lazy(() => import('./pages/ShoppingLists').then(m => ({ default: (m as any).ShoppingLists })));
const FridgeSearch = lazy(() => import('./pages/FridgeSearch').then(m => ({ default: (m as any).FridgeSearch })));
const Household = lazy(() => import('./pages/Household').then(m => ({ default: (m as any).Household })));
const ServerConfig = lazy(() => import('./pages/ServerConfig').then(m => ({ default: (m as any).ServerConfig })));
const Settings = lazy(() => import('./pages/Settings').then(m => ({ default: (m as any).Settings })));
const QuickAddRecipe = lazy(() => import('./pages/QuickAddRecipe').then(m => ({ default: (m as any).QuickAddRecipe })));
const SharedRecipe = lazy(() => import('./pages/SharedRecipe').then(m => ({ default: (m as any).SharedRecipe })));
const ImportFromPlatform = lazy(() => import('./pages/ImportFromPlatform').then(m => ({ default: (m as any).ImportFromPlatform })));
const AdminDashboard = lazy(() => import('./pages/AdminDashboard').then(m => ({ default: (m as any).AdminDashboard })));
const SecuritySettings = lazy(() => import('./pages/SecuritySettings').then(m => ({ default: (m as any).SecuritySettings })));
const ForgotPassword = lazy(() => import('./pages/ForgotPassword').then(m => ({ default: (m as any).ForgotPassword })));
const ResetPassword = lazy(() => import('./pages/ForgotPassword').then(m => ({ default: (m as any).ResetPassword })));
const OAuthCallback = lazy(() => import('./pages/OAuthCallback').then(m => ({ default: (m as any).OAuthCallback })));
const UserPreferences = lazy(() => import('./pages/UserPreferences').then(m => ({ default: (m as any).UserPreferences })));
const SetupWizard = lazy(() => import('./pages/SetupWizard').then(m => ({ default: (m as any).SetupWizard })));

import './App.css';

// Global Chat Component - only shows when authenticated
const GlobalChat = () => {
  const { isAuthenticated } = useAuth() as any;
  const { isChatOpen, openChat, closeChat } = useChat();

  if (!isAuthenticated) return null;

  return (
    <>
      {!isChatOpen && <ChatButton onClick={openChat} />}
      <ChatModal isOpen={isChatOpen} onClose={closeChat} />
    </>
  );
};

// Loading fallback component
const PageLoader = () => (
  <div className="min-h-screen bg-background flex items-center justify-center">
    <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin" />
  </div>
);

// Protected Route Component - includes LiveRefreshProvider for real-time updates
const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const { isAuthenticated, loading } = useAuth() as any;

  if (loading) return <PageLoader />;
  if (!isAuthenticated) return <Navigate to="/login" replace />;

  return (
    <LiveRefreshProvider>
      <AndroidLayout>{children}</AndroidLayout>
    </LiveRefreshProvider>
  );
};

// Public Route
const PublicRoute = ({ children }: { children: React.ReactNode }) => {
  const { isAuthenticated, loading } = useAuth() as any;
  
  if (loading) return <PageLoader />;
  if (isAuthenticated) return <Navigate to="/dashboard" replace />;
  
  return <>{children}</>;
};

function AppRoutes() {
  return (
    <Suspense fallback={<PageLoader />}>
      <Routes>
        {/* Public Routes */}
        <Route path="/" element={<PublicRoute><Landing /></PublicRoute>} />
        <Route path="/login" element={<PublicRoute><Login /></PublicRoute>} />
        <Route path="/register" element={<PublicRoute><Register /></PublicRoute>} />
        <Route path="/forgot-password" element={<ForgotPassword />} />
        <Route path="/reset-password" element={<ResetPassword />} />
        <Route path="/server" element={<ServerConfig />} />
        <Route path="/r/:shareCode" element={<SharedRecipe />} />
        <Route path="/shared/:shareCode" element={<SharedRecipe />} />
        <Route path="/oauth/callback/:provider" element={<OAuthCallback />} />

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
        <Route path="/fridge" element={<ProtectedRoute><FridgeSearch /></ProtectedRoute>} />
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
                <AppRoutes />
                <GlobalChat />
                <InstallPrompt />
                <Toaster
                position="top-right"
                toastOptions={{
                  style: {
                    background: 'hsl(var(--card))',
                    border: '1px solid hsl(var(--border))',
                    borderRadius: '1rem',
                    color: 'hsl(var(--foreground))'
                  },
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
