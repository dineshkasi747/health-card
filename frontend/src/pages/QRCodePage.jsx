import React, { useState, useEffect } from 'react';

// ============================================================================
// QR CODE PAGE - Emergency QR Code Display
// ============================================================================
const QRCodePage = ({ authService }) => {
  const [patientData, setPatientData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [downloaded, setDownloaded] = useState(false);

  useEffect(() => {
    fetchQRCode();
  }, []);

  const fetchQRCode = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await authService.get('/patients/me');
      const result = await response.json();
      
      if (result.status === 'success') {
        setPatientData(result.data);
      } else {
        setError(result.message || 'Failed to load QR code');
      }
    } catch (err) {
      console.error('Error fetching QR code:', err);
      setError('Unable to connect to server');
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = async () => {
    if (!patientData?.qr_image_url) return;

    try {
      // Fetch the image
      const response = await fetch(patientData.qr_image_url);
      const blob = await response.blob();
      
      // Create download link
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `emergency-qr-code-${Date.now()}.png`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
      
      setDownloaded(true);
      setTimeout(() => setDownloaded(false), 3000);
    } catch (err) {
      console.error('Error downloading QR code:', err);
      alert('Failed to download QR code');
    }
  };

  const handlePrint = () => {
    if (!patientData?.qr_image_url) return;
    
    const printWindow = window.open('', '_blank');
    printWindow.document.write(`
      <!DOCTYPE html>
      <html>
        <head>
          <title>Emergency QR Code</title>
          <style>
            body {
              font-family: Arial, sans-serif;
              display: flex;
              flex-direction: column;
              align-items: center;
              justify-content: center;
              min-height: 100vh;
              margin: 0;
              padding: 20px;
            }
            h1 { color: #1f2937; margin-bottom: 10px; }
            p { color: #6b7280; margin-bottom: 30px; }
            img { 
              max-width: 400px; 
              border: 4px solid #3b82f6;
              border-radius: 12px;
              box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            }
            .footer {
              margin-top: 30px;
              text-align: center;
              color: #9ca3af;
              font-size: 14px;
            }
          </style>
        </head>
        <body>
          <h1>Emergency Medical QR Code</h1>
          <p>Scan this code for emergency medical information</p>
          <img src="${patientData.qr_image_url}" alt="Emergency QR Code" />
          <div class="footer">
            <p>Keep this code accessible for emergency situations</p>
            <p>Generated: ${new Date().toLocaleDateString()}</p>
          </div>
        </body>
      </html>
    `);
    printWindow.document.close();
    printWindow.print();
  };

  const copyQRLink = () => {
    if (!patientData?.qr_token) return;
    
    const link = `${window.location.origin}/emergency/${patientData.qr_token}`;
    navigator.clipboard.writeText(link).then(() => {
      alert('QR link copied to clipboard!');
    }).catch(err => {
      console.error('Failed to copy link:', err);
    });
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
          onClick={fetchQRCode}
          className="mt-4 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Success Message */}
      {downloaded && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4 flex items-center">
          <span className="text-green-600 mr-2">✅</span>
          <p className="text-green-800">QR Code downloaded successfully!</p>
        </div>
      )}

      {/* Main QR Code Card */}
      <div className="bg-white rounded-lg shadow-lg p-8 text-center">
        <div className="mb-6">
          <h3 className="text-2xl font-bold text-gray-900 mb-2">Emergency QR Code</h3>
          <p className="text-gray-600">
            Show this QR code to healthcare providers in emergency situations
          </p>
        </div>

        {patientData?.qr_image_url ? (
          <div className="flex flex-col items-center">
            {/* QR Code Image */}
            <div className="relative group">
              <img
                src={patientData.qr_image_url}
                alt="Emergency QR Code"
                className="w-80 h-80 border-4 border-blue-500 rounded-lg shadow-xl transition-transform group-hover:scale-105"
              />
              <div className="absolute inset-0 bg-blue-500 bg-opacity-0 group-hover:bg-opacity-10 rounded-lg transition-all"></div>
            </div>

            {/* QR Code Info */}
            <div className="mt-6 p-4 bg-blue-50 rounded-lg max-w-md">
              <p className="text-sm text-blue-900">
                <strong>QR Token:</strong> <code className="bg-white px-2 py-1 rounded text-xs">{patientData.qr_token}</code>
              </p>
            </div>

            {/* Action Buttons */}
            <div className="mt-8 flex flex-wrap justify-center gap-4">
              <button
                onClick={handleDownload}
                className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 flex items-center gap-2 transition-colors shadow-md hover:shadow-lg"
              >
                <span>📥</span>
                Download QR Code
              </button>

              <button
                onClick={handlePrint}
                className="px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 flex items-center gap-2 transition-colors shadow-md hover:shadow-lg"
              >
                <span>🖨️</span>
                Print QR Code
              </button>

              <button
                onClick={copyQRLink}
                className="px-6 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700 flex items-center gap-2 transition-colors shadow-md hover:shadow-lg"
              >
                <span>🔗</span>
                Copy Link
              </button>
            </div>
          </div>
        ) : (
          <div className="w-80 h-80 mx-auto bg-gray-200 rounded-lg flex items-center justify-center">
            <div className="text-center">
              <span className="text-gray-400 text-4xl block mb-2">⚠️</span>
              <span className="text-gray-500">QR Code not available</span>
            </div>
          </div>
        )}
      </div>

      {/* Information Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* What's Included Card */}
        <div className="bg-white rounded-lg shadow p-6">
          <h4 className="font-semibold text-lg mb-4 flex items-center">
            <span className="text-2xl mr-2">ℹ️</span>
            What's Included
          </h4>
          <ul className="space-y-2 text-sm text-gray-700">
            <li className="flex items-start">
              <span className="text-green-600 mr-2">✓</span>
              <span>Basic personal information</span>
            </li>
            <li className="flex items-start">
              <span className="text-green-600 mr-2">✓</span>
              <span>Blood group</span>
            </li>
            <li className="flex items-start">
              <span className="text-green-600 mr-2">✓</span>
              <span>Known allergies</span>
            </li>
            <li className="flex items-start">
              <span className="text-green-600 mr-2">✓</span>
              <span>Chronic conditions</span>
            </li>
            <li className="flex items-start">
              <span className="text-green-600 mr-2">✓</span>
              <span>Emergency contact details</span>
            </li>
          </ul>
        </div>

        {/* How to Use Card */}
        <div className="bg-white rounded-lg shadow p-6">
          <h4 className="font-semibold text-lg mb-4 flex items-center">
            <span className="text-2xl mr-2">💡</span>
            How to Use
          </h4>
          <ol className="space-y-2 text-sm text-gray-700 list-decimal list-inside">
            <li>Keep a printed copy in your wallet</li>
            <li>Save the QR code on your phone's lock screen</li>
            <li>Share with family members</li>
            <li>Medical staff can scan it instantly in emergencies</li>
            <li>Update your profile to keep info current</li>
          </ol>
        </div>
      </div>

      {/* Security Notice */}
      <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-6">
        <div className="flex items-start">
          <span className="text-yellow-600 text-2xl mr-3">🔒</span>
          <div>
            <h4 className="font-semibold text-yellow-900 mb-2">Privacy & Security</h4>
            <p className="text-sm text-yellow-800">
              This QR code provides access to <strong>emergency information only</strong>. 
              Complete medical records are not accessible through this code. Only critical 
              information needed for emergency treatment is shared.
            </p>
          </div>
        </div>
      </div>

      {/* Emergency Access Info */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
        <div className="flex items-start">
          <span className="text-blue-600 text-2xl mr-3">🚑</span>
          <div>
            <h4 className="font-semibold text-blue-900 mb-2">Emergency Access</h4>
            <p className="text-sm text-blue-800 mb-3">
              Healthcare providers can access your emergency information by scanning this QR code 
              or visiting the emergency link. All emergency accesses are logged for your security.
            </p>
            {patientData?.qr_token && (
              <p className="text-xs text-blue-700 bg-white p-2 rounded font-mono break-all">
                Emergency Link: {window.location.origin}/emergency/{patientData.qr_token}
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

// ============================================================================
// DEMO WRAPPER
// ============================================================================
export default function QRCodePageDemo() {
  const mockAuthService = {
    get: async (endpoint) => {
      await new Promise(resolve => setTimeout(resolve, 800));
      return {
        json: async () => ({
          status: 'success',
          data: {
            qr_token: 'abc123-def456-ghi789',
            qr_image_url: 'https://api.qrserver.com/v1/create-qr-code/?size=400x400&data=https://example.com/emergency/abc123'
          }
        })
      };
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-6xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Emergency QR Code</h1>
          <p className="text-gray-600 mt-2">Your quick access medical information for emergencies</p>
        </div>
        <QRCodePage authService={mockAuthService} />
      </div>
    </div>
  );
}