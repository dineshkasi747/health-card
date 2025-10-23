import React, { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const VitalsPage = ({ authService }) => {
  const [vitals, setVitals] = useState([]);
  const [selectedVitalType, setSelectedVitalType] = useState('heart_rate');
  const [trendData, setTrendData] = useState(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [loading, setLoading] = useState(true);
  const [formData, setFormData] = useState({
    vital_type: 'heart_rate',
    value: '',
    unit: 'bpm',
    notes: ''
  });

  const vitalTypes = [
    { type: 'heart_rate', name: 'Heart Rate', unit: 'bpm', icon: '💓', color: 'red' },
    { type: 'blood_pressure', name: 'Blood Pressure', unit: 'mmHg', icon: '🩸', color: 'blue' },
    { type: 'temperature', name: 'Temperature', unit: '°F', icon: '🌡️', color: 'orange' },
    { type: 'oxygen_saturation', name: 'Oxygen Saturation', unit: '%', icon: '🫁', color: 'green' },
    { type: 'weight', name: 'Weight', unit: 'kg', icon: '⚖️', color: 'purple' },
    { type: 'blood_glucose', name: 'Blood Glucose', unit: 'mg/dL', icon: '🩺', color: 'yellow' }
  ];

  useEffect(() => {
    fetchVitals();
    fetchTrend(selectedVitalType);
  }, [selectedVitalType]);

  const fetchVitals = async () => {
    try {
      const response = await authService.get('/vitals?limit=50');
      const result = await response.json();
      if (result.status === 'success') {
        setVitals(result.data);
      }
    } catch (error) {
      console.error('Error fetching vitals:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchTrend = async (vitalType) => {
    try {
      const response = await authService.get(`/vitals/${vitalType}/trend?days=30`);
      const result = await response.json();
      if (result.status === 'success') {
        setTrendData(result.data);
      }
    } catch (error) {
      console.error('Error fetching trend:', error);
    }
  };

  const handleAddVital = async (e) => {
    e.preventDefault();
    try {
      const response = await authService.post('/vitals', formData);
      const result = await response.json();
      
      if (result.status === 'success') {
        setShowAddForm(false);
        setFormData({
          vital_type: 'heart_rate',
          value: '',
          unit: 'bpm',
          notes: ''
        });
        fetchVitals();
        fetchTrend(selectedVitalType);
      }
    } catch (error) {
      console.error('Error adding vital:', error);
      alert('Failed to add vital record');
    }
  };

  const getLatestVital = (type) => {
    const filtered = vitals.filter(v => v.vital_type === type);
    return filtered.length > 0 ? filtered[0] : null;
  };

  const formatChartData = () => {
    if (!trendData || !trendData.records) return [];
    
    return trendData.records.map(record => ({
      date: new Date(record.recorded_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
      value: record.value,
      fullDate: record.recorded_at
    }));
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
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-bold text-gray-800">Track Vitals</h2>
          <p className="text-gray-600 mt-1">Monitor your health metrics</p>
        </div>
        <button
          onClick={() => setShowAddForm(true)}
          className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors shadow-lg hover:shadow-xl"
        >
          + Add Vital Record
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {vitalTypes.map((vital) => {
          const latest = getLatestVital(vital.type);
          return (
            <div
              key={vital.type}
              onClick={() => setSelectedVitalType(vital.type)}
              className={`bg-white rounded-xl shadow-md p-6 cursor-pointer transition-all hover:shadow-lg ${
                selectedVitalType === vital.type ? 'ring-2 ring-blue-500' : ''
              }`}
            >
              <div className="flex items-center justify-between mb-4">
                <span className="text-3xl">{vital.icon}</span>
                <div className={`w-12 h-12 bg-${vital.color}-100 rounded-full flex items-center justify-center`}>
                  <div className={`w-6 h-6 bg-${vital.color}-500 rounded-full`}></div>
                </div>
              </div>
              <h4 className="text-gray-600 text-sm font-medium mb-2">{vital.name}</h4>
              {latest ? (
                <>
                  <p className="text-3xl font-bold text-gray-800">
                    {latest.value} <span className="text-lg text-gray-500">{vital.unit}</span>
                  </p>
                  <p className="text-xs text-gray-500 mt-2">
                    {new Date(latest.recorded_at).toLocaleString()}
                  </p>
                </>
              ) : (
                <p className="text-xl text-gray-400">No data</p>
              )}
            </div>
          );
        })}
      </div>

      {trendData && trendData.records && trendData.records.length > 0 && (
        <div className="bg-white rounded-xl shadow-md p-6">
          <div className="flex justify-between items-center mb-6">
            <div>
              <h3 className="text-lg font-semibold text-gray-800">
                {vitalTypes.find(v => v.type === selectedVitalType)?.name} Trend
              </h3>
              <p className="text-sm text-gray-500 mt-1">Last 30 days</p>
            </div>
            <div className="flex items-center space-x-4">
              <div className="text-center">
                <p className="text-xs text-gray-500">Average</p>
                <p className="text-lg font-semibold text-blue-600">{trendData.average}</p>
              </div>
              <div className="text-center">
                <p className="text-xs text-gray-500">Trend</p>
                <p className={`text-lg font-semibold ${
                  trendData.trend === 'increasing' ? 'text-red-600' :
                  trendData.trend === 'decreasing' ? 'text-green-600' : 'text-gray-600'
                }`}>
                  {trendData.trend === 'increasing' ? '↑' : 
                   trendData.trend === 'decreasing' ? '↓' : '→'}
                </p>
              </div>
            </div>
          </div>
          
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={formatChartData()}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Line 
                type="monotone" 
                dataKey="value" 
                stroke="#3b82f6" 
                strokeWidth={2}
                dot={{ fill: '#3b82f6', r: 4 }}
                activeDot={{ r: 6 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      <div className="bg-white rounded-xl shadow-md p-6">
        <h3 className="text-lg font-semibold mb-4 text-gray-800">Recent Vitals History</h3>
        <div className="space-y-3">
          {vitals.slice(0, 10).map((vital, i) => {
            const vitalInfo = vitalTypes.find(v => v.type === vital.vital_type);
            return (
              <div key={i} className="flex justify-between items-center p-4 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors">
                <div className="flex items-center">
                  <span className="text-2xl mr-4">{vitalInfo?.icon}</span>
                  <div>
                    <p className="font-medium text-gray-800">{vitalInfo?.name}</p>
                    <p className="text-sm text-gray-500">
                      {new Date(vital.recorded_at).toLocaleString()}
                    </p>
                  </div>
                </div>
                <p className="text-xl font-semibold text-gray-800">
                  {vital.value} <span className="text-sm text-gray-500">{vital.unit}</span>
                </p>
              </div>
            );
          })}
        </div>
        {vitals.length === 0 && (
          <p className="text-center text-gray-500 py-8">No vitals recorded yet. Add your first vital record!</p>
        )}
      </div>

      {showAddForm && (
        <AddVitalModal
          formData={formData}
          setFormData={setFormData}
          vitalTypes={vitalTypes}
          onSubmit={handleAddVital}
          onClose={() => setShowAddForm(false)}
        />
      )}
    </div>
  );
};

const AddVitalModal = ({ formData, setFormData, vitalTypes, onSubmit, onClose }) => (
  <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
    <div className="bg-white rounded-xl shadow-2xl p-8 max-w-md w-full mx-4">
      <h3 className="text-2xl font-bold mb-6 text-gray-800">Add Vital Record</h3>
      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Vital Type</label>
          <select
            value={formData.vital_type}
            onChange={(e) => {
              const vital = vitalTypes.find(v => v.type === e.target.value);
              setFormData({
                ...formData,
                vital_type: e.target.value,
                unit: vital?.unit || ''
              });
            }}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          >
            {vitalTypes.map(vital => (
              <option key={vital.type} value={vital.type}>
                {vital.icon} {vital.name}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Value</label>
          <div className="flex">
            <input
              type="number"
              step="0.1"
              value={formData.value}
              onChange={(e) => setFormData({...formData, value: e.target.value})}
              className="flex-1 px-4 py-2 border border-gray-300 rounded-l-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="Enter value"
              required
            />
            <span className="px-4 py-2 bg-gray-100 border border-l-0 border-gray-300 rounded-r-lg text-gray-600">
              {formData.unit}
            </span>
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Notes (Optional)</label>
          <textarea
            value={formData.notes}
            onChange={(e) => setFormData({...formData, notes: e.target.value})}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            rows="3"
            placeholder="Add any notes..."
          />
        </div>

        <div className="flex space-x-3 pt-4">
          <button
            onClick={onClose}
            className="flex-1 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={onSubmit}
            className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            Add Vital
          </button>
        </div>
      </div>
    </div>
  </div>
);

export default VitalsPage;