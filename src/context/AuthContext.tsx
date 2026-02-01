import React, { createContext, useContext, useState, useEffect } from 'react';
import { authApi, householdApi } from '../lib/api';
import { debug, DebugLogger, logStateChange } from '../lib/debug';

const authLogger = new DebugLogger('auth');
const AuthContext = createContext(null);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [household, setHousehold] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const initAuth = async () => {
      authLogger.info('Initializing auth state');
      const token = localStorage.getItem('token');
      const savedUser = localStorage.getItem('user');

      if (token && savedUser) {
        authLogger.debug('Found saved token and user, validating...');
        try {
          const parsedUser = JSON.parse(savedUser);
          setUser(parsedUser);
          authLogger.debug('Parsed saved user', { userId: parsedUser.id, email: parsedUser.email });

          // Get extended user info with role
          const res = await authApi.me();
          // Get server URL - use relative URL for HA ingress compatibility
          const serverUrl = localStorage.getItem('mise_server_url') || process.env.REACT_APP_BACKEND_URL || '';
          const apiPath = serverUrl ? `${serverUrl}/api/auth/me/extended` : 'api/auth/me/extended';
          const extendedRes = await fetch(
            apiPath,
            { headers: { 'Authorization': `Bearer ${token}` } }
          ).then(r => r.ok ? r.json() : null).catch(() => null);

          const userData = extendedRes || res.data;
          setUser(userData);
          localStorage.setItem('user', JSON.stringify(userData));
          authLogger.info('User authenticated successfully', { userId: userData.id, role: userData.role });

          // Fetch household
          if (userData.household_id) {
            authLogger.debug('Fetching household', { householdId: userData.household_id });
            const hRes = await householdApi.getMy();
            setHousehold(hRes.data);
            authLogger.debug('Household loaded', { householdId: hRes.data?.id });
          }
        } catch (error) {
          authLogger.error('Auth initialization failed', { error: error.message });
          console.error('Auth init error:', error);
          localStorage.removeItem('token');
          localStorage.removeItem('user');
        }
      } else {
        authLogger.debug('No saved auth state found');
      }
      setLoading(false);
      authLogger.info('Auth initialization complete', { isAuthenticated: !!token && !!savedUser });
    };

    initAuth();
  }, []);

  const login = async (email, password, totpCode = null) => {
    authLogger.info('Login attempt', { email: email.substring(0, 3) + '***' });
    const res = await authApi.login({ email, password, totp_code: totpCode });

    // Check if 2FA is required
    if (res.data.requires_2fa) {
      authLogger.info('2FA required for login');
      return { requires_2fa: true };
    }

    localStorage.setItem('token', res.data.token);
    localStorage.setItem('user', JSON.stringify(res.data.user));
    logStateChange('AuthContext', 'user', null, res.data.user);
    setUser(res.data.user);
    authLogger.info('Login successful', { userId: res.data.user.id, role: res.data.user.role });

    if (res.data.user.household_id) {
      authLogger.debug('Fetching household after login');
      const hRes = await householdApi.getMy();
      setHousehold(hRes.data);
    }

    return res.data;
  };

  const register = async (name, email, password, role = null, inviteCode = null) => {
    authLogger.info('Registration attempt', { email: email.substring(0, 3) + '***' });
    const res = await authApi.register({ name, email, password, role, invite_code: inviteCode });
    localStorage.setItem('token', res.data.token);
    localStorage.setItem('user', JSON.stringify(res.data.user));
    logStateChange('AuthContext', 'user', null, res.data.user);
    setUser(res.data.user);
    authLogger.info('Registration successful', { userId: res.data.user.id });
    return res.data;
  };

  const logout = async () => {
    authLogger.info('Logout initiated', { userId: user?.id });
    // Call backend to invalidate session before clearing local state
    try {
      await authApi.logout();
      authLogger.debug('Backend session invalidated');
    } catch (error) {
      // Ignore errors - we still want to clear local state even if backend call fails
      authLogger.warn('Logout API call failed', { error: error.message });
      console.debug('Logout API call failed:', error);
    }
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    logStateChange('AuthContext', 'user', user, null);
    setUser(null);
    setHousehold(null);
    authLogger.info('Logout complete');
  };

  const refreshHousehold = async () => {
    if (user?.household_id) {
      const hRes = await householdApi.getMy();
      setHousehold(hRes.data);
    } else {
      setHousehold(null);
    }
  };

  const updateUser = (newUser) => {
    setUser(newUser);
    localStorage.setItem('user', JSON.stringify(newUser));
  };

  const isAdmin = user?.role === 'admin';

  return (
    <AuthContext.Provider value={{
      user,
      household,
      loading,
      login,
      register,
      logout,
      refreshHousehold,
      updateUser,
      isAuthenticated: !!user,
      isAdmin,
    }}>
      {children}
    </AuthContext.Provider>
  );
};
