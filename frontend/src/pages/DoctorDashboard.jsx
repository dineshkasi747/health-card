import React, { useState, useEffect } from 'react';
import { Calendar, Users, Clock, FileText, Activity, Bell, Search, Filter, Download, Eye, Plus, Video, Phone, MessageSquare } from 'lucide-react';

function DoctorDashboard({ user, onLogout, apiUrl, authService }) {
  const [activeTab, setActiveTab] = useState('overview');
  const [patients, setPatients] = useState([]);
  const [appointments, setAppointments] = useState([]);
  const [selectedPatient, setSelectedPatient] = useState(null);
  const [notifications, setNotifications] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [stats, setStats] = useState({
    totalPatients: 0,
    todayAppointments: 0,
    pendingAppointments: 0,
    completedToday: 0
  });

  useEffect(() => {
    loadDashboardData();
  }, []);

  const loadDashboardData = async () => {
    setLoading(true);
    setError('');
    try {
      await Promise.all([
        loadPatients(),
        loadAppointments(),
        loadNotifications()
      ]);
    } catch (err) {
      console.error('Error loading dashboard data:', err);
      if (err.message.includes('CORS') || err.message.includes('Failed to fetch')) {
        setError('Unable to connect to server. Please ensure the backend is running and CORS is configured.');
      } else {
        setError(err.message);
      }
    } finally {
      setLoading(false);
    }
  };

  const loadPatients = async () => {
    try {
      // Try the correct endpoint - typically /doctors/{doctor_id}/patients or /doctors/me/patients
      // If that fails, try alternative endpoints
      let response;
      
      try {
        response = await authService.get('/doctors/me/patients');
      } catch (firstError) {
        console.warn('First endpoint failed, trying alternative...');
        // Try alternative endpoint structure
        response = await authService.get(`/doctors/${user.id}/patients`);
      }

      if (!response.ok) {
        const errorData = await response.json().catch(() => null);
        throw new Error(errorData?.detail || 'Failed to load patients');
      }

      const data = await response.json();
      const patientsList = data.data || data.patients || [];
      setPatients(patientsList);
      setStats(prev => ({ ...prev, totalPatients: patientsList.length }));
    } catch (err) {
      console.error('Error loading patients:', err);
      // Don't throw - allow dashboard to load even if patients fail
      setPatients([]);
    }
  };

  const loadAppointments = async () => {
    try {
      // Try with query parameter
      const response = await authService.get('/appointments?doctor_id=' + user.id);

      if (!response.ok) {
        const errorData = await response.json().catch(() => null);
        throw new Error(errorData?.detail || 'Failed to load appointments');
      }

      const data = await response.json();
      const appts = data.data || data.appointments || [];
      setAppointments(appts);

      const today = new Date().toDateString();
      const todayAppts = appts.filter(a => 
        new Date(a.scheduled_date || a.date).toDateString() === today
      );
      const pending = appts.filter(a => 
        a.status === 'scheduled' || a.status === 'confirmed' || a.status === 'pending'
      );
      const completed = todayAppts.filter(a => a.status === 'completed');

      setStats(prev => ({
        ...prev,
        todayAppointments: todayAppts.length,
        pendingAppointments: pending.length,
        completedToday: completed.length
      }));
    } catch (err) {
      console.error('Error loading appointments:', err);
      // Don't throw - allow dashboard to load even if appointments fail
      setAppointments([]);
    }
  };

  const loadNotifications = async () => {
    // Mock notifications - implement actual endpoint if available
    setNotifications([
      { id: 1, type: 'prescription_uploaded', message: 'New prescription uploaded by John Doe', time: '2 hours ago', read: false },
      { id: 2, type: 'appointment_reminder', message: 'Appointment with Jane Smith in 30 minutes', time: '30 minutes ago', read: false }
    ]);
  };

  const viewPatientDetails = async (patientId) => {
    setError('');
    try {
      const response = await authService.get(`/patients/${patientId}`);

      if (!response.ok) {
        const errorData = await response.json().catch(() => null);
        throw new Error(errorData?.detail || 'Failed to load patient details');
      }

      const data = await response.json();
      setSelectedPatient(data.data || data.patient || data);
      setActiveTab('patient-details');
    } catch (err) {
      console.error('Error loading patient details:', err);
      setError('Failed to load patient details: ' + err.message);
    }
  };

  const updateAppointmentStatus = async (appointmentId, newStatus) => {
    setError('');
    try {
      const response = await authService.patch(
        `/appointments/${appointmentId}`,
        { status: newStatus }
      );

      if (!response.ok) {
        const errorData = await response.json().catch(() => null);
        throw new Error(errorData?.detail || 'Failed to update appointment');
      }

      await loadAppointments();
      setError('');
    } catch (err) {
      console.error('Error updating appointment:', err);
      setError('Failed to update appointment: ' + err.message);
    }
  };

  const handleScanQR = async (qrToken) => {
    setError('');
    try {
      const response = await authService.get(`/qr/resolve/${qrToken}`);

      if (!response.ok) {
        const errorData = await response.json().catch(() => null);
        throw new Error(errorData?.detail || 'Invalid QR code');
      }

      const data = await response.json();
      setSelectedPatient(data.data || data.patient || data);
      setActiveTab('patient-details');
    } catch (err) {
      console.error('Error scanning QR:', err);
      setError('Invalid QR code: ' + err.message);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">Doctor Dashboard</h1>
              <p className="text-sm text-gray-600">Welcome, Dr. {user.name}</p>
            </div>
            <div className="flex items-center gap-4">
              <button className="relative p-2 text-gray-600 hover:bg-gray-100 rounded-lg transition">
                <Bell className="h-5 w-5" />
                {notifications.filter(n => !n.read).length > 0 && (
                  <span className="absolute top-1 right-1 h-2 w-2 bg-red-500 rounded-full"></span>
                )}
              </button>
              <button
                onClick={onLogout}
                className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition"
              >
                Logout
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Navigation Tabs */}
      <div className="bg-white border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <nav className="flex space-x-8">
            {[
              { id: 'overview', label: 'Overview', icon: Activity },
              { id: 'patients', label: 'Patients', icon: Users },
              { id: 'appointments', label: 'Appointments', icon: Calendar },
              { id: 'scan-qr', label: 'Scan QR', icon: Search }
            ].map(tab => {
              const Icon = tab.icon;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center gap-2 py-4 px-1 border-b-2 font-medium text-sm transition ${
                    activeTab === tab.id
                      ? 'border-blue-500 text-blue-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                  }`}
                >
                  <Icon className="h-4 w-4" />
                  {tab.label}
                </button>
              );
            })}
          </nav>
        </div>
      </div>

      {/* Error Alert */}
      {error && (
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mt-4">
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg flex justify-between items-center">
            <div className="flex-1">
              <p className="text-sm font-medium">Error</p>
              <p className="text-sm">{error}</p>
            </div>
            <button onClick={() => setError('')} className="text-red-700 hover:text-red-900 ml-4">
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>
      )}

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {activeTab === 'overview' && (
          <OverviewTab stats={stats} appointments={appointments} patients={patients} />
        )}

        {activeTab === 'patients' && (
          <PatientsTab
            patients={patients}
            loading={loading}
            onViewDetails={viewPatientDetails}
          />
        )}

        {activeTab === 'appointments' && (
          <AppointmentsTab
            appointments={appointments}
            loading={loading}
            onUpdateStatus={updateAppointmentStatus}
          />
        )}

        {activeTab === 'scan-qr' && (
          <QRScannerTab onScan={handleScanQR} />
        )}

        {activeTab === 'patient-details' && selectedPatient && (
          <PatientDetailsTab
            patient={selectedPatient}
            onClose={() => setActiveTab('patients')}
          />
        )}
      </main>
    </div>
  );
}

