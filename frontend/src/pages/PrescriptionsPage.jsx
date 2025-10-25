import React, { useState, useEffect } from 'react';
import { Home, FileText, MessageCircle, MapPin, Activity, Calendar, User, LogOut, Menu, X } from 'lucide-react';

// Import page components (these will be created separately)
import OverviewPage from './src/OverviewPage.jsx'
import PrescriptionsPage from './pages/PrescriptionsPage';
import AIChatPage from './pages/AIChatPage';
import HospitalsPage from './pages/HospitalsPage';
import VitalsPage from './pages/VitalsPage';
import AppointmentsPage from './pages/AppointmentsPage';

// ============================================================================
// AUTH SERVICE
// ============================================================================
const createAuthService = () => {
  let accessToken = null;
  
  const setToken = (token) => {
    accessToken = token;
  };
  
  const getToken = () => accessToken;
  
  const clearToken = () => {
    accessToken = null;
  };
  
  return {
    setToken,
    getToken,
    clearToken,
    get: async (endpoint) => {
      const response = await fetch(`http://localhost:8000${endpoint}`, {
        headers: { 'Authorization': `Bearer ${getToken()}` }
      });
      return response;
    },
    post: async (endpoint, data) => {
      const response = await fetch(`http://localhost:8000${endpoint}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${getToken()}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
      });
      return response;
    },
    upload: async (endpoint, formData) => {
      const response = await fetch(`http://localhost:8000${endpoint}`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${getToken()}` },
        body: formData
      });
      return response;
    }
  };
};

