import React, { useState, useEffect } from 'react';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const LabResultsPage = ({ authService }) => {
  const [labResults, setLabResults] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAddForm, setShowAddForm] = useState(false);
  const [selectedResult, setSelectedResult] = useState(null);
  const [uploadFile, setUploadFile] = useState(null);
  const [formData, setFormData] = useState({
    test_date: new Date().toISOString().split('T')[0],
    lab_name: '',
    tests: [{ test_name: '', result: '', unit: '', reference_range: '', status: 'normal' }]
  });

  useEffect(() => {
    fetchLabResults();
  }, []);

  const fetchLabResults = async () => {
    try {
      const response = await authService.get('/lab-results?limit=20');
      const result = await response.json();
      if (result.status === 'success') {
        setLabResults(result.data);
      }
    } catch (error) {
      console.error('Error fetching lab results:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleAddTest = () => {
    setFormData({
      ...formData,
      tests: [...formData.tests, { test_name: '', result: '', unit: '', reference_range: '', status: 'normal' }]
    });
  };

  const handleRemoveTest = (index) => {
    const newTests = formData.tests.filter((_, i) => i !== index);
    setFormData({ ...formData, tests: newTests });
  };

  const handleTestChange = (index, field, value) => {
    const newTests = [...formData.tests];
    newTests[index][field] = value;
    setFormData({ ...formData, tests: newTests });
  };

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      const allowedTypes = ['application/pdf', 'image/jpeg', 'image/png', 'image/jpg'];
      if (!allowedTypes.includes(file.type)) {
        alert('Invalid file type. Please upload PDF or image files.');
        return;
      }
      if (file.size > 10 * 1024 * 1024) {
        alert('File too large. Maximum size is 10MB.');
        return;
      }
      setUploadFile(file);
    }
  };

  const handleSubmit = async () => {
    if (!formData.lab_name || formData.tests.length === 0) {
      alert('Please fill in all required fields');
      return;
    }

    try {
      const formDataToSend = new FormData();
      formDataToSend.append('test_date', formData.test_date);
      formDataToSend.append('lab_name', formData.lab_name);
      formDataToSend.append('tests', JSON.stringify(formData.tests));
      
      if (uploadFile) {
        formDataToSend.append('file', uploadFile);
      }

      const response = await authService.uploadFile('/lab-results', uploadFile, {
        test_date: formData.test_date,
        lab_name: formData.lab_name,
        tests: formData.tests
      });
      
      const result = await response.json();
      
      if (result.status === 'success') {
        setShowAddForm(false);
        setFormData({
          test_date: new Date().toISOString().split('T')[0],
          lab_name: '',
          tests: [{ test_name: '', result: '', unit: '', reference_range: '', status: 'normal' }]
        });
        setUploadFile(null);
        fetchLabResults();
      }
    } catch (error) {
      console.error('Error adding lab result:', error);
      alert('Failed to add lab result');
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'normal': return 'bg-green-100 text-green-800';
      case 'abnormal': return 'bg-red-100 text-red-800';
      case 'borderline': return 'bg-yellow-100 text-yellow-800';
      default: return 'bg-gray-100 text-gray-800';
    }
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
          <h2 className="text-2xl font-bold text-gray-800">Lab Results</h2>
          <p className="text-gray-600 mt-1">View and manage your lab test reports</p>
        </div>
        <button
          onClick={() => setShowAddForm(true)}
          className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors shadow-lg hover:shadow-xl"
        >
          + Add Lab Result
        </button>
      </div>

      <div className="grid grid-cols-1 gap-6">
        {labResults.map((result, index) => (
          <div key={index} className="bg-white rounded-xl shadow-md overflow-hidden hover:shadow-lg transition-shadow">
            <div className="p-6">
              <div className="flex justify-between items-start mb-4">
                <div>
                  <h3 className="text-xl font-semibold text-gray-800">{result.lab_name}</h3>
                  <p className="text-sm text-gray-500 mt-1">
                    🗓️ Test Date: {new Date(result.test_date).toLocaleDateString('en-US', { 
                      year: 'numeric', 
                      month: 'long', 
                      day: 'numeric' 
                    })}
                  </p>
                </div>
                {result.report_url && (
                  <a
                    href={result.report_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="px-4 py-2 bg-blue-50 text-blue-600 rounded-lg hover:bg-blue-100 transition-colors"
                  >
                    📄 View Report
                  </a>
                )}
              </div>

              <div className="border-t pt-4">
                <button
                  onClick={() => setSelectedResult(selectedResult === index ? null : index)}
                  className="flex items-center justify-between w-full text-left"
                >
                  <span className="font-medium text-gray-700">
                    Tests: {result.tests?.length || 0}
                  </span>
                  <span className="text-gray-400">
                    {selectedResult === index ? '▲' : '▼'}
                  </span>
                </button>

                {selectedResult === index && (
                  <div className="mt-4 space-y-3">
                    {result.tests?.map((test, testIndex) => (
                      <div key={testIndex} className="p-4 bg-gray-50 rounded-lg">
                        <div className="flex justify-between items-start">
                          <div className="flex-1">
                            <h4 className="font-medium text-gray-800">{test.test_name}</h4>
                            <div className="mt-2 grid grid-cols-2 gap-4 text-sm">
                              <div>
                                <span className="text-gray-500">Result: </span>
                                <span className="font-semibold">{test.result} {test.unit}</span>
                              </div>
                              {test.reference_range && (
                                <div>
                                  <span className="text-gray-500">Reference: </span>
                                  <span className="font-medium">{test.reference_range}</span>
                                </div>
                              )}
                            </div>
                          </div>
                          <span className={`px-3 py-1 rounded-full text-xs font-medium ${getStatusColor(test.status)}`}>
                            {test.status || 'normal'}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      {labResults.length === 0 && (
        <div className="bg-white rounded-xl shadow-md p-12 text-center">
          <div className="text-6xl mb-4">🧪</div>
          <h3 className="text-xl font-semibold text-gray-800 mb-2">No Lab Results Yet</h3>
          <p className="text-gray-500 mb-6">Add your first lab test results to start tracking</p>
          <button
            onClick={() => setShowAddForm(true)}
            className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            Add Lab Result
          </button>
        </div>
      )}

      {showAddForm && (
        <AddLabResultModal
          formData={formData}
          setFormData={setFormData}
          uploadFile={uploadFile}
          onFileChange={handleFileChange}
          onAddTest={handleAddTest}
          onRemoveTest={handleRemoveTest}
          onTestChange={handleTestChange}
          onSubmit={handleSubmit}
          onClose={() => {
            setShowAddForm(false);
            setUploadFile(null);
          }}
        />
      )}
    </div>
  );
};

const AddLabResultModal = ({ 
  formData, 
  setFormData, 
  uploadFile, 
  onFileChange, 
  onAddTest, 
  onRemoveTest, 
  onTestChange, 
  onSubmit, 
  onClose 
}) => (
  <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 overflow-y-auto">
    <div className="bg-white rounded-xl shadow-2xl p-8 max-w-3xl w-full mx-4 my-8 max-h-[90vh] overflow-y-auto">
      <h3 className="text-2xl font-bold mb-6 text-gray-800">Add Lab Result</h3>
      
      <div className="space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Test Date *</label>
            <input
              type="date"
              value={formData.test_date}
              onChange={(e) => setFormData({...formData, test_date: e.target.value})}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Lab Name *</label>
            <input
              type="text"
              value={formData.lab_name}
              onChange={(e) => setFormData({...formData, lab_name: e.target.value})}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="Enter lab name"
              required
            />
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Upload Report (Optional)</label>
          <div className="border-2 border-dashed border-gray-300 rounded-lg p-4 text-center hover:border-blue-400 transition-colors cursor-pointer">
            <input
              type="file"
              onChange={onFileChange}
              accept=".pdf,.jpg,.jpeg,.png"
              className="hidden"
              id="lab-report-upload"
            />
            <label htmlFor="lab-report-upload" className="cursor-pointer">
              {uploadFile ? (
                <div className="text-green-600">
                  <div className="text-2xl mb-2">✓</div>
                  <p className="font-medium">{uploadFile.name}</p>
                  <p className="text-xs text-gray-500 mt-1">
                    {(uploadFile.size / (1024 * 1024)).toFixed(2)} MB
                  </p>
                </div>
              ) : (
                <div className="text-gray-600">
                  <div className="text-3xl mb-2">📄</div>
                  <p>Click to upload report</p>
                  <p className="text-xs text-gray-500 mt-1">PDF, JPG, PNG up to 10MB</p>
                </div>
              )}
            </label>
          </div>
        </div>

        <div>
          <div className="flex justify-between items-center mb-4">
            <label className="block text-sm font-medium text-gray-700">Test Results *</label>
            <button
              onClick={onAddTest}
              className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 text-sm"
            >
              + Add Test
            </button>
          </div>

          <div className="space-y-4 max-h-96 overflow-y-auto">
            {formData.tests.map((test, index) => (
              <div key={index} className="p-4 bg-gray-50 rounded-lg space-y-3">
                <div className="flex justify-between items-center">
                  <span className="font-medium text-gray-700">Test {index + 1}</span>
                  {formData.tests.length > 1 && (
                    <button
                      onClick={() => onRemoveTest(index)}
                      className="text-red-600 hover:text-red-700 text-sm"
                    >
                      Remove
                    </button>
                  )}
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <input
                    type="text"
                    value={test.test_name}
                    onChange={(e) => onTestChange(index, 'test_name', e.target.value)}
                    placeholder="Test Name"
                    className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                    required
                  />
                  <input
                    type="text"
                    value={test.result}
                    onChange={(e) => onTestChange(index, 'result', e.target.value)}
                    placeholder="Result"
                    className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                    required
                  />
                  <input
                    type="text"
                    value={test.unit}
                    onChange={(e) => onTestChange(index, 'unit', e.target.value)}
                    placeholder="Unit (e.g., mg/dL)"
                    className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  />
                  <input
                    type="text"
                    value={test.reference_range}
                    onChange={(e) => onTestChange(index, 'reference_range', e.target.value)}
                    placeholder="Reference Range"
                    className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  />
                  <select
                    value={test.status}
                    onChange={(e) => onTestChange(index, 'status', e.target.value)}
                    className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="normal">Normal</option>
                    <option value="abnormal">Abnormal</option>
                    <option value="borderline">Borderline</option>
                  </select>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="flex space-x-3 pt-4 border-t">
          <button
            onClick={onClose}
            className="flex-1 px-4 py-3 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={onSubmit}
            className="flex-1 px-4 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            Add Lab Result
          </button>
        </div>
      </div>
    </div>
  </div>
);

export default LabResultsPage;