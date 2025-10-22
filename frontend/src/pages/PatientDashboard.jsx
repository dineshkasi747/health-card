import React, { useState, useEffect } from 'react';

const API_URL = 'http://localhost:8000';

// ============================================================================
// OVERVIEW PAGE
// ============================================================================
const OverviewPage = ({ patientData, authService }) => {
  const [healthScore, setHealthScore] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    async function loadPatient() {
      try {
        const res = await authService.get('/patients/me');
        const json = await res.json();
        if (json.status === 'success' && mounted) {
          setPatientData(json.data);
        }
      } catch (err) {
        console.error('Failed to load patient', err);
      }
    }
    loadPatient();
    return () => { mounted = false; };
  }, []);


  useEffect(() => {
    fetchHealthScore();
  }, []);

  const fetchHealthScore = async () => {
    try {
      const response = await authService.get('/analytics/health-score');
      const result = await response.json();
      if (result.status === 'success') {
        setHealthScore(result.data);
      }
    } catch (error) {
      console.error('Error fetching health score:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="animate-pulse">Loading...</div>;
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <StatCard
          title="Health Score"
          value={healthScore?.health_score || 85}
          icon="❤️"
          color="blue"
        />
        <StatCard
          title="Medication Adherence"
          value={`${healthScore?.medication_adherence || 90}%`}
          icon="💊"
          color="green"
        />
        <StatCard
          title="Upcoming Appointments"
          value={healthScore?.upcoming_appointments || 2}
          icon="📅"
          color="purple"
        />
      </div>

      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold mb-4">Health Recommendations</h3>
        <div className="space-y-2">
          {(healthScore?.recommendations || ['Keep tracking your vitals regularly']).map((rec, i) => (
            <div key={i} className="flex items-start p-3 bg-blue-50 rounded-lg">
              <span className="text-blue-600 mr-3">💡</span>
              <p className="text-sm text-gray-700">{rec}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

// ============================================================================
// PROFILE PAGE
// ============================================================================
const ProfilePage = ({ patientData, authService, onUpdate }) => {
  const [formData, setFormData] = useState({
    blood_group: '',
    allergies: [],
    chronic_conditions: [],
    emergency_contact_name: '',
    emergency_contact_phone: ''
  });
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (patientData) {
      setFormData({
        blood_group: patientData.blood_group || '',
        allergies: patientData.allergies || [],
        chronic_conditions: patientData.chronic_conditions || [],
        emergency_contact_name: patientData.emergency_contact_name || '',
        emergency_contact_phone: patientData.emergency_contact_phone || ''
      });
    }
  }, [patientData]);

  const handleSave = async () => {
    setSaving(true);
    try {
      const response = await authService.post('/patients/me', formData);
      const result = await response.json();
      if (result.status === 'success') {
        onUpdate();
        setEditing(false);
      }
    } catch (error) {
      console.error('Error updating profile:', error);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex justify-between items-center mb-6">
          <h3 className="text-lg font-semibold">Medical Information</h3>
          <button
            onClick={() => editing ? handleSave() : setEditing(true)}
            disabled={saving}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            {saving ? 'Saving...' : editing ? 'Save Changes' : 'Edit Profile'}
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Blood Group</label>
            <input
              type="text"
              value={formData.blood_group}
              onChange={(e) => setFormData({...formData, blood_group: e.target.value})}
              disabled={!editing}
              className="w-full px-3 py-2 border rounded-lg"
              placeholder="A+"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Emergency Contact Name</label>
            <input
              type="text"
              value={formData.emergency_contact_name}
              onChange={(e) => setFormData({...formData, emergency_contact_name: e.target.value})}
              disabled={!editing}
              className="w-full px-3 py-2 border rounded-lg"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Emergency Contact Phone</label>
            <input
              type="tel"
              value={formData.emergency_contact_phone}
              onChange={(e) => setFormData({...formData, emergency_contact_phone: e.target.value})}
              disabled={!editing}
              className="w-full px-3 py-2 border rounded-lg"
            />
          </div>
        </div>
      </div>
    </div>
  );
};

// ============================================================================
// QR CODE PAGE
// ============================================================================
const QRCodePage = ({ patientData }) => (
  <div className="max-w-2xl mx-auto">
    <div className="bg-white rounded-lg shadow p-8 text-center">
      <h3 className="text-2xl font-bold mb-4">Emergency QR Code</h3>
      <p className="text-gray-600 mb-6">Show this QR code to healthcare providers in emergencies</p>
      
      {patientData?.qr_image_url ? (
        <div className="flex flex-col items-center">
          <img 
            src={patientData.qr_image_url} 
            alt="Emergency QR Code" 
            className="w-64 h-64 border-4 border-blue-500 rounded-lg shadow-lg"
          />
          <button className="mt-6 px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
            Download QR Code
          </button>
        </div>
      ) : (
        <div className="w-64 h-64 mx-auto bg-gray-200 rounded-lg flex items-center justify-center">
          <span className="text-gray-500">Loading QR Code...</span>
        </div>
      )}
    </div>
  </div>
);

// ============================================================================
// PRESCRIPTIONS PAGE
// ============================================================================
const PrescriptionsPage = ({ authService }) => {
  const [prescriptions, setPrescriptions] = useState([]);
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    fetchPrescriptions();
  }, []);

  const fetchPrescriptions = async () => {
    try {
      const response = await authService.get('/patients/me');
      const result = await response.json();
      if (result.status === 'success') {
        setPrescriptions(result.data.prescriptions || []);
      }
    } catch (error) {
      console.error('Error fetching prescriptions:', error);
    }
  };

  const handleUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setUploading(true);
    try {
      const response = await authService.uploadFile('/patients/me/prescriptions', file);
      const result = await response.json();
      if (result.status === 'success') {
        fetchPrescriptions();
      }
    } catch (error) {
      console.error('Error uploading:', error);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold mb-4">Upload Prescription</h3>
        <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center">
          <input
            type="file"
            onChange={handleUpload}
            accept=".pdf,.jpg,.jpeg,.png"
            className="hidden"
            id="prescription-upload"
            disabled={uploading}
          />
          <label htmlFor="prescription-upload" className="cursor-pointer">
            <div className="text-gray-600">
              <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
              </svg>
              <p className="mt-2">{uploading ? 'Uploading...' : 'Click to upload prescription'}</p>
              <p className="text-sm text-gray-500 mt-1">PDF, JPG, PNG up to 10MB</p>
            </div>
          </label>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold mb-4">My Prescriptions</h3>
        <div className="space-y-3">
          {prescriptions.length > 0 ? prescriptions.map((rx, i) => (
            <div key={i} className="flex items-center justify-between p-4 bg-gray-50 rounded-lg hover:bg-gray-100">
              <div className="flex items-center">
                <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center mr-3">
                  📄
                </div>
                <div>
                  <p className="font-medium">{rx.filename}</p>
                  <p className="text-sm text-gray-500">{new Date(rx.uploaded_at).toLocaleDateString()}</p>
                </div>
              </div>
              <a href={rx.url} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:text-blue-700">
                View
              </a>
            </div>
          )) : (
            <p className="text-center text-gray-500 py-8">No prescriptions uploaded yet</p>
          )}
        </div>
      </div>
    </div>
  );
};

// ============================================================================
// MEDICATIONS PAGE
// ============================================================================
const MedicationsPage = ({ authService }) => {
  const [medications, setMedications] = useState([]);
  const [showAddForm, setShowAddForm] = useState(false);

  useEffect(() => {
    fetchMedications();
  }, []);

  const fetchMedications = async () => {
    try {
      const response = await authService.get('/medications');
      const result = await response.json();
      if (result.status === 'success') {
        setMedications(result.data);
      }
    } catch (error) {
      console.error('Error:', error);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h3 className="text-lg font-semibold">Active Medications</h3>
        <button
          onClick={() => setShowAddForm(true)}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
        >
          + Add Medication
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {medications.map((med, i) => (
          <div key={i} className="bg-white rounded-lg shadow p-6">
            <div className="flex justify-between items-start mb-4">
              <div>
                <h4 className="font-semibold text-lg">{med.name}</h4>
                <p className="text-gray-600">{med.dosage}</p>
              </div>
              <span className="px-3 py-1 bg-green-100 text-green-800 rounded-full text-sm">
                Active
              </span>
            </div>
            <div className="space-y-2 text-sm">
              <p><span className="font-medium">Frequency:</span> {med.frequency}</p>
              <p><span className="font-medium">Times:</span> {med.times?.join(', ') || 'Not set'}</p>
              {med.instructions && <p><span className="font-medium">Instructions:</span> {med.instructions}</p>}
            </div>
          </div>
        ))}
      </div>

      {medications.length === 0 && (
        <div className="bg-white rounded-lg shadow p-12 text-center">
          <p className="text-gray-500">No medications added yet</p>
        </div>
      )}
    </div>
  );
};

// ============================================================================
// APPOINTMENTS PAGE
// ============================================================================
const AppointmentsPage = ({ authService }) => {
  const [appointments, setAppointments] = useState([]);

  useEffect(() => {
    fetchAppointments();
  }, []);

  const fetchAppointments = async () => {
    try {
      const response = await authService.get('/appointments');
      const result = await response.json();
      if (result.status === 'success') {
        setAppointments(result.data);
      }
    } catch (error) {
      console.error('Error:', error);
    }
  };

  return (
    <div className="space-y-6">
      <button className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
        Book New Appointment
      </button>

      <div className="space-y-4">
        {appointments.map((apt, i) => (
          <div key={i} className="bg-white rounded-lg shadow p-6">
            <div className="flex justify-between items-start">
              <div>
                <h4 className="font-semibold text-lg">{apt.doctor_name || 'Dr. Smith'}</h4>
                <p className="text-gray-600">{apt.reason || 'Regular Checkup'}</p>
                <p className="text-sm text-gray-500 mt-2">
                  📅 {new Date(apt.scheduled_date).toLocaleDateString()} at {apt.scheduled_time}
                </p>
              </div>
              <span className={`px-3 py-1 rounded-full text-sm ${
                apt.status === 'scheduled' ? 'bg-blue-100 text-blue-800' : 'bg-gray-100 text-gray-800'
              }`}>
                {apt.status}
              </span>
            </div>
          </div>
        ))}
      </div>

      {appointments.length === 0 && (
        <div className="bg-white rounded-lg shadow p-12 text-center">
          <p className="text-gray-500">No upcoming appointments</p>
        </div>
      )}
    </div>
  );
};

// ============================================================================
// VITALS PAGE  
// ============================================================================
const VitalsPage = ({ authService }) => {
  const [vitals, setVitals] = useState([]);
  const [showAddForm, setShowAddForm] = useState(false);

  useEffect(() => {
    fetchVitals();
  }, []);

  const fetchVitals = async () => {
    try {
      const response = await authService.get('/vitals?limit=10');
      const result = await response.json();
      if (result.status === 'success') {
        setVitals(result.data);
      }
    } catch (error) {
      console.error('Error:', error);
    }
  };

  return (
    <div className="space-y-6">
      <button
        onClick={() => setShowAddForm(true)}
        className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
      >
        + Add Vital Record
      </button>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {['heart_rate', 'blood_pressure', 'temperature', 'oxygen_saturation', 'weight'].map((type) => (
          <div key={type} className="bg-white rounded-lg shadow p-6">
            <h4 className="font-semibold mb-2 capitalize">{type.replace('_', ' ')}</h4>
            <p className="text-3xl font-bold text-blue-600">--</p>
            <p className="text-sm text-gray-500 mt-2">No recent data</p>
          </div>
        ))}
      </div>

      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold mb-4">Recent Vitals</h3>
        <div className="space-y-3">
          {vitals.map((vital, i) => (
            <div key={i} className="flex justify-between items-center p-3 bg-gray-50 rounded-lg">
              <div>
                <p className="font-medium capitalize">{vital.vital_type?.replace('_', ' ')}</p>
                <p className="text-sm text-gray-500">{new Date(vital.recorded_at).toLocaleString()}</p>
              </div>
              <p className="text-lg font-semibold">{vital.value} {vital.unit}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

// ============================================================================
// STAT CARD COMPONENT
// ============================================================================
const StatCard = ({ title, value, icon, color }) => (
  <div className="bg-white rounded-lg shadow p-6">
    <div className="flex items-center justify-between mb-4">
      <span className="text-2xl">{icon}</span>
      <div className={`w-12 h-12 bg-${color}-100 rounded-full flex items-center justify-center`}>
        <div className={`w-6 h-6 bg-${color}-500 rounded-full`}></div>
      </div>
    </div>
    <h3 className="text-gray-600 text-sm mb-1">{title}</h3>
    <p className="text-3xl font-bold">{value}</p>
  </div>
);

// ============================================================================
// MAIN DASHBOARD WRAPPER
// ============================================================================
const PatientDashboard = ({ user = {name: 'John Doe', email: 'john@example.com'}, onLogout = () => {} }) => {
  const [currentView, setCurrentView] = useState('overview');
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [patientData, setPatientData] = useState(null);

  const menuItems = [
    { id: 'overview', name: 'Dashboard', icon: '🏠' },
    { id: 'profile', name: 'My Profile', icon: '👤' },
    { id: 'qr-code', name: 'Emergency QR', icon: '📱' },
    { id: 'prescriptions', name: 'Prescriptions', icon: '📄' },
    { id: 'medications', name: 'Medications', icon: '💊' },
    { id: 'appointments', name: 'Appointments', icon: '📅' },
    { id: 'vitals', name: 'Track Vitals', icon: '❤️' }
  ];

  const renderView = () => {
    const props = { patientData, authService, onUpdate: () => {} };
    switch (currentView) {
      case 'overview': return <OverviewPage {...props} />;
      case 'profile': return <ProfilePage {...props} />;
      case 'qr-code': return <QRCodePage {...props} />;
      case 'prescriptions': return <PrescriptionsPage {...props} />;
      case 'medications': return <MedicationsPage {...props} />;
      case 'appointments': return <AppointmentsPage {...props} />;
      case 'vitals': return <VitalsPage {...props} />;
      default: return <OverviewPage {...props} />;
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 flex">
      <div className={`${sidebarOpen ? 'w-64' : 'w-20'} bg-white border-r transition-all duration-300`}>
        <div className="p-4 border-b flex items-center justify-between">
          {sidebarOpen && <span className="text-lg font-semibold">Health Card</span>}
          <button onClick={() => setSidebarOpen(!sidebarOpen)} className="p-1 rounded hover:bg-gray-100">
            {sidebarOpen ? '◀' : '▶'}
          </button>
        </div>

        <nav className="p-4 space-y-1">
          {menuItems.map(item => (
            <button
              key={item.id}
              onClick={() => setCurrentView(item.id)}
              className={`w-full flex items-center ${sidebarOpen ? 'px-4' : 'justify-center'} py-3 rounded-lg ${
                currentView === item.id ? 'bg-blue-50 text-blue-600' : 'hover:bg-gray-50'
              }`}
            >
              <span className="text-xl">{item.icon}</span>
              {sidebarOpen && <span className="ml-3">{item.name}</span>}
            </button>
          ))}
        </nav>

        <div className="absolute bottom-0 left-0 right-0 p-4 border-t">
          {sidebarOpen ? (
            <div className="flex items-center justify-between">
              <div className="flex items-center">
                <div className="w-10 h-10 bg-blue-600 rounded-full flex items-center justify-center text-white">
                  {user.name.charAt(0)}
                </div>
                <div className="ml-3">
                  <p className="text-sm font-medium">{user.name}</p>
                  <p className="text-xs text-gray-500">{user.email}</p>
                </div>
              </div>
              <button onClick={onLogout} className="p-2 hover:bg-red-50 rounded-lg text-red-600">
                🚪
              </button>
            </div>
          ) : (
            <button onClick={onLogout} className="w-full p-2 hover:bg-red-50 rounded-lg text-red-600">
              🚪
            </button>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        <div className="bg-white border-b px-8 py-4">
          <h1 className="text-2xl font-bold">{menuItems.find(i => i.id === currentView)?.name}</h1>
          <p className="text-sm text-gray-500 mt-1">Welcome back, {user.name.split(' ')[0]}!</p>
        </div>

        <div className="p-8">
          {renderView()}
        </div>
      </div>
    </div>
  );
};

export default PatientDashboard;