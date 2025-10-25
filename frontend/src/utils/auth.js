// src/utils/auth.js
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

/**
 * Token management utility
 */
export const auth = {
  // Get access token
  getToken: () => localStorage.getItem('token'),
  
  // Get refresh token
  getRefreshToken: () => localStorage.getItem('refresh_token'),
  
  // Set tokens
  setTokens: (accessToken, refreshToken) => {
    localStorage.setItem('token', data.data.access_token);
    if (refreshToken) {
      localStorage.setItem('refresh_token', data.data.refresh_token);
    }
  },
  
  // Clear tokens
  clearTokens: () => {
    localStorage.removeItem('token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user');
  },
  
  // Check if user is authenticated
  isAuthenticated: () => {
    return !!localStorage.getItem('token');
  },
  
  // Refresh access token
  refreshToken: async () => {
    const refreshToken = auth.getRefreshToken();
    
    if (!refreshToken) {
      throw new Error('No refresh token available');
    }
    
    try {
      const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ refresh_token: refreshToken })
      });
      
      if (!response.ok) {
        throw new Error('Failed to refresh token');
      }
      
      const data = await response.json();
      auth.setTokens(data.data.access_token, data.data.refresh_token);
      return data.data.access_token;
    } catch (error) {
      auth.clearTokens();
      throw error;
    }
  }
};

/**
 * Enhanced fetch wrapper with automatic token refresh
 */
// utils/auth.js (or wherever)
export async function authenticatedFetch(url, options = {}) {
  const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
  const token = localStorage.getItem('token');

  const fullUrl = url.startsWith('http') ? url : `${API_BASE_URL}${url}`;
  console.log('authenticatedFetch ->', fullUrl, options);

  try {
    options.headers = {
      ...(options.headers || {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {})
    };

    const res = await fetch(fullUrl, options);
    if (!res.ok) {
      // attempt to parse body for details
      const text = await res.text().catch(()=>null);
      console.warn('Request failed', res.status, text);
    }
    return res;
  } catch (err) {
    console.error('Network error fetching', fullUrl, err);
    throw err; // keep throwing so caller can handle
  }
}


/**
 * Logout utility
 */
export const logout = () => {
  auth.clearTokens();
  window.location.href = '/login';
};