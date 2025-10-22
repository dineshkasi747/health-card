// DoctorDashboard.jsx - Fixed version with proper token handling
import React, { useState, useEffect } from 'react';

function DoctorDashboard({ user, onLogout, apiUrl, authService }) {
  const [patients, setPatients] = useState([]);
  const [selectedPatient, setSelectedPatient] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState('patients'); // 'patients' or 'scan'

  useEffect(() => {
    loadPatients();
  }, []);

  const loadPatients = async () => {
    setLoading(true);
    setError('');
    
    try {
      console.log('📋 Loading doctor patients...');
      
      // Use authenticatedFetch from AuthService
      const response = await authService.authenticatedFetch(
        `${apiUrl}/doctors/me/patients`,
        { method: 'GET' }
      );

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Failed to load patients');
      }

      const data = await response.json();
      console.log('✅ Patients loaded:', data.data.length);
      setPatients(data.data || []);
    } catch (err) {
      console.error('❌ Error loading patients:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const viewPatientDetails = async (patientId) => {
    try {
      console.log('👤 Loading patient details:', patientId);
      
      const response = await authService.authenticatedFetch(
        `${apiUrl}/patients/${patientId}`,
        { method: 'GET' }
      );

      if (!response.ok) {
        throw new Error('Failed to load patient details');
      }

      const data = await response.json();
      console.log('✅ Patient details loaded');
      setSelectedPatient(data.data);
    } catch (err) {
      console.error('❌ Error loading patient details:', err);
      setError(err.message);
    }
  };

  const handleScanQR = async (qrToken) => {
    try {
      console.log('🔍 Scanning QR code:', qrToken);
      
      const response = await authService.authenticatedFetch(
        `${apiUrl}/qr/resolve/${qrToken}`,
        { method: 'GET' }
      );

      if (!response.ok) {
        throw new Error('Invalid QR code');
      }

      const data = await response.json();
      console.log('✅ QR code resolved');
      setSelectedPatient(data.data);
      setActiveTab('patients');
    } catch (err) {
      console.error('❌ Error scanning QR:', err);
      setError(err.message);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">Doctor Dashboard</h1>
              <p className="text-sm text-gray-600">Welcome, Dr. {user.name}</p>
            </div>
            <button
              onClick={onLogout}
              className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition"
            >
              Logout
            </button>
          </div>
        </div>
      </header>

      {/* Tabs */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mt-6">
        <div className="border-b border-gray-200">
          <nav className="-mb-px flex space-x-8">
            <button
              onClick={() => setActiveTab('patients')}
              className={`${
                activeTab === 'patients'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm transition`}
            >
              My Patients
            </button>
            <button
              onClick={() => setActiveTab('scan')}
              className={`${
                activeTab === 'scan'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm transition`}
            >
              Scan QR Code
            </button>
          </nav>
        </div>
      </div>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {error && (
          <div className="mb-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
            <p className="text-sm">{error}</p>
            <button
              onClick={() => setError('')}
              className="text-xs underline mt-1"
            >
              Dismiss
            </button>
          </div>
        )}

        {activeTab === 'patients' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Patients List */}
            <div className="lg:col-span-1 bg-white rounded-lg shadow p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">
                Patient List ({patients.length})
              </h2>

              {loading ? (
                <div className="text-center py-8">
                  <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                  <p className="text-sm text-gray-600 mt-2">Loading patients...</p>
                </div>
              ) : patients.length === 0 ? (
                <div className="text-center py-8">
                  <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                  </svg>
                  <p className="mt-2 text-sm text-gray-600">No patients yet</p>
                  <p className="text-xs text-gray-500 mt-1">Scan a patient's QR code to get started</p>
                </div>
              ) : (
                <div className="space-y-2 max-h-96 overflow-y-auto">
                  {patients.map((patient) => (
                    <button
                      key={patient.id}
                      onClick={() => viewPatientDetails(patient.id)}
                      className={`w-full text-left p-3 rounded-lg border transition ${
                        selectedPatient?.id === patient.id
                          ? 'bg-blue-50 border-blue-200'
                          : 'bg-white border-gray-200 hover:bg-gray-50'
                      }`}
                    >
                      <p className="font-medium text-gray-900">{patient.user?.name || 'Unknown'}</p>
                      <p className="text-xs text-gray-500">{patient.user?.email}</p>
                      <p className="text-xs text-gray-400 mt-1">
                        {patient.prescriptions?.length || 0} prescriptions
                      </p>
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Patient Details */}
            <div className="lg:col-span-2 bg-white rounded-lg shadow p-6">
              {selectedPatient ? (
                <div>
                  <div className="flex justify-between items-start mb-6">
                    <div>
                      <h2 className="text-xl font-semibold text-gray-900">
                        {selectedPatient.user?.name}
                      </h2>
                      <p className="text-sm text-gray-600">{selectedPatient.user?.email}</p>
                      {selectedPatient.user?.phone && (
                        <p className="text-sm text-gray-600">{selectedPatient.user?.phone}</p>
                      )}
                    </div>
                    <button
                      onClick={() => setSelectedPatient(null)}
                      className="text-gray-400 hover:text-gray-600"
                    >
                      <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>

                  {/* Medical Summary */}
                  {selectedPatient.medical_summary && (
                    <div className="mb-6 p-4 bg-blue-50 rounded-lg">
                      <h3 className="font-medium text-gray-900 mb-2">Medical Summary</h3>
                      <p className="text-sm text-gray-700">{selectedPatient.medical_summary}</p>
                    </div>
                  )}

                  {/* Prescriptions */}
                  <div>
                    <h3 className="font-medium text-gray-900 mb-4">
                      Prescriptions ({selectedPatient.prescriptions?.length || 0})
                    </h3>

                    {selectedPatient.prescriptions?.length > 0 ? (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {selectedPatient.prescriptions.map((prescription, index) => (
                          <div
                            key={index}
                            className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition"
                          >
                            <div className="flex items-start justify-between">
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
                                <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                                </svg>
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
                        <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                        </svg>
                        <p className="text-sm mt-2">No prescriptions uploaded yet</p>
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                <div className="text-center py-12 text-gray-500">
                  <svg className="mx-auto h-16 w-16 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                  </svg>
                  <p className="mt-4 text-lg">Select a patient to view details</p>
                  <p className="text-sm text-gray-400 mt-1">Click on a patient from the list</p>
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === 'scan' && (
          <QRScanner onScan={handleScanQR} />
        )}
      </main>
    </div>
  );
}

// QR Scanner Component
function QRScanner({ onScan }) {
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
            <svg className="h-10 w-10 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v1m6 11h2m-6 0h-2v4m0-11v3m0 0h.01M12 12h4.01M16 20h4M4 12h4m12 0h.01M5 8h2a1 1 0 001-1V5a1 1 0 00-1-1H5a1 1 0 00-1 1v2a1 1 0 001 1zm12 0h2a1 1 0 001-1V5a1 1 0 00-1-1h-2a1 1 0 00-1 1v2a1 1 0 001 1zM5 20h2a1 1 0 001-1v-2a1 1 0 00-1-1H5a1 1 0 00-1 1v2a1 1 0 001 1z" />
            </svg>
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
            <p className="text-xs text-gray-500 mt-1">
              The QR token is typically a UUID format (e.g., 123e4567-e89b-12d3-a456-426614174000)
            </p>
          </div>

          <button
            onClick={handleSubmit}
            disabled={!qrToken.trim() || scanning}
            className="w-full py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition flex items-center justify-center"
          >
            {scanning ? (
              <>
                <svg className="animate-spin -ml-1 mr-2 h-5 w-5" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Scanning...
              </>
            ) : (
              <>
                <svg className="mr-2 h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
                Scan QR Code
              </>
            )}
          </button>
        </div>

        <div className="mt-6 p-4 bg-gray-50 rounded-lg">
          <h3 className="text-sm font-medium text-gray-900 mb-2">How to scan:</h3>
          <ol className="text-xs text-gray-600 space-y-1 list-decimal list-inside">
            <li>Ask the patient to show their QR code</li>
            <li>Use a QR scanner app to read the code</li>
            <li>Copy the token from the QR code</li>
            <li>Paste it in the field above</li>
          </ol>
        </div>
      </div>
    </div>
  );
}

export default DoctorDashboard