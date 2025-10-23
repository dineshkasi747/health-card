import React, { useState, useEffect } from 'react';
import { authService } from '../App';

const MedicationsPage = () => {
  const [medications, setMedications] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAddForm, setShowAddForm] = useState(false);
  const [adherenceData, setAdherenceData] = useState(null);
  const [loadingAdherence, setLoadingAdherence] = useState(false);

  // Form state for adding medication
  const [formData, setFormData] = useState({
    name: '',
    dosage: '',
    frequency: 'daily',
    custom_frequency: '',
    start_date: new Date().toISOString().split('T')[0],
    end_date: '',
    times: [],
    instructions: '',
    reminders_enabled: true
  });

  const [timeInput, setTimeInput] = useState('09:00');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Fetch medications on component mount
  useEffect(() => {
    fetchMedications();
    fetchAdherence();
  }, []);

  const fetchMedications = async () => {
    try {
      setLoading(true);
      const response = await authService.get('/medications?active_only=true');
      const result = await response.json();

      if (result.status === 'success') {
        setMedications(result.data);
      } else {
        setError('Failed to load medications');
      }
    } catch (err) {
      console.error('Error fetching medications:', err);
      setError('Network error loading medications');
    } finally {
      setLoading(false);
    }
  };

  const fetchAdherence = async () => {
    try {
      setLoadingAdherence(true);
      const response = await authService.get('/medications/adherence?days=30');
      const result = await response.json();

      if (result.status === 'success') {
        setAdherenceData(result.data);
      }
    } catch (err) {
      console.error('Error fetching adherence:', err);
    } finally {
      setLoadingAdherence(false);
    }
  };

  const handleAddMedication = async () => {
    try {
      setError('');
      setSuccess('');

      // Validation
      if (!formData.name || !formData.dosage) {
        setError('Please fill in medication name and dosage');
        return;
      }

      const response = await authService.post('/medications', formData);
      const result = await response.json();

      if (result.status === 'success') {
        setSuccess('Medication added successfully!');
        setShowAddForm(false);
        fetchMedications();
        
        // Reset form
        setFormData({
          name: '',
          dosage: '',
          frequency: 'daily',
          custom_frequency: '',
          start_date: new Date().toISOString().split('T')[0],
          end_date: '',
          times: [],
          instructions: '',
          reminders_enabled: true
        });
      } else {
        setError(result.message || 'Failed to add medication');
      }
    } catch (err) {
      console.error('Error adding medication:', err);
      setError('Network error. Please try again.');
    }
  };

  const handleLogIntake = async (medId, wasTaken) => {
    try {
      const response = await authService.post(`/medications/${medId}/log`, {
        was_taken: wasTaken,
        notes: ''
      });
      const result = await response.json();

      if (result.status === 'success') {
        setSuccess(wasTaken ? 'Medication intake logged!' : 'Missed dose logged');
        fetchAdherence(); // Refresh adherence stats
      }
    } catch (err) {
      console.error('Error logging intake:', err);
      setError('Failed to log medication intake');
    }
  };

  const handleDeactivateMedication = async (medId) => {
    try {
      const response = await authService.patch(`/medications/${medId}`, {
        is_active: false
      });
      const result = await response.json();

      if (result.status === 'success') {
        setSuccess('Medication deactivated');
        fetchMedications();
      }
    } catch (err) {
      console.error('Error deactivating medication:', err);
      setError('Failed to deactivate medication');
    }
  };

  const addTime = () => {
    if (timeInput && !formData.times.includes(timeInput)) {
      setFormData({
        ...formData,
        times: [...formData.times, timeInput]
      });
    }
  };

  const removeTime = (time) => {
    setFormData({
      ...formData,
      times: formData.times.filter(t => t !== time)
    });
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading medications...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto p-6 space-y-6">
      {/* Header with Adherence Stats */}
      <div className="bg-gradient-to-r from-blue-600 to-indigo-600 rounded-lg shadow-lg p-6 text-white">
        <div className="flex justify-between items-start">
          <div>
            <h1 className="text-3xl font-bold mb-2">My Medications</h1>
            <p className="text-blue-100">Track and manage your medications</p>
          </div>
          {adherenceData && !loadingAdherence && (
            <div className="bg-white bg-opacity-20 rounded-lg p-4 text-center">
              <div className="text-4xl font-bold">{adherenceData.adherence_rate}%</div>
              <div className="text-sm text-blue-100">30-day adherence</div>
              <div className="text-xs text-blue-100 mt-1">
                {adherenceData.taken_doses}/{adherenceData.total_doses} doses
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Error/Success Messages */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
          {error}
        </div>
      )}
      {success && (
        <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-lg">
          {success}
        </div>
      )}

      {/* Add Medication Button */}
      <div className="flex justify-end">
        <button
          onClick={() => setShowAddForm(!showAddForm)}
          className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition flex items-center gap-2 font-semibold"
        >
          <span className="text-xl">{showAddForm ? '✕' : '+'}</span>
          {showAddForm ? 'Cancel' : 'Add Medication'}
        </button>
      </div>

      {/* Add Medication Form */}
      {showAddForm && (
        <div className="bg-white rounded-lg shadow-lg p-6 border-2 border-blue-200">
          <h2 className="text-xl font-bold mb-6 text-gray-800">Add New Medication</h2>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Medication Name *
              </label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({...formData, name: e.target.value})}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                placeholder="e.g., Aspirin"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Dosage *
              </label>
              <input
                type="text"
                value={formData.dosage}
                onChange={(e) => setFormData({...formData, dosage: e.target.value})}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                placeholder="e.g., 100mg"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Frequency
              </label>
              <select
                value={formData.frequency}
                onChange={(e) => setFormData({...formData, frequency: e.target.value})}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              >
                <option value="daily">Daily</option>
                <option value="twice_daily">Twice Daily</option>
                <option value="three_times_daily">Three Times Daily</option>
                <option value="weekly">Weekly</option>
                <option value="as_needed">As Needed</option>
                <option value="custom">Custom</option>
              </select>
            </div>

            {formData.frequency === 'custom' && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Custom Frequency
                </label>
                <input
                  type="text"
                  value={formData.custom_frequency}
                  onChange={(e) => setFormData({...formData, custom_frequency: e.target.value})}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  placeholder="e.g., Every other day"
                />
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Start Date
              </label>
              <input
                type="date"
                value={formData.start_date}
                onChange={(e) => setFormData({...formData, start_date: e.target.value})}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                End Date (Optional)
              </label>
              <input
                type="date"
                value={formData.end_date}
                onChange={(e) => setFormData({...formData, end_date: e.target.value})}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          {/* Times */}
          <div className="mt-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Reminder Times
            </label>
            <div className="flex gap-2 mb-2">
              <input
                type="time"
                value={timeInput}
                onChange={(e) => setTimeInput(e.target.value)}
                className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              />
              <button
                onClick={addTime}
                className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700"
              >
                Add Time
              </button>
            </div>
            <div className="flex flex-wrap gap-2">
              {formData.times.map((time, index) => (
                <span
                  key={index}
                  className="px-3 py-1 bg-blue-100 text-blue-700 rounded-full text-sm flex items-center gap-2"
                >
                  {time}
                  <button
                    onClick={() => removeTime(time)}
                    className="text-blue-900 hover:text-red-600 font-bold"
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>
          </div>

          {/* Instructions */}
          <div className="mt-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Instructions
            </label>
            <textarea
              value={formData.instructions}
              onChange={(e) => setFormData({...formData, instructions: e.target.value})}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              rows="3"
              placeholder="e.g., Take with food"
            />
          </div>

          {/* Reminders Toggle */}
          <div className="mt-4 flex items-center">
            <input
              type="checkbox"
              checked={formData.reminders_enabled}
              onChange={(e) => setFormData({...formData, reminders_enabled: e.target.checked})}
              className="w-5 h-5 text-blue-600 rounded focus:ring-2 focus:ring-blue-500"
            />
            <label className="ml-2 text-sm text-gray-700">
              Enable reminders for this medication
            </label>
          </div>

          {/* Submit Button */}
          <div className="mt-6 flex gap-3">
            <button
              onClick={handleAddMedication}
              className="flex-1 px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-semibold"
            >
              Add Medication
            </button>
            <button
              onClick={() => setShowAddForm(false)}
              className="px-6 py-3 bg-gray-300 text-gray-700 rounded-lg hover:bg-gray-400"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Medications List */}
      {medications.length === 0 ? (
        <div className="bg-white rounded-lg shadow p-12 text-center">
          <div className="text-6xl mb-4">💊</div>
          <h3 className="text-xl font-semibold text-gray-700 mb-2">No medications yet</h3>
          <p className="text-gray-500 mb-6">Start by adding your first medication</p>
          <button
            onClick={() => setShowAddForm(true)}
            className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            Add Your First Medication
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {medications.map((med) => (
            <div key={med.id} className="bg-white rounded-lg shadow-lg p-6 hover:shadow-xl transition">
              <div className="flex justify-between items-start mb-4">
                <div className="flex-1">
                  <h3 className="text-xl font-bold text-gray-800">{med.name}</h3>
                  <p className="text-lg text-gray-600">{med.dosage}</p>
                </div>
                <span className="px-3 py-1 bg-green-100 text-green-800 rounded-full text-sm font-semibold">
                  Active
                </span>
              </div>

              <div className="space-y-2 text-sm mb-4">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-gray-700">Frequency:</span>
                  <span className="text-gray-600">
                    {med.frequency.replace('_', ' ').charAt(0).toUpperCase() + 
                     med.frequency.replace('_', ' ').slice(1)}
                  </span>
                </div>

                {med.times && med.times.length > 0 && (
                  <div className="flex items-start gap-2">
                    <span className="font-medium text-gray-700">Times:</span>
                    <div className="flex flex-wrap gap-1">
                      {med.times.map((time, idx) => (
                        <span key={idx} className="px-2 py-1 bg-blue-50 text-blue-700 rounded text-xs">
                          {time}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {med.instructions && (
                  <div className="flex items-start gap-2">
                    <span className="font-medium text-gray-700">Instructions:</span>
                    <span className="text-gray-600">{med.instructions}</span>
                  </div>
                )}

                <div className="flex items-center gap-2">
                  <span className="font-medium text-gray-700">Started:</span>
                  <span className="text-gray-600">
                    {new Date(med.start_date).toLocaleDateString()}
                  </span>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex gap-2 pt-4 border-t border-gray-200">
                <button
                  onClick={() => handleLogIntake(med.id, true)}
                  className="flex-1 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 text-sm font-semibold"
                >
                  ✓ Taken
                </button>
                <button
                  onClick={() => handleLogIntake(med.id, false)}
                  className="flex-1 px-4 py-2 bg-yellow-600 text-white rounded-lg hover:bg-yellow-700 text-sm font-semibold"
                >
                  ✕ Missed
                </button>
                <button
                  onClick={() => handleDeactivateMedication(med.id)}
                  className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 text-sm"
                >
                  Stop
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default MedicationsPage;