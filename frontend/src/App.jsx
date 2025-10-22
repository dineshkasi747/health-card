// App.jsx - Complete Digital Health Card System
// Fully integrated with backend (main.py, models.py, config.py)
import React, { useState, useEffect } from 'react';
import LoginPage from './pages/LoginPage';
import SignupPage from './pages/SignupPage';
import PatientDashboard from './pages/PatientDashboard';
import DoctorDashboard from './pages/DoctorDashboard';
import AdminDashboard from './pages/AdminDashboard';

const API_URL = 'http://localhost:8000';

// ============================================================================
// AUTH SERVICE - Complete token management with session persistence
// ============================================================================
class AuthService {
  constructor() {
    this.loadFromStorage();
  }

  loadFromStorage() {
    try {
      const accessToken = localStorage.getItem('access_token');
      const refreshToken = localStorage.getItem('refresh_token');
      const userStr = localStorage.getItem('user');
      
      this.tokens = {
        access: accessToken,
        refresh: refreshToken
      };
      
      this.user = userStr ? JSON.parse(userStr) : null;
    } catch (error) {
      console.error('Error loading from storage:', error);
      this.tokens = { access: null, refresh: null };
      this.user = null;
    }
  }

  setTokens(accessToken, refreshToken) {
    this.tokens = {
      access: accessToken,
      refresh: refreshToken
    };
    localStorage.setItem('access_token', accessToken);
    localStorage.setItem('refresh_token', refreshToken);
  }

  getAccessToken() {
    return this.tokens?.access || localStorage.getItem('access_token');
  }

  getRefreshToken() {
    return this.tokens?.refresh || localStorage.getItem('refresh_token');
  }

  setUser(user) {
    this.user = user;
    localStorage.setItem('user', JSON.stringify(user));
  }

  getUser() {
    if (this.user) return this.user;
    
    const userStr = localStorage.getItem('user');
    if (userStr) {
      try {
        this.user = JSON.parse(userStr);
        return this.user;
      } catch {
        return null;
      }
    }
    return null;
  }

  clearAuth() {
    this.tokens = { access: null, refresh: null };
    this.user = null;
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user');
  }

  isAuthenticated() {
    return !!(this.getAccessToken() && this.getUser());
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
      
      // Handle response structure from backend
      if (data.status === 'success' && data.data) {
        this.setTokens(data.data.access_token, data.data.refresh_token);
        this.setUser(data.data.user);
        console.log('✅ Token refreshed successfully');
        return data.data.access_token;
      } else {
        throw new Error('Invalid response format');
      }
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

    const headers = {
      ...options.headers,
      'Authorization': `Bearer ${accessToken}`
    };

    // Only add Content-Type for non-FormData requests
    if (!(options.body instanceof FormData)) {
      headers['Content-Type'] = 'application/json';
    }

    try {
      let response = await fetch(url, { ...options, headers });

      // If unauthorized, try refreshing token
      if (response.status === 401) {
        console.log('⚠️ 401 Unauthorized - Token expired, refreshing...');
        
        try {
          const newAccessToken = await this.refreshAccessToken();
          headers['Authorization'] = `Bearer ${newAccessToken}`;
          
          // Retry with new token
          console.log('🔁 Retrying request with new token...');
          response = await fetch(url, { ...options, headers });
          
          if (response.ok) {
            console.log('✅ Request successful after token refresh');
          }
        } catch (refreshError) {
          console.error('❌ Refresh failed, redirecting to login...');
          this.clearAuth();
          window.location.reload();
          throw new Error('Session expired. Please login again.');
        }
      }

      return response;
    } catch (error) {
      console.error('Authenticated fetch error:', error);
      throw error;
    }
  }

  // Helper methods for common API calls
  async get(endpoint) {
    return this.authenticatedFetch(`${API_URL}${endpoint}`, {
      method: 'GET'
    });
  }

  async post(endpoint, data) {
    return this.authenticatedFetch(`${API_URL}${endpoint}`, {
      method: 'POST',
      body: JSON.stringify(data)
    });
  }

  async patch(endpoint, data) {
    return this.authenticatedFetch(`${API_URL}${endpoint}`, {
      method: 'PATCH',
      body: JSON.stringify(data)
    });
  }