// ============================================================================
// PATIENT DASHBOARD MAIN COMPONENT
// ============================================================================
const PatientDashboard = () => {
  const [authService] = useState(() => createAuthService());
  const [currentPage, setCurrentPage] = useState('overview');
  const [patientData, setPatientData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [loginEmail, setLoginEmail] = useState('');
  const [loginPassword, setLoginPassword] = useState('');

  // Handle login
  const handleLogin = async () => {
    if (!loginEmail || !loginPassword) {
      alert('Please enter both email and password');
      return;
    }

    try {
      const response = await fetch('http://localhost:8000/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: loginEmail, password: loginPassword })
      });
      
      const data = await response.json();
      
      if (data.status === 'success') {
        authService.setToken(data.data.access_token);
        setPatientData(data.data.user);
        setIsAuthenticated(true);
        fetchPatientData();
      } else {
        alert('Login failed: ' + data.message);
      }
    } catch (error) {
      console.error('Login error:', error);
      alert('Login failed. Please check your credentials.');
    }
  };

  const handleLogout = () => {
    authService.clearToken();
    setIsAuthenticated(false);
    setPatientData(null);
    setLoginEmail('');
    setLoginPassword('');
    setCurrentPage('overview');
  };

  const fetchPatientData = async () => {
    try {
      setLoading(true);
      const response = await authService.get('/patients/me');
      const data = await response.json();
      if (data.status === 'success') {
        setPatientData(data.data);
      }
    } catch (error) {
      console.error('Error:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isAuthenticated) {
      fetchPatientData();
    }
  }, [isAuthenticated]);

  // Login Screen
  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
        <div className="bg-white rounded-2xl shadow-xl p-8 w-full max-w-md">
          <div className="text-center mb-8">
            <div className="text-5xl mb-4">🏥</div>
            <h1 className="text-3xl font-bold text-gray-800 mb-2">Digital Health Card</h1>
            <p className="text-gray-600">Sign in to access your health dashboard</p>
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Email</label>
              <input
                type="email"
                value={loginEmail}
                onChange={(e) => setLoginEmail(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleLogin()}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="your.email@example.com"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Password</label>
              <input
                type="password"
                value={loginPassword}
                onChange={(e) => setLoginPassword(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleLogin()}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="••••••••"
              />
            </div>

            <button
              onClick={handleLogin}
              className="w-full bg-blue-600 text-white py-3 rounded-lg font-medium hover:bg-blue-700 transition"
            >
              Sign In
            </button>
          </div>

          <div className="mt-6 text-center text-sm text-gray-600">
            <p>Demo Account:</p>
            <p className="font-mono text-xs mt-1">patient@example.com / password123</p>
          </div>
        </div>
      </div>
    );
  }

  const navItems = [
    { id: 'overview', name: 'Overview', icon: Home },
    { id: 'prescriptions', name: 'Prescriptions', icon: FileText },
    { id: 'ai-chat', name: 'AI Assistant', icon: MessageCircle },
    { id: 'hospitals', name: 'Hospitals', icon: MapPin },
    { id: 'vitals', name: 'Vitals', icon: Activity },
    { id: 'appointments', name: 'Appointments', icon: Calendar },
  ];

  // Render current page
  const renderPage = () => {
    const pageProps = {
      authService,
      patientData,
      setCurrentPage
    };

    switch (currentPage) {
      case 'overview':
        return <OverviewPage {...pageProps} />;
      case 'prescriptions':
        return <PrescriptionsPage {...pageProps} />;
      case 'ai-chat':
        return <AIChatPage {...pageProps} />;
      case 'hospitals':
        return <HospitalsPage {...pageProps} />;
      case 'vitals':
        return <VitalsPage {...pageProps} />;
      case 'appointments':
        return <AppointmentsPage {...pageProps} />;
      default:
        return <OverviewPage {...pageProps} />;
    }
  };

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar */}
      <div className={`${sidebarOpen ? 'w-64' : 'w-20'} bg-white border-r border-gray-200 transition-all duration-300 flex flex-col`}>
        <div className="p-4 border-b border-gray-200 flex items-center justify-between">
          {sidebarOpen && (
            <div className="flex items-center gap-2">
              <span className="text-2xl">🏥</span>
              <span className="font-bold text-gray-800">HealthCard</span>
            </div>
          )}
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="p-2 hover:bg-gray-100 rounded-lg transition"
          >
            {sidebarOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>

        <nav className="flex-1 p-4 space-y-2">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.id}
                onClick={() => setCurrentPage(item.id)}
                className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition ${
                  currentPage === item.id
                    ? 'bg-blue-50 text-blue-600 font-medium'
                    : 'text-gray-600 hover:bg-gray-50'
                }`}
              >
                <Icon size={20} />
                {sidebarOpen && <span>{item.name}</span>}
              </button>
            );
          })}
        </nav>

        <div className="p-4 border-t border-gray-200">
          {patientData && (
            <div className={`${sidebarOpen ? 'flex items-center gap-3 mb-3' : 'flex justify-center mb-3'}`}>
              <div className="w-10 h-10 bg-blue-100 rounded-full flex items-center justify-center">
                <User size={20} className="text-blue-600" />
              </div>
              {sidebarOpen && (
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-gray-800 truncate">{patientData.name}</p>
                  <p className="text-xs text-gray-500 truncate">{patientData.email}</p>
                </div>
              )}
            </div>
          )}
          <button
            onClick={handleLogout}
            className={`w-full flex items-center ${sidebarOpen ? 'gap-3' : 'justify-center'} px-4 py-3 text-red-600 hover:bg-red-50 rounded-lg transition`}
          >
            <LogOut size={20} />
            {sidebarOpen && <span>Logout</span>}
          </button>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-auto">
        <div className="p-8">
          <div className="mb-8">
            <h1 className="text-3xl font-bold text-gray-800 mb-2">
              {navItems.find(item => item.id === currentPage)?.name || 'Dashboard'}
            </h1>
            <p className="text-gray-600">
              {currentPage === 'overview' && 'Welcome back! Here\'s your health overview.'}
              {currentPage === 'prescriptions' && 'Manage and upload your prescriptions with AI analysis.'}
              {currentPage === 'ai-chat' && 'Ask your AI health assistant anything.'}
              {currentPage === 'hospitals' && 'Find nearby healthcare facilities.'}
              {currentPage === 'vitals' && 'Track your vital signs and health metrics.'}
              {currentPage === 'appointments' && 'Manage your doctor appointments.'}
            </p>
          </div>

          {loading ? (
            <div className="text-center py-12">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
              <p className="text-gray-600 mt-4">Loading...</p>
            </div>
          ) : (
            renderPage()
          )}
        </div>
      </div>
    </div>
  );
};

export default PatientDashboard;