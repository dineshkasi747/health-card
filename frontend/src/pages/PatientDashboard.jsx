// PatientDashboard.jsx - Complete Dashboard with All Pages
import React, { useState, useEffect } from 'react';
import OverviewPage from './OverviewPage';
import ProfilePage from './ProfilePage';
import QRCodePage from './QRCodePage';
import PrescriptionsPage from './PrescriptionsPage';
import MedicationsPage from './MedicationsPage';
import AppointmentsPage from './AppointmentsPage';
import VitalsPage from './VitalsPage';
import LabResultsPage from './LabResultsPage';
import AIChat from './AIChat';
import EmergencyContacts from './EmergencyContacts';

const API_URL = 'http://localhost:8000';

// ============================================================================
// MAIN PATIENT DASHBOARD WRAPPER
// ============================================================================
const PatientDashboard = ({ user, onLogout, authService }) => {
  const [currentView, setCurrentView] = useState('overview');
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [patientData, setPatientData] = useState(null);
  const [loading, setLoading] = useState(true);

  // Menu items configuration
  const menuItems = [
    { id: 'overview', name: 'Dashboard', icon: '🏠' },
    { id: 'profile', name: 'My Profile', icon: '👤' },
    { id: 'qr-code', name: 'Emergency QR', icon: '📱' },
    { id: 'prescriptions', name: 'Prescriptions', icon: '📄' },
    { id: 'medications', name: 'Medications', icon: '💊' },
    { id: 'appointments', name: 'Appointments', icon: '📅' },
    { id: 'vitals', name: 'Track Vitals', icon: '❤️' },
    { id: 'lab-results', name: 'Lab Results', icon: '🧪' },
    { id: 'ai-chat', name: 'AI Assistant', icon: '🤖' },
    { id: 'emergency', name: 'Emergency Contacts', icon: '🚨' }
  ];

  // Load patient data on mount
  useEffect(() => {
    fetchPatientData();
  }, []);

  const fetchPatientData = async () => {
    try {
      setLoading(true);
      const response = await authService.get('/patients/me');
      const result = await response.json();
      
      if (result.status === 'success') {
        setPatientData(result.data);
      }
    } catch (error) {
      console.error('Error fetching patient data:', error);
    } finally {
      setLoading(false);
    }
  };

  // Render the current view based on selection
  const renderView = () => {
    const props = { 
      patientData, 
      authService, 
      onUpdate: fetchPatientData 
    };

    switch (currentView) {
      case 'overview':
        return <OverviewPage {...props} />;
      case 'profile':
        return <ProfilePage {...props} />;
      case 'qr-code':
        return <QRCodePage {...props} />;
      case 'prescriptions':
        return <PrescriptionsPage {...props} />;
      case 'medications':
        return <MedicationsPage {...props} />;
      case 'appointments':
        return <AppointmentsPage {...props} />;
      case 'vitals':
        return <VitalsPage {...props} />;
      case 'lab-results':
        return <LabResultsPage {...props} />;
      case 'ai-chat':
        return <AIChat {...props} />;
      case 'emergency':
        return <EmergencyContacts {...props} />;
      default:
        return <OverviewPage {...props} />;
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-16 w-16 border-b-4 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600 text-lg">Loading your dashboard...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 flex">
      {/* Sidebar */}
      <div 
        className={`${
          sidebarOpen ? 'w-64' : 'w-20'
        } bg-white border-r border-gray-200 transition-all duration-300 flex flex-col`}
      >
        {/* Sidebar Header */}
        <div className="p-4 border-b border-gray-200 flex items-center justify-between">
          {sidebarOpen && (
            <div className="flex items-center">
              <span className="text-2xl mr-2">🏥</span>
              <span className="text-lg font-semibold text-gray-800">Health Card</span>
            </div>
          )}
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="p-2 rounded-lg hover:bg-gray-100 transition-colors"
            title={sidebarOpen ? 'Collapse sidebar' : 'Expand sidebar'}
          >
            {sidebarOpen ? (
              <span className="text-gray-600">◀</span>
            ) : (
              <span className="text-gray-600">▶</span>
            )}
          </button>
        </div>

        {/* Navigation Menu */}
        <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
          {menuItems.map((item) => (
            <button
              key={item.id}
              onClick={() => setCurrentView(item.id)}
              className={`w-full flex items-center ${
                sidebarOpen ? 'px-4 justify-start' : 'justify-center px-2'
              } py-3 rounded-lg transition-all ${
                currentView === item.id
                  ? 'bg-blue-50 text-blue-600 shadow-sm'
                  : 'text-gray-700 hover:bg-gray-100'
              }`}
              title={!sidebarOpen ? item.name : ''}
            >
              <span className="text-xl">{item.icon}</span>
              {sidebarOpen && (
                <span className="ml-3 font-medium">{item.name}</span>
              )}
            </button>
          ))}
        </nav>

        {/* User Profile Section */}
        <div className="border-t border-gray-200 p-4">
          {sidebarOpen ? (
            <div className="flex items-center justify-between">
              <div className="flex items-center">
                <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-full flex items-center justify-center text-white font-bold">
                  {user?.name?.charAt(0).toUpperCase() || 'U'}
                </div>
                <div className="ml-3">
                  <p className="text-sm font-medium text-gray-800 truncate max-w-[120px]">
                    {user?.name || 'User'}
                  </p>
                  <p className="text-xs text-gray-500 truncate max-w-[120px]">
                    {user?.email || 'user@example.com'}
                  </p>
                </div>
              </div>
              <button
                onClick={onLogout}
                className="p-2 hover:bg-red-50 rounded-lg text-red-600 transition-colors"
                title="Logout"
              >
                🚪
              </button>
            </div>
          ) : (
            <div className="flex flex-col items-center space-y-2">
              <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-full flex items-center justify-center text-white font-bold">
                {user?.name?.charAt(0).toUpperCase() || 'U'}
              </div>
              <button
                onClick={onLogout}
                className="p-2 hover:bg-red-50 rounded-lg text-red-600 transition-colors"
                title="Logout"
              >
                🚪
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto">
        {/* Top Header */}
        <div className="bg-white border-b border-gray-200 px-8 py-6 shadow-sm">
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">
                {menuItems.find((i) => i.id === currentView)?.name || 'Dashboard'}
              </h1>
              <p className="text-sm text-gray-500 mt-1">
                Welcome back, {user?.name?.split(' ')[0] || 'there'}! 👋
              </p>
            </div>
            
            {/* Quick Actions */}
            <div className="flex items-center space-x-3">
              <button
                onClick={() => setCurrentView('ai-chat')}
                className="p-2 rounded-lg hover:bg-blue-50 text-blue-600 transition-colors"
                title="AI Assistant"
              >
                <span className="text-2xl">🤖</span>
              </button>
              <button
                onClick={() => setCurrentView('emergency')}
                className="p-2 rounded-lg hover:bg-red-50 text-red-600 transition-colors"
                title="Emergency Contacts"
              >
                <span className="text-2xl">🚨</span>
              </button>
            </div>
          </div>
        </div>

        {/* Page Content */}
        <div className="p-8">
          {renderView()}
        </div>

        {/* Footer */}
        <footer className="bg-white border-t border-gray-200 px-8 py-4 text-center text-sm text-gray-500">
          <p>© 2024 Health Card. Your health, our priority. 🏥</p>
        </footer>
      </div>
    </div>
  );
};

export default PatientDashboard;