  async delete(endpoint) {
    return this.authenticatedFetch(`${API_URL}${endpoint}`, {
      method: 'DELETE'
    });
  }

  async uploadFile(endpoint, file, additionalData = {}) {
    const formData = new FormData();
    formData.append('file', file);
    
    Object.keys(additionalData).forEach(key => {
      formData.append(key, additionalData[key]);
    });

    return this.authenticatedFetch(`${API_URL}${endpoint}`, {
      method: 'POST',
      body: formData
    });
  }
}

// Create singleton instance
const authService = new AuthService();

// ============================================================================
// WEBSOCKET SERVICE - For real-time notifications and chat
// ============================================================================
class WebSocketService {
  constructor() {
    this.notificationWs = null;
    this.chatWs = null;
    this.notificationListeners = new Set();
    this.chatListeners = new Set();
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
  }

  // Connect to notifications WebSocket
  connectNotifications(token) {
    if (this.notificationWs && this.notificationWs.readyState === WebSocket.OPEN) {
      console.log('Notification WebSocket already connected');
      return;
    }

    try {
      const wsUrl = `ws://localhost:8000/ws/notifications?token=${token}`;
      this.notificationWs = new WebSocket(wsUrl);

      this.notificationWs.onopen = () => {
        console.log('🔗 Notification WebSocket connected');
        this.reconnectAttempts = 0;
      };

      this.notificationWs.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          console.log('📨 Notification received:', data);
          this.notifyNotificationListeners(data);
        } catch (error) {
          console.error('Error parsing notification:', error);
        }
      };

      this.notificationWs.onerror = (error) => {
        console.error('Notification WebSocket error:', error);
      };

      this.notificationWs.onclose = () => {
        console.log('Notification WebSocket disconnected');
        this.attemptReconnectNotifications(token);
      };
    } catch (error) {
      console.error('Notification WebSocket connection error:', error);
    }
  }

  // Connect to chat WebSocket
  connectChat(token) {
    if (this.chatWs && this.chatWs.readyState === WebSocket.OPEN) {
      console.log('Chat WebSocket already connected');
      return;
    }

    try {
      const wsUrl = `ws://localhost:8000/ws/chat?token=${token}`;
      this.chatWs = new WebSocket(wsUrl);

      this.chatWs.onopen = () => {
        console.log('💬 Chat WebSocket connected');
      };

      this.chatWs.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          console.log('💬 Chat message received:', data);
          this.notifyChatListeners(data);
        } catch (error) {
          console.error('Error parsing chat message:', error);
        }
      };

      this.chatWs.onerror = (error) => {
        console.error('Chat WebSocket error:', error);
      };

      this.chatWs.onclose = () => {
        console.log('Chat WebSocket disconnected');
      };
    } catch (error) {
      console.error('Chat WebSocket connection error:', error);
    }
  }

  sendChatMessage(message) {
    if (this.chatWs && this.chatWs.readyState === WebSocket.OPEN) {
      this.chatWs.send(JSON.stringify({ message }));
    } else {
      console.error('Chat WebSocket not connected');
    }
  }

  attemptReconnectNotifications(token) {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);
      console.log(`Attempting to reconnect notifications in ${delay}ms...`);
      
      setTimeout(() => {
        this.connectNotifications(token);
      }, delay);
    }
  }

  disconnectAll() {
    if (this.notificationWs) {
      this.notificationWs.close();
      this.notificationWs = null;
    }
    if (this.chatWs) {
      this.chatWs.close();
      this.chatWs = null;
    }
  }

  addNotificationListener(callback) {
    this.notificationListeners.add(callback);
  }

  removeNotificationListener(callback) {
    this.notificationListeners.delete(callback);
  }

  addChatListener(callback) {
    this.chatListeners.add(callback);
  }

  removeChatListener(callback) {
    this.chatListeners.delete(callback);
  }

  notifyNotificationListeners(data) {
    this.notificationListeners.forEach(callback => {
      try {
        callback(data);
      } catch (error) {
        console.error('Error in notification listener:', error);
      }
    });
  }

  notifyChatListeners(data) {
    this.chatListeners.forEach(callback => {
      try {
        callback(data);
      } catch (error) {
        console.error('Error in chat listener:', error);
      }
    });
  }
}

