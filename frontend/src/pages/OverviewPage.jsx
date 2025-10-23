import React, { useState, useEffect } from 'react';

// ============================================================================
// OVERVIEW PAGE - Dashboard Homepage
// ============================================================================
const OverviewPage = ({ authService }) => {
  const [healthScore, setHealthScore] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchHealthAnalytics();
  }, []);

  const fetchHealthAnalytics = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await authService.get('/analytics/health-score');
      const result = await response.json();
      
      if (result.status === 'success') {
        setHealthScore(result.data);
      } else {
        setError(result.message || 'Failed to load health analytics');
      }
    } catch (err) {
      console.error('Error fetching health analytics:', err);
      setError('Unable to connect to server');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
        <p className="text-red-800">❌ {error}</p>
        <button
          onClick={fetchHealthAnalytics}
          className="mt-4 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Health Metrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <StatCard
          title="Health Score"
          value={healthScore?.health_score || 0}
          icon="❤️"
          color="blue"
          subtitle="Overall health rating"
        />
        <StatCard
          title="Medication Adherence"
          value={`${healthScore?.medication_adherence || 0}%`}
          icon="💊"
          color="green"
          subtitle="Medication compliance rate"
        />
        <StatCard
          title="Upcoming Appointments"
          value={healthScore?.upcoming_appointments || 0}
          icon="📅"
          color="purple"
          subtitle="Scheduled consultations"
        />
      </div>

      {/* Vitals Summary */}
      {healthScore?.vitals_summary && Object.keys(healthScore.vitals_summary).length > 0 && (
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold mb-4">Recent Vitals</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {Object.entries(healthScore.vitals_summary).map(([vitalType, data]) => (
              <div key={vitalType} className="p-4 bg-gray-50 rounded-lg">
                <p className="text-sm text-gray-600 capitalize mb-1">
                  {vitalType.replace('_', ' ')}
                </p>
                <p className="text-2xl font-bold text-blue-600">
                  {data.latest?.value || '--'} {data.latest?.unit || ''}
                </p>
                <p className="text-xs text-gray-500 mt-1">
                  {data.count} records • Last: {data.latest?.date ? new Date(data.latest.date).toLocaleDateString() : 'N/A'}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Health Recommendations */}
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold mb-4">Health Recommendations</h3>
        <div className="space-y-3">
          {healthScore?.recommendations && healthScore.recommendations.length > 0 ? (
            healthScore.recommendations.map((rec, i) => (
              <div key={i} className="flex items-start p-4 bg-blue-50 rounded-lg hover:bg-blue-100 transition-colors">
                <span className="text-blue-600 text-xl mr-3">💡</span>
                <p className="text-sm text-gray-700 flex-1">{rec}</p>
              </div>
            ))
          ) : (
            <div className="text-center py-8 text-gray-500">
              <p className="text-4xl mb-2">🎉</p>
              <p>Great job! You're doing well. Keep it up!</p>
            </div>
          )}
        </div>
      </div>

      {/* Quick Actions */}
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold mb-4">Quick Actions</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <QuickActionButton icon="💊" label="Log Medication" />
          <QuickActionButton icon="❤️" label="Add Vital" />
          <QuickActionButton icon="📅" label="Book Appointment" />
          <QuickActionButton icon="📄" label="Upload Prescription" />
        </div>
      </div>
    </div>
  );
};

// ============================================================================
// STAT CARD COMPONENT
// ============================================================================
const StatCard = ({ title, value, icon, color, subtitle }) => {
  const colorClasses = {
    blue: 'bg-blue-100 text-blue-600',
    green: 'bg-green-100 text-green-600',
    purple: 'bg-purple-100 text-purple-600',
    red: 'bg-red-100 text-red-600',
  };

  return (
    <div className="bg-white rounded-lg shadow p-6 hover:shadow-lg transition-shadow">
      <div className="flex items-center justify-between mb-4">
        <span className="text-3xl">{icon}</span>
        <div className={`w-12 h-12 rounded-full flex items-center justify-center ${colorClasses[color]}`}>
          <div className="w-6 h-6 bg-current rounded-full opacity-60"></div>
        </div>
      </div>
      <h3 className="text-gray-600 text-sm mb-1">{title}</h3>
      <p className="text-3xl font-bold text-gray-900 mb-1">{value}</p>
      {subtitle && <p className="text-xs text-gray-500">{subtitle}</p>}
    </div>
  );
};

// ============================================================================
// QUICK ACTION BUTTON
// ============================================================================
const QuickActionButton = ({ icon, label }) => (
  <button className="flex flex-col items-center justify-center p-4 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors">
    <span className="text-3xl mb-2">{icon}</span>
    <span className="text-sm text-gray-700 text-center">{label}</span>
  </button>
);

// ============================================================================
// DEMO WRAPPER
// ============================================================================
export default function OverviewPageDemo() {
  // Mock auth service for demo
  const mockAuthService = {
    get: async (endpoint) => {
      // Simulate API delay
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      return {
        json: async () => ({
          status: 'success',
          data: {
            health_score: 85,
            medication_adherence: 92.5,
            upcoming_appointments: 2,
            vitals_summary: {
              heart_rate: {
                count: 15,
                latest: { value: 72, unit: 'bpm', date: new Date().toISOString() }
              },
              blood_pressure: {
                count: 12,
                latest: { value: '120/80', unit: 'mmHg', date: new Date().toISOString() }
              },
              temperature: {
                count: 8,
                latest: { value: 98.6, unit: '°F', date: new Date().toISOString() }
              }
            },
            recommendations: [
              'Great job maintaining 90%+ medication adherence!',
              'Consider tracking your blood pressure more regularly',
              'You have 2 upcoming appointments this month'
            ]
          }
        })
      };
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-7xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Dashboard Overview</h1>
          <p className="text-gray-600 mt-2">Welcome back! Here's your health summary.</p>
        </div>
        <OverviewPage authService={mockAuthService} />
      </div>
    </div>
  );
}