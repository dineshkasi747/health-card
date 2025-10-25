// App.js - Complete version with automatic token refresh
import React, { useState, useEffect } from 'react';
import LoginPage from './pages/LoginPage';
import SignupPage from './pages/SignupPage';
import PatientDashboard from './pages/PatientDashboard';
import DoctorDashboard from './pages/DoctorDashboard';
import AdminDashboard from './pages/AdminDashboard';

const API_URL = 'http://localhost:8000';

// ============================================================================
// AUTH SERVICE - Handles all token management (IN-MEMORY STORAGE)
// ============================================================================
class AuthService {
  constructor() {
    this.tokens = {
      access: null,
      refresh: null
    };
    this.user = null;
  }

  setTokens(accessToken, refreshToken) {
    this.tokens.access = accessToken;
    this.tokens.refresh = refreshToken;
  }

  getAccessToken() {
    return this.tokens.access;
  }

  getRefreshToken() {
    return this.tokens.refresh;
  }

  setUser(user) {
    this.user = user;
  }

  getUser() {
    return this.user;
  }

  clearAuth() {
    this.tokens.access = null;
    this.tokens.refresh = null;
    this.user = null;
  }

  async refreshAccessToken() {
    const refreshToken = this.getRefreshToken();
    
    if (!refreshToken) {
      throw new Error('No refresh token available');
    }

    try {
      console.log('🔄 Refreshing access token...');
      
      const response = await fetch(`${API_URL}/auth/refresh`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${refreshToken}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        throw new Error('Token refresh failed');
      }

      const data = await response.json();
      this.setTokens(data.data.access_token, data.data.refresh_token);
      this.setUser(data.data.user);
      
      console.log('✅ Token refreshed successfully');
      return data.data.access_token;
    } catch (error) {
      console.error('❌ Token refresh error:', error);
      this.clearAuth();
      throw error;
    }
  }

  async authenticatedFetch(url, options = {}) {
    const accessToken = this.getAccessToken();
    
    if (!accessToken) {
      throw new Error('No access token available');
    }

    // Build full URL if it's a relative path
    const fullUrl = url.startsWith('http') ? url : `${API_URL}${url}`;

    // Prepare headers
    const headers = {
      ...options.headers,
      'Authorization': `Bearer ${accessToken}`
    };

    // Only set Content-Type if body exists and it's not FormData
    if (options.body && !(options.body instanceof FormData)) {
      headers['Content-Type'] = headers['Content-Type'] || 'application/json';
    }

    try {
      let response = await fetch(fullUrl, { ...options, headers });

      // If unauthorized, try refreshing token
      if (response.status === 401) {
        console.log('⚠️ 401 Unauthorized - Token expired, refreshing...');
        
        try {
          const newAccessToken = await this.refreshAccessToken();
          headers['Authorization'] = `Bearer ${newAccessToken}`;
          
          // Retry with new token
          console.log('🔁 Retrying request with new token...');
          response = await fetch(fullUrl, { ...options, headers });
          
          if (response.ok) {
            console.log('✅ Request successful after token refresh');
          }
        } catch (refreshError) {
          console.error('❌ Refresh failed, redirecting to login...');
          this.clearAuth();
          throw new Error('Session expired. Please login again.');
        }
      }

      return response;
    } catch (error) {
      console.error('Authenticated fetch error:', error);
      throw error;
    }
  }

  // Helper methods for common HTTP verbs
  async get(endpoint) {
    return this.authenticatedFetch(endpoint, { method: 'GET' });
  }

  async post(endpoint, data) {
    const isFormData = data instanceof FormData;
    return this.authenticatedFetch(endpoint, {
      method: 'POST',
      body: isFormData ? data : JSON.stringify(data)
    });
  }

  async patch(endpoint, data) {
    const isFormData = data instanceof FormData;
    return this.authenticatedFetch(endpoint, {
      method: 'PATCH',
      body: isFormData ? data : JSON.stringify(data)
    });
  }

  async delete(endpoint) {
    return this.authenticatedFetch(endpoint, { method: 'DELETE' });
  }

  async uploadFile(endpoint, file, additionalData = {}) {
    const formData = new FormData();
    formData.append('file', file);
    Object.keys(additionalData).forEach(key => {
      formData.append(key, additionalData[key]);
    });
    return this.authenticatedFetch(endpoint, {
      method: 'POST',
      body: formData
    });
  }
}

// Create a singleton instance
const authService = new AuthService();

// ============================================================================
// MAIN APP COMPONENT
// ============================================================================
function App() {
  const [currentPage, setCurrentPage] = useState('login');
  const [user, setUser] = useState(null);

  const handleLogin = (userData, accessToken, refreshToken) => {
    console.log('🎉 Login successful:', userData.name);
    
    // Store tokens and user data
    authService.setTokens(accessToken, refreshToken);
    authService.setUser(userData);
    
    setUser(userData);
    
    // Navigate based on role
    if (userData.role === 'patient') {
      setCurrentPage('patient-dashboard');
    } else if (userData.role === 'doctor') {
      setCurrentPage('doctor-dashboard');
    } else if (userData.role === 'admin') {
      setCurrentPage('admin-dashboard');
    }
  };

  const handleLogout = () => {
    console.log('👋 Logging out...');
    authService.clearAuth();
    setUser(null);
    setCurrentPage('login');
  };

  const renderPage = () => {
    switch (currentPage) {
      case 'login':
        return (
          <LoginPage 
            onLogin={handleLogin}
            onNavigateSignup={() => setCurrentPage('signup')}
            apiUrl={API_URL}
          />
        );
      
      case 'signup':
        return (
          <SignupPage 
            onSignup={handleLogin}
            onNavigateLogin={() => setCurrentPage('login')}
            apiUrl={API_URL}
          />
        );
      
      case 'patient-dashboard':
        return (
          <PatientDashboard 
            user={user}
            onLogout={handleLogout}
            apiUrl={API_URL}
            authService={authService}
          />
        );
      
      case 'doctor-dashboard':
        return (
          <DoctorDashboard 
            user={user}
            onLogout={handleLogout}
            apiUrl={API_URL}
            authService={authService}
          />
        );
      
      case 'admin-dashboard':
        return (
          <AdminDashboard 
            user={user}
            onLogout={handleLogout}
            apiUrl={API_URL}
            authService={authService}
          />
        );
      
      default:
        return (
          <LoginPage 
            onLogin={handleLogin}
            onNavigateSignup={() => setCurrentPage('signup')}
            apiUrl={API_URL}
          />
        );
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {renderPage()}
    </div>
  );
}

export default App;
export { authService };