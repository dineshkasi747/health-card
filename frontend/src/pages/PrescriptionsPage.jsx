// src/pages/Prescriptions.jsx
import React, { useState, useEffect } from 'react';
import { FileText, Download, Eye, Calendar, User, Pill, Clock, AlertCircle, Filter, Search } from 'lucide-react';
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

const Prescriptions = () => {
  const [prescriptions, setPresciptions] = useState([]);
  const [filteredPrescriptions, setFilteredPrescriptions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [filterStatus, setFilterStatus] = useState('all'); // all, active, expired
  const [selectedPrescription, setSelectedPrescription] = useState(null);
  const [showDetailModal, setShowDetailModal] = useState(false);

  useEffect(() => {
    fetchPrescriptions();
  }, []);

  useEffect(() => {
    filterPrescriptionsList();
  }, [prescriptions, searchTerm, filterStatus]);

  // ENDPOINT: GET /api/medications/prescriptions
  const fetchPrescriptions = async () => {
    try {
      setLoading(true);
      const token = localStorage.getItem('token');
      const response = await axios.get(`${API_BASE_URL}/medications/prescriptions`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setPresciptions(response.data.prescriptions || []);
      setError('');
    } catch (err) {
      console.error('Error fetching prescriptions:', err);
      setError('Failed to load prescriptions');
    } finally {
      setLoading(false);
    }
  };

  const filterPrescriptionsList = () => {
    let filtered = [...prescriptions];

    // Filter by search term
    if (searchTerm) {
      filtered = filtered.filter(prescription =>
        prescription.medicationName.toLowerCase().includes(searchTerm.toLowerCase()) ||
        prescription.doctorName.toLowerCase().includes(searchTerm.toLowerCase())
      );
    }

    // Filter by status
    if (filterStatus !== 'all') {
      const now = new Date();
      filtered = filtered.filter(prescription => {
        const expiryDate = new Date(prescription.expiryDate);
        if (filterStatus === 'active') {
          return expiryDate >= now;
        } else if (filterStatus === 'expired') {
          return expiryDate < now;
        }
        return true;
      });
    }

    setFilteredPrescriptions(filtered);
  };

  // ENDPOINT: GET /api/medications/prescriptions/:id/download
  const handleDownload = async (prescriptionId, fileName) => {
    try {
      const token = localStorage.getItem('token');
      const response = await axios.get(
        `${API_BASE_URL}/medications/prescriptions/${prescriptionId}/download`,
        {
          headers: { Authorization: `Bearer ${token}` },
          responseType: 'blob'
        }
      );

      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', fileName || `prescription_${prescriptionId}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (err) {
      console.error('Error downloading prescription:', err);
      alert('Failed to download prescription');
    }
  };

  const handleViewDetails = (prescription) => {
    setSelectedPrescription(prescription);
    setShowDetailModal(true);
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    });
  };

  const isExpired = (expiryDate) => {
    return new Date(expiryDate) < new Date();
  };

  const getStatusBadge = (expiryDate) => {
    if (isExpired(expiryDate)) {
      return (
        <span className="px-3 py-1 bg-red-100 text-red-700 text-xs font-medium rounded-full">
          Expired
        </span>
      );
    }
    return (
      <span className="px-3 py-1 bg-green-100 text-green-700 text-xs font-medium rounded-full">
        Active
      </span>
    );
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
          <h1 className="text-2xl font-bold text-gray-800 mb-1">Prescriptions</h1>
          <p className="text-gray-600">View and manage your medical prescriptions</p>
        </div>

        {/* Error Message */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6 flex items-center gap-3">
            <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0" />
            <p className="text-red-700">{error}</p>
          </div>
        )}

        {/* Search and Filter */}
        <div className="bg-white rounded-lg shadow-sm p-4 mb-6">
          <div className="flex flex-col md:flex-row gap-4">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
              <input
                type="text"
                placeholder="Search by medication or doctor name..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
            <div className="flex items-center gap-2">
              <Filter className="w-5 h-5 text-gray-400" />
              <select
                value={filterStatus}
                onChange={(e) => setFilterStatus(e.target.value)}
                className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                <option value="all">All Prescriptions</option>
                <option value="active">Active Only</option>
                <option value="expired">Expired Only</option>
              </select>
            </div>
          </div>
        </div>

        {/* Prescriptions List */}
        {filteredPrescriptions.length === 0 ? (
          <div className="bg-white rounded-lg shadow-sm p-12 text-center">
            <FileText className="w-16 h-16 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-800 mb-2">No Prescriptions Found</h3>
            <p className="text-gray-600">
              {searchTerm || filterStatus !== 'all' 
                ? 'Try adjusting your search or filters' 
                : 'Your prescriptions will appear here'}
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4">
            {filteredPrescriptions.map((prescription) => (
              <div
                key={prescription._id}
                className="bg-white rounded-lg shadow-sm p-6 hover:shadow-md transition-shadow"
              >
                <div className="flex flex-col md:flex-row justify-between gap-4">
                  <div className="flex-1">
                    <div className="flex items-start justify-between mb-3">
                      <div>
                        <h3 className="text-xl font-semibold text-gray-800 mb-1">
                          {prescription.medicationName}
                        </h3>
                        <p className="text-gray-600">{prescription.dosage}</p>
                      </div>
                      {getStatusBadge(prescription.expiryDate)}
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
                      <div className="flex items-center gap-3 text-sm">
                        <User className="w-4 h-4 text-gray-400" />
                        <div>
                          <p className="text-gray-500">Prescribed by</p>
                          <p className="text-gray-800 font-medium">{prescription.doctorName}</p>
                        </div>
                      </div>

                      <div className="flex items-center gap-3 text-sm">
                        <Calendar className="w-4 h-4 text-gray-400" />
                        <div>
                          <p className="text-gray-500">Date Issued</p>
                          <p className="text-gray-800 font-medium">{formatDate(prescription.dateIssued)}</p>
                        </div>
                      </div>

                      <div className="flex items-center gap-3 text-sm">
                        <Clock className="w-4 h-4 text-gray-400" />
                        <div>
                          <p className="text-gray-500">Valid Until</p>
                          <p className={`font-medium ${isExpired(prescription.expiryDate) ? 'text-red-600' : 'text-gray-800'}`}>
                            {formatDate(prescription.expiryDate)}
                          </p>
                        </div>
                      </div>

                      <div className="flex items-center gap-3 text-sm">
                        <Pill className="w-4 h-4 text-gray-400" />
                        <div>
                          <p className="text-gray-500">Refills</p>
                          <p className="text-gray-800 font-medium">
                            {prescription.refillsRemaining || 0} remaining
                          </p>
                        </div>
                      </div>
                    </div>

                    {prescription.instructions && (
                      <div className="mt-4 p-3 bg-blue-50 rounded-lg">
                        <p className="text-sm text-blue-900">
                          <strong>Instructions:</strong> {prescription.instructions}
                        </p>
                      </div>
                    )}
                  </div>

                  <div className="flex md:flex-col gap-2">
                    <button
                      onClick={() => handleViewDetails(prescription)}
                      className="flex items-center gap-2 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
                    >
                      <Eye className="w-4 h-4" />
                      <span>View</span>
                    </button>
                    <button
                      onClick={() => handleDownload(prescription._id, prescription.fileName)}
                      className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                    >
                      <Download className="w-4 h-4" />
                      <span>Download</span>
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Detail Modal */}
        {showDetailModal && selectedPrescription && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
            <div className="bg-white rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto">
              <div className="p-6">
                <div className="flex justify-between items-start mb-6">
                  <h2 className="text-2xl font-bold text-gray-800">Prescription Details</h2>
                  <button
                    onClick={() => setShowDetailModal(false)}
                    className="text-gray-500 hover:text-gray-700"
                  >
                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>

                <div className="space-y-4">
                  <div>
                    <label className="text-sm text-gray-500">Medication Name</label>
                    <p className="text-lg font-semibold text-gray-800">{selectedPrescription.medicationName}</p>
                  </div>

                  <div>
                    <label className="text-sm text-gray-500">Dosage</label>
                    <p className="text-gray-800">{selectedPrescription.dosage}</p>
                  </div>

                  <div>
                    <label className="text-sm text-gray-500">Prescribed By</label>
                    <p className="text-gray-800">{selectedPrescription.doctorName}</p>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="text-sm text-gray-500">Date Issued</label>
                      <p className="text-gray-800">{formatDate(selectedPrescription.dateIssued)}</p>
                    </div>
                    <div>
                      <label className="text-sm text-gray-500">Expiry Date</label>
                      <p className="text-gray-800">{formatDate(selectedPrescription.expiryDate)}</p>
                    </div>
                  </div>

                  <div>
                    <label className="text-sm text-gray-500">Refills Remaining</label>
                    <p className="text-gray-800">{selectedPrescription.refillsRemaining || 0}</p>
                  </div>

                  {selectedPrescription.instructions && (
                    <div>
                      <label className="text-sm text-gray-500">Instructions</label>
                      <p className="text-gray-800">{selectedPrescription.instructions}</p>
                    </div>
                  )}

                  {selectedPrescription.notes && (
                    <div>
                      <label className="text-sm text-gray-500">Additional Notes</label>
                      <p className="text-gray-800">{selectedPrescription.notes}</p>
                    </div>
                  )}
                </div>

                <div className="mt-6 flex gap-3">
                  <button
                    onClick={() => handleDownload(selectedPrescription._id, selectedPrescription.fileName)}
                    className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                  >
                    <Download className="w-4 h-4" />
                    <span>Download Prescription</span>
                  </button>
                  <button
                    onClick={() => setShowDetailModal(false)}
                    className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50"
                  >
                    Close
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default Prescriptions;