// Overview Tab Component
function OverviewTab({ stats, appointments, patients }) {
  const today = new Date().toDateString();
  const todayAppointments = appointments.filter(a => 
    new Date(a.scheduled_date || a.date).toDateString() === today
  );

  return (
    <div className="space-y-6">
      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard
          title="Total Patients"
          value={stats.totalPatients}
          icon={Users}
          color="blue"
        />
        <StatCard
          title="Today's Appointments"
          value={stats.todayAppointments}
          icon={Calendar}
          color="green"
        />
        <StatCard
          title="Pending"
          value={stats.pendingAppointments}
          icon={Clock}
          color="yellow"
        />
        <StatCard
          title="Completed Today"
          value={stats.completedToday}
          icon={FileText}
          color="purple"
        />
      </div>

      {/* Today's Schedule */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Today's Schedule</h2>
          {todayAppointments.length > 0 ? (
            <div className="space-y-3">
              {todayAppointments.slice(0, 5).map(appt => (
                <div key={appt.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                  <div className="flex-1">
                    <p className="font-medium text-gray-900">{appt.patient_name || 'Unknown Patient'}</p>
                    <p className="text-sm text-gray-600">{appt.scheduled_time || appt.time || 'No time set'}</p>
                  </div>
                  <span className={`px-3 py-1 rounded-full text-xs font-medium ${
                    appt.status === 'completed' ? 'bg-green-100 text-green-800' :
                    appt.status === 'confirmed' ? 'bg-blue-100 text-blue-800' :
                    'bg-yellow-100 text-yellow-800'
                  }`}>
                    {appt.status}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-center text-gray-500 py-8">No appointments scheduled for today</p>
          )}
        </div>

        {/* Recent Patients */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Recent Patients</h2>
          {patients.length > 0 ? (
            <div className="space-y-3">
              {patients.slice(0, 5).map(patient => (
                <div key={patient.id} className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                  <div className="h-10 w-10 bg-blue-100 rounded-full flex items-center justify-center">
                    <span className="text-blue-600 font-medium">
                      {patient.user?.name?.charAt(0) || patient.name?.charAt(0) || '?'}
                    </span>
                  </div>
                  <div className="flex-1">
                    <p className="font-medium text-gray-900">{patient.user?.name || patient.name || 'Unknown'}</p>
                    <p className="text-sm text-gray-600">
                      {patient.prescriptions?.length || 0} prescriptions
                    </p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-center text-gray-500 py-8">No patients yet</p>
          )}
        </div>
      </div>
    </div>
  );
}

// Stat Card Component
function StatCard({ title, value, icon: Icon, color }) {
  const colorClasses = {
    blue: 'bg-blue-100 text-blue-600',
    green: 'bg-green-100 text-green-600',
    yellow: 'bg-yellow-100 text-yellow-600',
    purple: 'bg-purple-100 text-purple-600'
  };

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-gray-600">{title}</p>
          <p className="text-3xl font-bold text-gray-900 mt-2">{value}</p>
        </div>
        <div className={`p-3 rounded-lg ${colorClasses[color]}`}>
          <Icon className="h-6 w-6" />
        </div>
      </div>
    </div>
  );
}

// Patients Tab Component
function PatientsTab({ patients, loading, onViewDetails }) {
  const [searchTerm, setSearchTerm] = useState('');
  const [filteredPatients, setFilteredPatients] = useState(patients);

  useEffect(() => {
    const filtered = patients.filter(p =>
      (p.user?.name || p.name || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
      (p.user?.email || p.email || '').toLowerCase().includes(searchTerm.toLowerCase())
    );
    setFilteredPatients(filtered);
  }, [searchTerm, patients]);

  return (
    <div className="space-y-6">
      {/* Search Bar */}
      <div className="bg-white rounded-lg shadow p-4">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
          <input
            type="text"
            placeholder="Search patients by name or email..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
      </div>

      {/* Patients List */}
      <div className="bg-white rounded-lg shadow">
        <div className="p-6 border-b">
          <h2 className="text-lg font-semibold text-gray-900">
            All Patients ({filteredPatients.length})
          </h2>
        </div>

        {loading ? (
          <div className="flex justify-center items-center py-12">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
          </div>
        ) : filteredPatients.length > 0 ? (
          <div className="divide-y">
            {filteredPatients.map(patient => (
              <div key={patient.id} className="p-6 hover:bg-gray-50 transition">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div className="h-12 w-12 bg-blue-100 rounded-full flex items-center justify-center">
                      <span className="text-blue-600 font-semibold text-lg">
                        {(patient.user?.name || patient.name || '?').charAt(0)}
                      </span>
                    </div>
                    <div>
                      <p className="font-semibold text-gray-900">{patient.user?.name || patient.name || 'Unknown'}</p>
                      <p className="text-sm text-gray-600">{patient.user?.email || patient.email || 'No email'}</p>
                      {(patient.user?.phone || patient.phone) && (
                        <p className="text-sm text-gray-500">{patient.user?.phone || patient.phone}</p>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="text-right mr-4">
                      <p className="text-sm text-gray-600">
                        {patient.prescriptions?.length || 0} prescriptions
                      </p>
                      {patient.blood_group && (
                        <p className="text-sm font-medium text-red-600">
                          Blood: {patient.blood_group}
                        </p>
                      )}
                    </div>
                    <button
                      onClick={() => onViewDetails(patient.id)}
                      className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition flex items-center gap-2"
                    >
                      <Eye className="h-4 w-4" />
                      View Details
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-12">
            <Users className="mx-auto h-12 w-12 text-gray-400" />
            <p className="mt-4 text-gray-600">No patients found</p>
          </div>
        )}
      </div>
    </div>
  );
}

// Appointments Tab Component  
function AppointmentsTab({ appointments, loading, onUpdateStatus }) {
  const [filter, setFilter] = useState('all');

  const filteredAppointments = appointments.filter(appt => {
    if (filter === 'all') return true;
    if (filter === 'today') {
      return new Date(appt.scheduled_date || appt.date).toDateString() === new Date().toDateString();
    }
    return appt.status === filter;
  });

  const getStatusColor = (status) => {
    const colors = {
      scheduled: 'bg-yellow-100 text-yellow-800',
      pending: 'bg-yellow-100 text-yellow-800',
      confirmed: 'bg-blue-100 text-blue-800',
      completed: 'bg-green-100 text-green-800',
      cancelled: 'bg-red-100 text-red-800',
      rescheduled: 'bg-purple-100 text-purple-800',
      no_show: 'bg-gray-100 text-gray-800'
    };
    return colors[status] || 'bg-gray-100 text-gray-800';
  };

  const getConsultationIcon = (type) => {
    switch(type) {
      case 'video_call': return Video;
      case 'phone_call': return Phone;
      default: return Users;
    }
  };

  return (
    <div className="space-y-6">
      {/* Filter Tabs */}
      <div className="bg-white rounded-lg shadow p-4">
        <div className="flex gap-2 flex-wrap">
          {['all', 'today', 'scheduled', 'confirmed', 'completed'].map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
                filter === f
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              {f.charAt(0).toUpperCase() + f.slice(1).replace('_', ' ')}
            </button>
          ))}
        </div>
      </div>

      {/* Appointments List */}
      <div className="bg-white rounded-lg shadow">
        <div className="p-6 border-b">
          <h2 className="text-lg font-semibold text-gray-900">
            Appointments ({filteredAppointments.length})
          </h2>
        </div>

        {loading ? (
          <div className="flex justify-center items-center py-12">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
          </div>
        ) : filteredAppointments.length > 0 ? (
          <div className="divide-y">
            {filteredAppointments.map(appt => {
              const ConsultIcon = getConsultationIcon(appt.consultation_type || appt.type);
              return (
                <div key={appt.id} className="p-6 hover:bg-gray-50 transition">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-3 mb-2">
                        <h3 className="font-semibold text-gray-900">{appt.patient_name || 'Unknown Patient'}</h3>
                        <span className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(appt.status)}`}>
                          {appt.status}
                        </span>
                      </div>
                      <div className="space-y-1">
                        <div className="flex items-center gap-2 text-sm text-gray-600">
                          <Calendar className="h-4 w-4" />
                          {new Date(appt.scheduled_date || appt.date).toLocaleDateString('en-US', {
                            weekday: 'short',
                            year: 'numeric',
                            month: 'short',
                            day: 'numeric'
                          })}
                        </div>
                        <div className="flex items-center gap-2 text-sm text-gray-600">
                          <Clock className="h-4 w-4" />
                          {appt.scheduled_time || appt.time || 'No time set'}
                        </div>
                        <div className="flex items-center gap-2 text-sm text-gray-600">
                          <ConsultIcon className="h-4 w-4" />
                          {(appt.consultation_type || appt.type || 'in_person').replace('_', ' ')}
                        </div>
                        {appt.reason && (
                          <p className="text-sm text-gray-600 mt-2">Reason: {appt.reason}</p>
                        )}
                      </div>
                    </div>

                    <div className="flex flex-col gap-2">
                      {(appt.status === 'scheduled' || appt.status === 'pending') && (
                        <>
                          <button
                            onClick={() => onUpdateStatus(appt.id, 'confirmed')}
                            className="px-3 py-1 bg-blue-600 text-white rounded text-sm hover:bg-blue-700 transition"
                          >
                            Confirm
                          </button>
                          <button
                            onClick={() => onUpdateStatus(appt.id, 'cancelled')}
                            className="px-3 py-1 bg-red-600 text-white rounded text-sm hover:bg-red-700 transition"
                          >
                            Cancel
                          </button>
                        </>
                      )}
                      {appt.status === 'confirmed' && (
                        <button
                          onClick={() => onUpdateStatus(appt.id, 'completed')}
                          className="px-3 py-1 bg-green-600 text-white rounded text-sm hover:bg-green-700 transition"
                        >
                          Complete
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="text-center py-12">
            <Calendar className="mx-auto h-12 w-12 text-gray-400" />
            <p className="mt-4 text-gray-600">No appointments found</p>
          </div>
        )}
      </div>
    </div>
  );
}

// QR Scanner Tab
function QRScannerTab({ onScan }) {
  const [qrToken, setQrToken] = useState('');
  const [scanning, setScanning] = useState(false);

  const handleSubmit = async () => {
    if (!qrToken.trim()) return;
    
    setScanning(true);
    try {
      await onScan(qrToken.trim());
      setQrToken('');
    } finally {
      setScanning(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto">
      <div className="bg-white rounded-lg shadow p-8">
        <div className="text-center mb-8">
          <div className="mx-auto h-20 w-20 bg-blue-100 rounded-full flex items-center justify-center mb-4">
            <Search className="h-10 w-10 text-blue-600" />
          </div>
          <h2 className="text-2xl font-bold text-gray-900">Scan Patient QR Code</h2>
          <p className="text-gray-600 mt-2">Enter the QR token to access patient records</p>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              QR Token
            </label>
            <input
              type="text"
              value={qrToken}
              onChange={(e) => setQrToken(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleSubmit()}
              placeholder="Enter or paste QR token"
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              disabled={scanning}
            />
          </div>

          <button
            onClick={handleSubmit}
            disabled={!qrToken.trim() || scanning}
            className="w-full py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition flex items-center justify-center"
          >
            {scanning ? (
              <>
                <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white mr-2"></div>
                Scanning...
              </>
            ) : (
              <>
                <Search className="mr-2 h-5 w-5" />
                Scan QR Code
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

// Patient Details Tab
function PatientDetailsTab({ patient, onClose }) {
  return (
    <div className="bg-white rounded-lg shadow">
      <div className="p-6 border-b flex justify-between items-center">
        <h2 className="text-xl font-semibold text-gray-900">Patient Details</h2>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
          <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <div className="p-6 space-y-6">
        {/* Patient Info */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <h3 className="font-medium text-gray-900 mb-4">Personal Information</h3>
            <div className="space-y-3">
              <div>
                <p className="text-sm text-gray-600">Name</p>
                <p className="font-medium">{patient.user?.name || patient.name || 'Unknown'}</p>
              </div>
              <div>
                <p className="text-sm text-gray-600">Email</p>
                <p className="font-medium">{patient.user?.email || patient.email || 'N/A'}</p>
              </div>
              {(patient.user?.phone || patient.phone) && (
                <div>
                  <p className="text-sm text-gray-600">Phone</p>
                  <p className="font-medium">{patient.user?.phone || patient.phone}</p>
                </div>
              )}
              {patient.blood_group && (
                <div>
                  <p className="text-sm text-gray-600">Blood Group</p>
                  <p className="font-medium text-red-600">{patient.blood_group}</p>
                </div>
              )}
            </div>
          </div>

          <div>
            <h3 className="font-medium text-gray-900 mb-4">Medical Information</h3>
            {patient.allergies?.length > 0 ? (
              <div className="mb-3">
                <p className="text-sm text-gray-600">Allergies</p>
                <div className="flex flex-wrap gap-2 mt-1">
                  {patient.allergies.map((allergy, i) => (
                    <span key={i} className="px-2 py-1 bg-red-100 text-red-800 rounded text-sm">
                      {allergy}
                    </span>
                  ))}
                </div>
              </div>
            ) : (
              <p className="text-sm text-gray-500 mb-3">No allergies recorded</p>
            )}
            {patient.chronic_conditions?.length > 0 ? (
              <div>
                <p className="text-sm text-gray-600">Chronic Conditions</p>
                <div className="flex flex-wrap gap-2 mt-1">
                  {patient.chronic_conditions.map((condition, i) => (
                    <span key={i} className="px-2 py-1 bg-yellow-100 text-yellow-800 rounded text-sm">
                      {condition}
                    </span>
                  ))}
                </div>
              </div>
            ) : (
              <p className="text-sm text-gray-500">No chronic conditions recorded</p>
            )}
          </div>
        </div>

        {/* Medical Summary */}
        {patient.medical_summary && (
          <div className="p-4 bg-blue-50 rounded-lg">
            <h3 className="font-medium text-gray-900 mb-2">Medical Summary</h3>
            <p className="text-sm text-gray-700">{patient.medical_summary}</p>
          </div>
        )}

        {/* Emergency Contact */}
        {patient.emergency_contact_name && (
          <div>
            <h3 className="font-medium text-gray-900 mb-4">Emergency Contact</h3>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-sm text-gray-600">Name</p>
                <p className="font-medium">{patient.emergency_contact_name}</p>
              </div>
              {patient.emergency_contact_phone && (
                <div>
                  <p className="text-sm text-gray-600">Phone</p>
                  <p className="font-medium">{patient.emergency_contact_phone}</p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Prescriptions */}
        <div>
          <h3 className="font-medium text-gray-900 mb-4">
            Prescriptions ({patient.prescriptions?.length || 0})
          </h3>
          {patient.prescriptions?.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {patient.prescriptions.map((prescription, index) => (
                <div
                  key={index}
                  className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition"
                >
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex-1">
                      <p className="font-medium text-gray-900 text-sm">
                        {prescription.filename || 'Prescription'}
                      </p>
                      <p className="text-xs text-gray-500 mt-1">
                        {new Date(prescription.uploaded_at).toLocaleDateString('en-US', {
                          year: 'numeric',
                          month: 'short',
                          day: 'numeric',
                        })}
                      </p>
                    </div>
                    <a
                      href={prescription.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="ml-2 p-2 text-blue-600 hover:bg-blue-50 rounded transition"
                    >
                      <Download className="h-5 w-5" />
                    </a>
                  </div>
                  
                  {prescription.content_type?.includes('image') && (
                    <div className="mt-3">
                      <img
                        src={prescription.url}
                        alt="Prescription"
                        className="w-full h-32 object-cover rounded"
                      />
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8 text-gray-500">
              <FileText className="mx-auto h-12 w-12 text-gray-400" />
              <p className="text-sm mt-2">No prescriptions uploaded yet</p>
            </div>
          )}
        </div>

        {/* Vaccinations */}
        {patient.vaccinations?.length > 0 && (
          <div>
            <h3 className="font-medium text-gray-900 mb-4">
              Vaccinations ({patient.vaccinations.length})
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {patient.vaccinations.map((vacc, index) => (
                <div key={index} className="border border-gray-200 rounded-lg p-3">
                  <p className="font-medium text-gray-900">{vacc.vaccine_name}</p>
                  <p className="text-sm text-gray-600">
                    Date: {new Date(vacc.administered_date).toLocaleDateString()}
                  </p>
                  {vacc.dose_number && (
                    <p className="text-sm text-gray-600">Dose: {vacc.dose_number}</p>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Action Buttons */}
        <div className="flex gap-3 pt-4 border-t">
          <button className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition flex items-center justify-center gap-2">
            <MessageSquare className="h-4 w-4" />
            Send Message
          </button>
          <button className="flex-1 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition flex items-center justify-center gap-2">
            <Calendar className="h-4 w-4" />
            Schedule Appointment
          </button>
        </div>
      </div>
    </div>
  );
}

export default DoctorDashboard;