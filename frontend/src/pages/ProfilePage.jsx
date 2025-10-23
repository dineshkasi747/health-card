import React, { useState, useEffect } from 'react';

// ============================================================================
// PROFILE PAGE - Patient Information Management
// ============================================================================
const ProfilePage = ({ authService }) => {
  const [patientData, setPatientData] = useState(null);
  const [formData, setFormData] = useState({
    blood_group: '',
    allergies: [],
    chronic_conditions: [],
    emergency_contact_name: '',
    emergency_contact_phone: '',
    date_of_birth: '',
    gender: '',
    address: ''
  });
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [successMessage, setSuccessMessage] = useState('');

  // New item inputs for arrays
  const [newAllergy, setNewAllergy] = useState('');
  const [newCondition, setNewCondition] = useState('');

  useEffect(() => {
    fetchPatientData();
  }, []);

  const fetchPatientData = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await authService.get('/patients/me');
      const result = await response.json();
      
      if (result.status === 'success') {
        setPatientData(result.data);
        setFormData({
          blood_group: result.data.blood_group || '',
          allergies: result.data.allergies || [],
          chronic_conditions: result.data.chronic_conditions || [],
          emergency_contact_name: result.data.emergency_contact_name || '',
          emergency_contact_phone: result.data.emergency_contact_phone || '',
          date_of_birth: result.data.date_of_birth || '',
          gender: result.data.gender || '',
          address: result.data.address || ''
        });
      } else {
        setError(result.message || 'Failed to load profile');
      }
    } catch (err) {
      console.error('Error fetching patient data:', err);
      setError('Unable to connect to server');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setSuccessMessage('');
    
    try {
      const response = await authService.patch('/patients/me', formData);
      const result = await response.json();
      
      if (result.status === 'success') {
        setPatientData(result.data);
        setEditing(false);
        setSuccessMessage('Profile updated successfully!');
        setTimeout(() => setSuccessMessage(''), 3000);
      } else {
        setError(result.message || 'Failed to update profile');
      }
    } catch (err) {
      console.error('Error updating profile:', err);
      setError('Unable to save changes');
    } finally {
      setSaving(false);
    }
  };

  const handleCancel = () => {
    // Reset form to original data
    if (patientData) {
      setFormData({
        blood_group: patientData.blood_group || '',
        allergies: patientData.allergies || [],
        chronic_conditions: patientData.chronic_conditions || [],
        emergency_contact_name: patientData.emergency_contact_name || '',
        emergency_contact_phone: patientData.emergency_contact_phone || '',
        date_of_birth: patientData.date_of_birth || '',
        gender: patientData.gender || '',
        address: patientData.address || ''
      });
    }
    setEditing(false);
    setError(null);
  };

  const addAllergy = () => {
    if (newAllergy.trim()) {
      setFormData({
        ...formData,
        allergies: [...formData.allergies, newAllergy.trim()]
      });
      setNewAllergy('');
    }
  };

  const removeAllergy = (index) => {
    setFormData({
      ...formData,
      allergies: formData.allergies.filter((_, i) => i !== index)
    });
  };

  const addCondition = () => {
    if (newCondition.trim()) {
      setFormData({
        ...formData,
        chronic_conditions: [...formData.chronic_conditions, newCondition.trim()]
      });
      setNewCondition('');
    }
  };

  const removeCondition = (index) => {
    setFormData({
      ...formData,
      chronic_conditions: formData.chronic_conditions.filter((_, i) => i !== index)
    });
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Success Message */}
      {successMessage && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4 flex items-center">
          <span className="text-green-600 mr-2">✅</span>
          <p className="text-green-800">{successMessage}</p>
        </div>
      )}

      {/* Error Message */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-center">
          <span className="text-red-600 mr-2">❌</span>
          <p className="text-red-800">{error}</p>
        </div>
      )}

      {/* Medical Information Card */}
      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex justify-between items-center mb-6">
          <h3 className="text-lg font-semibold">Medical Information</h3>
          <div className="flex gap-2">
            {editing ? (
              <>
                <button
                  onClick={handleCancel}
                  disabled={saving}
                  className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
                >
                  {saving ? 'Saving...' : 'Save Changes'}
                </button>
              </>
            ) : (
              <button
                onClick={() => setEditing(true)}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
              >
                ✏️ Edit Profile
              </button>
            )}
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Blood Group */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Blood Group
            </label>
            <input
              type="text"
              value={formData.blood_group}
              onChange={(e) => setFormData({...formData, blood_group: e.target.value})}
              disabled={!editing}
              className="w-full px-3 py-2 border rounded-lg disabled:bg-gray-50 disabled:text-gray-600"
              placeholder="e.g., A+, O-, B+"
            />
          </div>

          {/* Date of Birth */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Date of Birth
            </label>
            <input
              type="date"
              value={formData.date_of_birth}
              onChange={(e) => setFormData({...formData, date_of_birth: e.target.value})}
              disabled={!editing}
              className="w-full px-3 py-2 border rounded-lg disabled:bg-gray-50 disabled:text-gray-600"
            />
          </div>

          {/* Gender */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Gender
            </label>
            <select
              value={formData.gender}
              onChange={(e) => setFormData({...formData, gender: e.target.value})}
              disabled={!editing}
              className="w-full px-3 py-2 border rounded-lg disabled:bg-gray-50 disabled:text-gray-600"
            >
              <option value="">Select Gender</option>
              <option value="male">Male</option>
              <option value="female">Female</option>
              <option value="other">Other</option>
            </select>
          </div>

          {/* Emergency Contact Name */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Emergency Contact Name
            </label>
            <input
              type="text"
              value={formData.emergency_contact_name}
              onChange={(e) => setFormData({...formData, emergency_contact_name: e.target.value})}
              disabled={!editing}
              className="w-full px-3 py-2 border rounded-lg disabled:bg-gray-50 disabled:text-gray-600"
              placeholder="Full name"
            />
          </div>

          {/* Emergency Contact Phone */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Emergency Contact Phone
            </label>
            <input
              type="tel"
              value={formData.emergency_contact_phone}
              onChange={(e) => setFormData({...formData, emergency_contact_phone: e.target.value})}
              disabled={!editing}
              className="w-full px-3 py-2 border rounded-lg disabled:bg-gray-50 disabled:text-gray-600"
              placeholder="+1234567890"
            />
          </div>

          {/* Address */}
          <div className="md:col-span-2">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Address
            </label>
            <textarea
              value={formData.address}
              onChange={(e) => setFormData({...formData, address: e.target.value})}
              disabled={!editing}
              rows={3}
              className="w-full px-3 py-2 border rounded-lg disabled:bg-gray-50 disabled:text-gray-600"
              placeholder="Full address"
            />
          </div>
        </div>
      </div>

      {/* Allergies Section */}
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold mb-4">Allergies</h3>
        
        {editing && (
          <div className="flex gap-2 mb-4">
            <input
              type="text"
              value={newAllergy}
              onChange={(e) => setNewAllergy(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && addAllergy()}
              placeholder="Add new allergy"
              className="flex-1 px-3 py-2 border rounded-lg"
            />
            <button
              onClick={addAllergy}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              + Add
            </button>
          </div>
        )}

        <div className="space-y-2">
          {formData.allergies.length > 0 ? (
            formData.allergies.map((allergy, index) => (
              <div key={index} className="flex items-center justify-between p-3 bg-red-50 rounded-lg">
                <span className="text-gray-800">⚠️ {allergy}</span>
                {editing && (
                  <button
                    onClick={() => removeAllergy(index)}
                    className="text-red-600 hover:text-red-800"
                  >
                    ✕
                  </button>
                )}
              </div>
            ))
          ) : (
            <p className="text-gray-500 text-center py-4">No allergies recorded</p>
          )}
        </div>
      </div>

      {/* Chronic Conditions Section */}
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold mb-4">Chronic Conditions</h3>
        
        {editing && (
          <div className="flex gap-2 mb-4">
            <input
              type="text"
              value={newCondition}
              onChange={(e) => setNewCondition(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && addCondition()}
              placeholder="Add new condition"
              className="flex-1 px-3 py-2 border rounded-lg"
            />
            <button
              onClick={addCondition}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              + Add
            </button>
          </div>
        )}

        <div className="space-y-2">
          {formData.chronic_conditions.length > 0 ? (
            formData.chronic_conditions.map((condition, index) => (
              <div key={index} className="flex items-center justify-between p-3 bg-yellow-50 rounded-lg">
                <span className="text-gray-800">🩺 {condition}</span>
                {editing && (
                  <button
                    onClick={() => removeCondition(index)}
                    className="text-red-600 hover:text-red-800"
                  >
                    ✕
                  </button>
                )}
              </div>
            ))
          ) : (
            <p className="text-gray-500 text-center py-4">No chronic conditions recorded</p>
          )}
        </div>
      </div>

      {/* Assigned Doctor Info */}
      {patientData?.assigned_doctor && (
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold mb-4">Assigned Doctor</h3>
          <div className="flex items-center p-4 bg-blue-50 rounded-lg">
            <div className="w-12 h-12 bg-blue-600 rounded-full flex items-center justify-center text-white text-xl mr-4">
              👨‍⚕️
            </div>
            <div>
              <p className="font-semibold text-gray-900">{patientData.assigned_doctor.name}</p>
              <p className="text-sm text-gray-600">{patientData.assigned_doctor.specialization}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

// ============================================================================
// DEMO WRAPPER
// ============================================================================
export default function ProfilePageDemo() {
  const mockAuthService = {
    get: async (endpoint) => {
      await new Promise(resolve => setTimeout(resolve, 800));
      return {
        json: async () => ({
          status: 'success',
          data: {
            id: '123',
            blood_group: 'A+',
            allergies: ['Penicillin', 'Peanuts'],
            chronic_conditions: ['Hypertension', 'Type 2 Diabetes'],
            emergency_contact_name: 'Jane Doe',
            emergency_contact_phone: '+1234567890',
            date_of_birth: '1990-05-15',
            gender: 'male',
            address: '123 Main Street, City, State 12345',
            assigned_doctor: {
              id: 'doc1',
              name: 'Dr. Sarah Smith',
              specialization: 'General Physician'
            }
          }
        })
      };
    },
    patch: async (endpoint, data) => {
      await new Promise(resolve => setTimeout(resolve, 1000));
      return {
        json: async () => ({
          status: 'success',
          data: data
        })
      };
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-4xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">My Profile</h1>
          <p className="text-gray-600 mt-2">Manage your medical information and emergency contacts</p>
        </div>
        <ProfilePage authService={mockAuthService} />
      </div>
    </div>
  );
}