const wsService = new WebSocketService();

// ============================================================================
// MAIN APP COMPONENT
// ============================================================================
function App() {
  const [currentPage, setCurrentPage] = useState('loading');
  const [user, setUser] = useState(null);
  const [notifications, setNotifications] = useState([]);
  const [isValidating, setIsValidating] = useState(true);

  // Initialize app and check for existing session
  useEffect(() => {
    const initializeApp = async () => {
      setIsValidating(true);
      
      // Check if user is authenticated
      if (authService.isAuthenticated()) {
        const savedUser = authService.getUser();
        setUser(savedUser);
        
        // Navigate to appropriate dashboard
        navigateToDashboard(savedUser.role);
        
        // Connect to WebSocket for notifications
        const accessToken = authService.getAccessToken();
        if (accessToken) {
          wsService.connectNotifications(accessToken);
          if (savedUser.role === 'patient') {
            wsService.connectChat(accessToken);
          }
        }
        
        console.log('✅ Session restored:', savedUser.name);
      } else {
        setCurrentPage('login');
      }
      
      setIsValidating(false);
    };

    initializeApp();

    // Cleanup on unmount
    return () => {
      wsService.disconnectAll();
    };
  }, []);

  // Handle notifications
  useEffect(() => {
    const handleNotification = (notification) => {
      setNotifications(prev => [notification, ...prev].slice(0, 10));
      
      // Show browser notification if permitted
      if ('Notification' in window && Notification.permission === 'granted') {
        new Notification('Digital Health Card', {
          body: notification.message || 'New notification',
          icon: '/logo192.png'
        });
      }
    };

    wsService.addNotificationListener(handleNotification);

    // Request notification permission
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission();
    }

    return () => {
      wsService.removeNotificationListener(handleNotification);
    };
  }, []);

  const navigateToDashboard = (role) => {
    switch (role) {
      case 'patient':
        setCurrentPage('patient-dashboard');
        break;
      case 'doctor':
        setCurrentPage('doctor-dashboard');
        break;
      case 'admin':
        setCurrentPage('admin-dashboard');
        break;
      default:
        setCurrentPage('login');
    }
  };

  const handleLogin = (userData, accessToken, refreshToken) => {
    console.log('🎉 Login successful:', userData.name);
    
    // Store authentication data
    authService.setTokens(accessToken, refreshToken);
    authService.setUser(userData);
    
    setUser(userData);
    
    // Connect WebSocket
    wsService.connectNotifications(accessToken);
    if (userData.role === 'patient') {
      wsService.connectChat(accessToken);
    }
    
    // Navigate to appropriate dashboard
    navigateToDashboard(userData.role);
  };

  const handleLogout = () => {
    console.log('👋 Logging out...');
    
    // Disconnect WebSocket
    wsService.disconnectAll();
    
    // Clear authentication
    authService.clearAuth();
    
    // Reset state
    setUser(null);
    setNotifications([]);
    setCurrentPage('login');
  };

  const handleNavigate = (page) => {
    setCurrentPage(page);
  };

  // Loading screen
  if (isValidating) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-16 w-16 border-b-4 border-blue-600 mb-4"></div>
          <h2 className="text-xl font-semibold text-gray-800">Loading Digital Health Card</h2>
          <p className="text-gray-600 mt-2">Please wait...</p>
        </div>
      </div>
    );
  }

  const renderPage = () => {
    switch (currentPage) {
      case 'login':
        return (
          <LoginPage 
            onLogin={handleLogin}
            onNavigateSignup={() => handleNavigate('signup')}
            apiUrl={API_URL}
          />
        );
      
      case 'signup':
        return (
          <SignupPage 
            onSignup={handleLogin}
            onNavigateLogin={() => handleNavigate('login')}
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
            wsService={wsService}
            notifications={notifications}
            onNavigate={handleNavigate}
          />
        );
      
      case 'doctor-dashboard':
        return (
          <DoctorDashboard 
            user={user}
            onLogout={handleLogout}
            apiUrl={API_URL}
            authService={authService}
            wsService={wsService}
            notifications={notifications}
            onNavigate={handleNavigate}
          />
        );
      
      case 'admin-dashboard':
        return (
          <AdminDashboard 
            user={user}
            onLogout={handleLogout}
            apiUrl={API_URL}
            authService={authService}
            notifications={notifications}
            onNavigate={handleNavigate}
          />
        );
      
      default:
        return (
          <LoginPage 
            onLogin={handleLogin}
            onNavigateSignup={() => handleNavigate('signup')}
            apiUrl={API_URL}
          />
        );
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {renderPage()}
      
      {/* Global notification toast */}
      {notifications.length > 0 && (
        <div className="fixed top-4 right-4 z-50 space-y-2">
          {notifications.slice(0, 3).map((notif, index) => (
            <div
              key={index}
              className="bg-white rounded-lg shadow-lg p-4 max-w-sm animate-slide-in-right border-l-4 border-blue-500"
            >
              <div className="flex items-start">
                <div className="flex-shrink-0">
                  <svg className="h-6 w-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
                  </svg>
                </div>
                <div className="ml-3 flex-1">
                  <p className="text-sm font-medium text-gray-900">
                    {notif.type || 'Notification'}
                  </p>
                  <p className="text-sm text-gray-600 mt-1">
                    {notif.message}
                  </p>
                </div>
                <button
                  onClick={() => {
                    setNotifications(prev => prev.filter((_, i) => i !== index));
                  }}
                  className="ml-4 flex-shrink-0 text-gray-400 hover:text-gray-600"
                >
                  <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default App;
export { authService, wsService, API_URL };

// ============================================================================
// CUSTOM HOOKS FOR API CALLS - Matching backend endpoints
// ============================================================================

// Generic API hook
export const useApi = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const request = async (method, endpoint, data = null) => {
    setLoading(true);
    setError(null);

    try {
      let response;
      switch (method) {
        case 'GET':
          response = await authService.get(endpoint);
          break;
        case 'POST':
          response = await authService.post(endpoint, data);
          break;
        case 'PATCH':
          response = await authService.patch(endpoint, data);
          break;
        case 'DELETE':
          response = await authService.delete(endpoint);
          break;
        default:
          throw new Error('Invalid HTTP method');
      }

      const result = await response.json();
      
      // Handle backend response format
      if (result.status === 'error') {
        throw new Error(result.message || 'API request failed');
      }
      
      setLoading(false);
      return result;
    } catch (err) {
      setError(err.message);
      setLoading(false);
      throw err;
    }
  };

  return { loading, error, request };
};

// Patient API calls - matches /patients/* endpoints
export const usePatient = () => {
  const { request } = useApi();

  return {
    getMyInfo: () => request('GET', '/patients/me'),
    updateMyInfo: (data) => request('PATCH', '/patients/me', data),
    uploadPrescription: async (file) => {
      const response = await authService.uploadFile('/patients/me/prescriptions', file);
      return response.json();
    }
  };
};

// Medication API calls - matches /medications/* endpoints
export const useMedications = () => {
  const { request } = useApi();

  return {
    list: (activeOnly = true) => request('GET', `/medications?active_only=${activeOnly}`),
    create: (data) => request('POST', '/medications', data),
    update: (medId, data) => request('PATCH', `/medications/${medId}`, data),
    logIntake: (medId, wasTaken, notes) => 
      request('POST', `/medications/${medId}/log`, { was_taken: wasTaken, notes }),
    getAdherence: (days = 30) => request('GET', `/medications/adherence?days=${days}`)
  };
};

// Appointment API calls - matches /appointments/* endpoints
export const useAppointments = () => {
  const { request } = useApi();

  return {
    list: (upcomingOnly = true) => request('GET', `/appointments?upcoming_only=${upcomingOnly}`),
    create: (data) => request('POST', '/appointments', data),
    updateStatus: (apptId, status) => 
      request('PATCH', `/appointments/${apptId}/status`, { status })
  };
};

// Vitals API calls - matches /vitals/* endpoints
export const useVitals = () => {
  const { request } = useApi();

  return {
    add: (data) => request('POST', '/vitals', data),
    list: (vitalType = null, limit = 50) => {
      const params = new URLSearchParams();
      if (vitalType) params.append('vital_type', vitalType);
      params.append('limit', limit);
      return request('GET', `/vitals?${params.toString()}`);
    },
    getTrend: (vitalType, days = 30) => 
      request('GET', `/vitals/${vitalType}/trend?days=${days}`)
  };
};

// Lab Results API calls - matches /lab-results/* endpoints
export const useLabResults = () => {
  const { request } = useApi();

  return {
    list: (limit = 10) => request('GET', `/lab-results?limit=${limit}`),
    add: async (testDate, labName, tests, file = null) => {
      const formData = new FormData();
      formData.append('test_date', testDate);
      formData.append('lab_name', labName);
      formData.append('tests', JSON.stringify(tests));
      if (file) formData.append('file', file);
      
      const response = await authService.authenticatedFetch(
        `${API_URL}/lab-results`,
        { method: 'POST', body: formData }
      );
      return response.json();
    }
  };
};

// AI Chat API calls - matches /ai/chat endpoint
export const useAIChat = () => {
  const { request } = useApi();

  return {
    sendMessage: (message, sessionId = null) => 
      request('POST', '/ai/chat', { message, session_id: sessionId })
  };
};

// Health Analytics - matches /analytics/* endpoints
export const useHealthAnalytics = () => {
  const { request } = useApi();

  return {
    getHealthScore: () => request('GET', '/analytics/health-score')
  };
};

// Insurance API calls - matches /insurance/* endpoints
export const useInsurance = () => {
  const { request } = useApi();

  return {
    listPolicies: () => request('GET', '/insurance/policies'),
    addPolicy: (data) => request('POST', '/insurance/policies', data)
  };
};

// Wearables API calls - matches /wearables/* endpoints
export const useWearables = () => {
  const { request } = useApi();

  return {
    connect: (deviceType, accessToken, refreshToken = null) =>
      request('POST', '/wearables/connect', {
        device_type: deviceType,
        access_token: accessToken,
        refresh_token: refreshToken
      }),
    sync: (deviceId, data) =>
      request('POST', '/wearables/sync', { device_id: deviceId, data })
  };
};

// Family Members API calls - matches /family/* endpoints
export const useFamilyMembers = () => {
  const { request } = useApi();

  return {
    list: () => request('GET', '/family/members'),
    add: (name, relationship, dateOfBirth = null, memberEmail = null) =>
      request('POST', '/family/members', {
        name,
        relationship,
        date_of_birth: dateOfBirth,
        member_email: memberEmail
      })
  };
};

// Consent Management API calls - matches /consent/* endpoints
export const useConsent = () => {
  const { request } = useApi();

  return {
    list: () => request('GET', '/consent'),
    manage: (data) => request('POST', '/consent', data)
  };
};

// Hospital Search API calls - matches /hospitals/* endpoints
export const useHospitalSearch = () => {
  const { request } = useApi();

  return {
    searchNearby: (latitude, longitude, radiusKm = 5) =>
      request('GET', `/hospitals/nearby?latitude=${latitude}&longitude=${longitude}&radius_km=${radiusKm}`)
  };
};

// Doctor API calls - matches /doctors/* endpoints
export const useDoctors = () => {
  const { request } = useApi();

  return {
    getMyInfo: () => request('GET', '/doctors/me'),
    getMyPatients: () => request('GET', '/doctors/me/patients')
  };
};

// Admin API calls - matches /admin/* endpoints
export const useAdmin = () => {
  const { request } = useApi();

  return {
    listUsers: (skip = 0, limit = 50) => 
      request('GET', `/admin/users?skip=${skip}&limit=${limit}`),
    getStats: () => request('GET', '/admin/stats'),
    getAuditLogs: (userId = null, action = null, limit = 50) => {
      const params = new URLSearchParams();
      if (userId) params.append('user_id', userId);
      if (action) params.append('action', action);
      params.append('limit', limit);
      return request('GET', `/audit/logs?${params.toString()}`);
    }
  };
};

// Emergency Access - matches /emergency/* endpoint (public, no auth)
export const getEmergencyInfo = async (qrToken) => {
  const response = await fetch(`${API_URL}/emergency/${qrToken}`);
  return response.json();
};