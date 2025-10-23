import React, { useState, useEffect } from 'react';
import { authService } from '../App';  

const AppointmentsPage = () => {
  const [appointments, setAppointments] = useState([]);
  const [doctors, setDoctors] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showBookForm, setShowBookForm] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Form state for booking appointment
  const [formData, setFormData] = useState({
    doctor_id: '',
    scheduled_date: '',
    scheduled_time: '09:00',
    consultation_type: 'in_person',
    reason: ''
  });

  // Filter state
  const [filter, setFilter] = useState('upcoming'); // 'upcoming' or 'all'

  useEffect(() => {
    fetchAppointments();
    fetchDoctors();
  }, [filter]);

  const fetchAppointments = async () => {
    try {
      setLoading(true);
      const upcomingOnly = filter === 'upcoming';
      const response = await authService.get(`/appointments?upcoming_only=${upcomingOnly}`);
      const result = await response.json();

      if (result.status === 'success') {
        setAppointments(result.data);
      } else {
        setError('Failed to load appointments');
      }
    } catch (err) {
      console.error('Error fetching appointments:', err);
      setError('Network error loading appointments');
    } finally {
      setLoading(false);
    }
  };

  const fetchDoctors = async () => {
    try {
      // In a real app, you'd have an endpoint to list available doctors
      // For now, we'll use a mock list
      const mockDoctors = [
        { id: '1', name: 'Dr. Sarah Johnson', specialization: 'General Physician' },
        { id: '2', name: 'Dr. Michael Chen', specialization: 'Cardiologist' },
        { id: '3', name: 'Dr. Emily Rodriguez', specialization: 'Dermatologist' },
        { id: '4', name: 'Dr. James Williams', specialization: 'Orthopedist' }
      ];
      setDoctors(mockDoctors);
    } catch (err) {
      console.error('Error fetching doctors:', err);
    }
  };

  const handleBookAppointment = async () => {
    try {
      setError('');
      setSuccess('');

      // Validation
      if (!formData.doctor_id || !formData.scheduled_date || !formData.reason) {
        setError('Please fill in all required fields');
        return;
      }

      // Check if date is in the future
      const selectedDate = new Date(formData.scheduled_date);
      const today = new Date();
      today.setHours(0, 0, 0, 0);
      
      if (selectedDate < today) {
        setError('Please select a future date');
        return;
      }

      const response = await authService.post('/appointments', formData);
      const result = await response.json();

      if (result.status === 'success') {
        setSuccess('Appointment booked successfully!');
        setShowBookForm(false);
        fetchAppointments();
        
        // Reset form
        setFormData({
          doctor_id: '',
          scheduled_date: '',
          scheduled_time: '09:00',
          consultation_type: 'in_person',
          reason: ''
        });
      } else {
        setError(result.message || 'Failed to book appointment');
      }
    } catch (err) {
      console.error('Error booking appointment:', err);
      setError('Network error. Please try again.');
    }
  };

  const handleCancelAppointment = async (appointmentId) => {
    if (!confirm('Are you sure you want to cancel this appointment?')) {
      return;
    }

    try {
      const response = await authService.patch(
        `/appointments/${appointmentId}/status`,
        { status: 'cancelled' }
      );
      const result = await response.json();

      if (result.status === 'success') {
        setSuccess('Appointment cancelled successfully');
        fetchAppointments();
      } else {
        setError('Failed to cancel appointment');
      }
    } catch (err) {
      console.error('Error cancelling appointment:', err);
      setError('Network error. Please try again.');
    }
  };

  const getStatusColor = (status) => {
    const colors = {
      scheduled: 'bg-blue-100 text-blue-800',
      completed: 'bg-green-100 text-green-800',
      cancelled: 'bg-red-100 text-red-800',
      rescheduled: 'bg-yellow-100 text-yellow-800',
      no_show: 'bg-gray-100 text-gray-800'
    };
    return colors[status] || 'bg-gray-100 text-gray-800';
  };

  const getConsultationIcon = (type) => {
    const icons = {
      in_person: '🏥',
      video: '📹',
      phone: '📞'
    };
    return icons[type] || '🏥';
  };

  // Generate time slots
  const generateTimeSlots = () => {
    const slots = [];
    for (let hour = 9; hour <= 17; hour++) {
      slots.push(`${hour.toString().padStart(2, '0')}:00`);
      if (hour < 17) {
        slots.push(`${hour.toString().padStart(2, '0')}:30`);
      }
    }
    return slots;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading appointments...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="bg-gradient-to-r from-purple-600 to-indigo-600 rounded-lg shadow-lg p-6 text-white">
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-3xl font-bold mb-2">My Appointments</h1>
            <p className="text-purple-100">Manage your healthcare appointments</p>
          </div>
          <div className="text-right">
            <div className="text-4xl font-bold">{appointments.length}</div>
            <div className="text-sm text-purple-100">
              {filter === 'upcoming' ? 'Upcoming' : 'Total'}
            </div>
          </div>
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

      {/* Action Bar */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        {/* Filter Buttons */}
        <div className="flex gap-2">
          <button
            onClick={() => setFilter('upcoming')}
            className={`px-4 py-2 rounded-lg font-medium transition ${
              filter === 'upcoming'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
            }`}
          >
            Upcoming
          </button>
          <button
            onClick={() => setFilter('all')}
            className={`px-4 py-2 rounded-lg font-medium transition ${
              filter === 'all'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
            }`}
          >
            All Appointments
          </button>
        </div>

        {/* Book Appointment Button */}
        <button
          onClick={() => setShowBookForm(!showBookForm)}
          className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition flex items-center gap-2 font-semibold"
        >
          <span className="text-xl">{showBookForm ? '✕' : '+'}</span>
          {showBookForm ? 'Cancel' : 'Book Appointment'}
        </button>
      </div>

      {/* Book Appointment Form */}
      {showBookForm && (
        <div className="bg-white rounded-lg shadow-lg p-6 border-2 border-blue-200">
          <h2 className="text-xl font-bold mb-6 text-gray-800">Book New Appointment</h2>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Select Doctor *
              </label>
              <select
                value={formData.doctor_id}
                onChange={(e) => setFormData({...formData, doctor_id: e.target.value})}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              >
                <option value="">Choose a doctor...</option>
                {doctors.map((doc) => (
                  <option key={doc.id} value={doc.id}>
                    {doc.name} - {doc.specialization}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Consultation Type
              </label>
              <select
                value={formData.consultation_type}
                onChange={(e) => setFormData({...formData, consultation_type: e.target.value})}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              >
                <option value="in_person">In-Person Visit</option>
                <option value="video">Video Call</option>
                <option value="phone">Phone Call</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Date *
              </label>
              <input
                type="date"
                value={formData.scheduled_date}
                onChange={(e) => setFormData({...formData, scheduled_date: e.target.value})}
                min={new Date().toISOString().split('T')[0]}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Time *
              </label>
              <select
                value={formData.scheduled_time}
                onChange={(e) => setFormData({...formData, scheduled_time: e.target.value})}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              >
                {generateTimeSlots().map((time) => (
                  <option key={time} value={time}>
                    {time}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="mt-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Reason for Visit *
            </label>
            <textarea
              value={formData.reason}
              onChange={(e) => setFormData({...formData, reason: e.target.value})}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              rows="3"
              placeholder="Describe your symptoms or reason for consultation..."
            />
          </div>

          <div className="mt-6 flex gap-3">
            <button
              onClick={handleBookAppointment}
              className="flex-1 px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-semibold"
            >
              Book Appointment
            </button>
            <button
              onClick={() => setShowBookForm(false)}
              className="px-6 py-3 bg-gray-300 text-gray-700 rounded-lg hover:bg-gray-400"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Appointments List */}
      {appointments.length === 0 ? (
        <div className="bg-white rounded-lg shadow p-12 text-center">
          <div className="text-6xl mb-4">📅</div>
          <h3 className="text-xl font-semibold text-gray-700 mb-2">
            {filter === 'upcoming' ? 'No upcoming appointments' : 'No appointments yet'}
          </h3>
          <p className="text-gray-500 mb-6">
            {filter === 'upcoming' 
              ? 'You have no scheduled appointments' 
              : 'Start by booking your first appointment'}
          </p>
          <button
            onClick={() => setShowBookForm(true)}
            className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            Book Your First Appointment
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          {appointments.map((apt) => (
            <div key={apt.id} className="bg-white rounded-lg shadow-lg p-6 hover:shadow-xl transition">
              <div className="flex flex-col md:flex-row justify-between gap-4">
                {/* Left Side - Main Info */}
                <div className="flex-1">
                  <div className="flex items-start gap-4">
                    <div className="text-4xl">
                      {getConsultationIcon(apt.consultation_type)}
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        <h3 className="text-xl font-bold text-gray-800">
                          {apt.doctor_name || 'Dr. Smith'}
                        </h3>
                        <span className={`px-3 py-1 rounded-full text-xs font-semibold ${getStatusColor(apt.status)}`}>
                          {apt.status.replace('_', ' ').toUpperCase()}
                        </span>
                      </div>
                      
                      <p className="text-gray-600 mb-3">{apt.reason}</p>
                      
                      <div className="space-y-1 text-sm">
                        <div className="flex items-center gap-2 text-gray-700">
                          <span className="font-medium">📅 Date:</span>
                          <span>{new Date(apt.scheduled_date).toLocaleDateString('en-US', {
                            weekday: 'long',
                            year: 'numeric',
                            month: 'long',
                            day: 'numeric'
                          })}</span>
                        </div>
                        <div className="flex items-center gap-2 text-gray-700">
                          <span className="font-medium">🕐 Time:</span>
                          <span>{apt.scheduled_time}</span>
                        </div>
                        <div className="flex items-center gap-2 text-gray-700">
                          <span className="font-medium">📍 Type:</span>
                          <span className="capitalize">
                            {apt.consultation_type.replace('_', ' ')}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Right Side - Actions */}
                {apt.status === 'scheduled' && (
                  <div className="flex flex-col gap-2 md:w-48">
                    <button
                      onClick={() => handleCancelAppointment(apt.id)}
                      className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 text-sm font-semibold"
                    >
                      Cancel Appointment
                    </button>
                    <button className="px-4 py-2 bg-blue-100 text-blue-700 rounded-lg hover:bg-blue-200 text-sm font-semibold">
                      Reschedule
                    </button>
                    {apt.consultation_type === 'video' && (
                      <button className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 text-sm font-semibold">
                        Join Video Call
                      </button>
                    )}
                  </div>
                )}

                {apt.status === 'completed' && (
                  <div className="flex flex-col gap-2 md:w-48">
                    <button className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-semibold">
                      View Notes
                    </button>
                    <button className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 text-sm font-semibold">
                      Book Follow-up
                    </button>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Quick Stats */}
      {appointments.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-white rounded-lg shadow p-4 text-center">
            <div className="text-3xl font-bold text-blue-600">
              {appointments.filter(a => a.status === 'scheduled').length}
            </div>
            <div className="text-sm text-gray-600">Scheduled</div>
          </div>
          <div className="bg-white rounded-lg shadow p-4 text-center">
            <div className="text-3xl font-bold text-green-600">
              {appointments.filter(a => a.status === 'completed').length}
            </div>
            <div className="text-sm text-gray-600">Completed</div>
          </div>
          <div className="bg-white rounded-lg shadow p-4 text-center">
            <div className="text-3xl font-bold text-red-600">
              {appointments.filter(a => a.status === 'cancelled').length}
            </div>
            <div className="text-sm text-gray-600">Cancelled</div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AppointmentsPage;