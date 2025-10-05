import React, { useState, useEffect } from 'react';
import { toast } from 'react-toastify';
import axios from 'axios';
import { useDropzone } from 'react-dropzone';
import PageLayout from '../components/PageLayout';
import RobotCarSelector from '../components/RobotCarSelector';
import { 
  Upload, 
  Play, 
  Square, 
  RotateCcw, 
  FileCode, 
  CheckCircle,
  AlertCircle,
  Clock,
  Trash2,
  Camera,
  LogIn,
  Bot,
  Zap
} from 'lucide-react';

const Control = () => {
  const [uploads, setUploads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [executionStatus, setExecutionStatus] = useState(null);
  const [hasActiveBooking, setHasActiveBooking] = useState(false);
  const [cameraStatus, setCameraStatus] = useState(null);
  const [checkingIn, setCheckingIn] = useState(false);
  const [selectedCar, setSelectedCar] = useState(null);

  useEffect(() => {
    fetchUploads();
    checkExecutionStatus();
    checkCameraStatus();
    checkSelectedCar();
  }, []);

  const fetchUploads = async () => {
    try {
      const response = await axios.get('/api/uploads/my-uploads');
      setUploads(response.data.uploads);
    } catch (error) {
      console.error('Error fetching uploads:', error);
      toast.error('Failed to load uploads');
    } finally {
      setLoading(false);
    }
  };

  const checkExecutionStatus = async () => {
    try {
      const response = await axios.get('/api/control/status');
      setExecutionStatus(response.data);
      setHasActiveBooking(response.data.hasActiveBooking);
    } catch (error) {
      console.error('Error checking execution status:', error);
    }
  };

  const checkCameraStatus = async () => {
    try {
      const response = await axios.get('/api/control/camera/status');
      setCameraStatus(response.data);
    } catch (error) {
      console.error('Error checking camera status:', error);
    }
  };

  const checkSelectedCar = async () => {
    try {
      const response = await axios.get('/api/robots/my-car');
      if (response.data.hasSelectedCar) {
        setSelectedCar(response.data.selectedCar);
      }
    } catch (error) {
      console.error('Error checking selected car:', error);
    }
  };

  const handleCarSelected = (car) => {
    setSelectedCar(car);
    checkExecutionStatus();
    checkCameraStatus();
  };

  const handleCarReleased = () => {
    setSelectedCar(null);
    checkExecutionStatus();
    checkCameraStatus();
  };

  const handleCheckIn = async () => {
    setCheckingIn(true);
    try {
      const response = await axios.post('/api/control/checkin');
      toast.success(response.data.message);
      await checkExecutionStatus(); // Refresh status
    } catch (error) {
      toast.error(error.response?.data?.error || 'Failed to check in');
    } finally {
      setCheckingIn(false);
    }
  };

  const startCamera = async () => {
    try {
      const response = await axios.post('/api/control/camera/start');
      toast.success(response.data.message);
      await checkCameraStatus();
    } catch (error) {
      toast.error(error.response?.data?.error || 'Failed to start camera');
    }
  };

  const stopCamera = async () => {
    try {
      const response = await axios.post('/api/control/camera/stop');
      toast.success(response.data.message);
      await checkCameraStatus();
    } catch (error) {
      toast.error(error.response?.data?.error || 'Failed to stop camera');
    }
  };

  const onDrop = async (acceptedFiles) => {
    const file = acceptedFiles[0];
    if (!file) return;

    if (!file.name.endsWith('.py')) {
      toast.error('Only Python files (.py) are allowed');
      return;
    }

    setUploading(true);
    const formData = new FormData();
    formData.append('codeFile', file);

    try {
      const response = await axios.post('/api/uploads/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      toast.success(response.data.message);
      fetchUploads();
      
      if (response.data.hasActiveBooking) {
        checkExecutionStatus();
      }
    } catch (error) {
      toast.error(error.response?.data?.error || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'text/x-python': ['.py']
    },
    multiple: false
  });

  const handleRun = async () => {
    if (!hasActiveBooking) {
      toast.error('You need an active booking to run code');
      return;
    }

    try {
      const response = await axios.post('/api/control/run');
      toast.success(response.data.message);
      checkExecutionStatus();
    } catch (error) {
      toast.error(error.response?.data?.error || 'Failed to run code');
    }
  };

  const handleStop = async () => {
    try {
      const response = await axios.post('/api/control/stop');
      toast.success(response.data.message);
      checkExecutionStatus();
    } catch (error) {
      toast.error(error.response?.data?.error || 'Failed to stop code');
    }
  };

  const handleReset = async () => {
    if (!hasActiveBooking) {
      toast.error('You need an active booking to reset the field');
      return;
    }

    try {
      const response = await axios.post('/api/control/reset');
      toast.success(response.data.message);
      checkExecutionStatus();
    } catch (error) {
      toast.error(error.response?.data?.error || 'Failed to reset field');
    }
  };

  const handleDeleteUpload = async (uploadId) => {
    if (!window.confirm('Are you sure you want to delete this upload?')) {
      return;
    }

    try {
      await axios.delete(`/api/uploads/${uploadId}`);
      toast.success('Upload deleted successfully');
      fetchUploads();
    } catch (error) {
      toast.error(error.response?.data?.error || 'Failed to delete upload');
    }
  };

  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  if (loading) {
    return (
      <div className="container py-8">
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        </div>
      </div>
    );
  }

  return (
    <PageLayout 
      title="Control Panel" 
      subtitle="Upload and execute your Python code on the field"
    >

      {/* Robot Car Selection */}
      <RobotCarSelector 
        onCarSelected={handleCarSelected}
        selectedCar={selectedCar}
        onCarReleased={handleCarReleased}
      />

      {/* Status Card */}
      <div className="card mb-8">
        <h3 className="text-lg font-semibold mb-4 flex items-center space-x-2">
          <Zap className="h-5 w-5 text-yellow-400" />
          <span className="glow-text">System Status</span>
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="flex items-center space-x-3">
            {hasActiveBooking ? (
              <CheckCircle className="h-5 w-5 text-green-400" />
            ) : (
              <AlertCircle className="h-5 w-5 text-yellow-400" />
            )}
            <div>
              <p className="text-sm font-medium text-gray-300">Booking Status</p>
              <p className="text-sm text-white">
                {hasActiveBooking ? 'Active' : 'No active booking'}
              </p>
            </div>
          </div>
          
          <div className="flex items-center space-x-3">
            {selectedCar ? (
              <Bot className="h-5 w-5 text-blue-400" />
            ) : (
              <AlertCircle className="h-5 w-5 text-red-400" />
            )}
            <div>
              <p className="text-sm font-medium text-gray-300">Robot Car</p>
              <p className="text-sm text-white">
                {selectedCar ? selectedCar.name : 'Not selected'}
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-3">
            {executionStatus?.executionStatus?.is_running ? (
              <Play className="h-5 w-5 text-green-400" />
            ) : (
              <Square className="h-5 w-5 text-gray-400" />
            )}
            <div>
              <p className="text-sm font-medium text-gray-300">Execution Status</p>
              <p className="text-sm text-white">
                {executionStatus?.executionStatus?.is_running ? 'Running' : 'Stopped'}
              </p>
            </div>
          </div>
          
          <div className="flex items-center space-x-3">
            {cameraStatus?.cameraStatus?.camera_active ? (
              <Camera className="h-5 w-5 text-green-400" />
            ) : (
              <Camera className="h-5 w-5 text-gray-400" />
            )}
            <div>
              <p className="text-sm font-medium text-gray-300">Camera Status</p>
              <p className="text-sm text-white">
                {cameraStatus?.cameraStatus?.camera_active ? 'Active' : 'Inactive'}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Check-in and Camera Controls */}
      <div className="card mb-8">
        <h3 className="text-lg font-semibold mb-4 flex items-center space-x-2">
          <Camera className="h-5 w-5 text-blue-400" />
          <span className="glow-text">Field Access & Camera</span>
        </h3>
        <div className="flex flex-wrap gap-4">
          {!hasActiveBooking && (
            <button
              onClick={handleCheckIn}
              disabled={checkingIn}
              className={`btn flex items-center space-x-2 ${
                checkingIn ? 'btn-secondary' : 'btn-primary'
              }`}
            >
              <LogIn className="h-4 w-4" />
              <span>{checkingIn ? 'Checking In...' : 'Check In'}</span>
            </button>
          )}
          
          {hasActiveBooking && selectedCar && (
            <>
              <button
                onClick={startCamera}
                disabled={cameraStatus?.cameraStatus?.camera_active}
                className={`btn flex items-center space-x-2 ${
                  cameraStatus?.cameraStatus?.camera_active ? 'btn-secondary' : 'btn-success'
                }`}
              >
                <Camera className="h-4 w-4" />
                <span>Start Camera</span>
              </button>
              
              <button
                onClick={stopCamera}
                disabled={!cameraStatus?.cameraStatus?.camera_active}
                className={`btn flex items-center space-x-2 ${
                  !cameraStatus?.cameraStatus?.camera_active ? 'btn-secondary' : 'btn-danger'
                }`}
              >
                <Camera className="h-4 w-4" />
                <span>Stop Camera</span>
              </button>
            </>
          )}
        </div>
        
        {!selectedCar && hasActiveBooking && (
          <div className="mt-4 p-4 bg-yellow-500/10 border border-yellow-500/20 rounded-lg">
            <div className="flex items-center space-x-2">
              <AlertCircle className="h-4 w-4 text-yellow-400" />
              <p className="text-sm text-yellow-300">
                Please select a robot car to access camera controls.
              </p>
            </div>
          </div>
        )}
        
        {hasActiveBooking && selectedCar && cameraStatus?.cameraStatus?.camera_active && (
          <div className="mt-4 p-4 bg-gray-800/50 border border-blue-400/20 rounded-lg">
            <h4 className="text-sm font-medium text-white mb-2 flex items-center space-x-2">
              <Camera className="h-4 w-4 text-green-400" />
              <span>Live Camera Feed - {selectedCar.name}</span>
            </h4>
            <div className="relative">
              <img
                src={cameraStatus.cameraStreamUrl || `http://${selectedCar.ip}:${selectedCar.port}/camera/stream`}
                alt="Live Camera Feed"
                className="w-full max-w-md rounded-lg shadow-lg"
                style={{ maxHeight: '300px' }}
                onError={(e) => {
                  e.target.style.display = 'none';
                }}
              />
              <div className="absolute top-2 right-2 bg-red-500 text-white px-2 py-1 rounded text-xs font-medium animate-pulse">
                LIVE
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Upload Section */}
        <div className="card">
          <h3 className="text-lg font-semibold mb-4 flex items-center space-x-2">
            <Upload className="h-5 w-5 text-blue-400" />
            <span className="glow-text">Upload Python Code</span>
          </h3>
          
          <div
            {...getRootProps()}
            className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all duration-300 ${
              isDragActive
                ? 'border-blue-400 bg-gradient-to-br from-blue-500/10 to-blue-400/20 scale-105'
                : 'border-gray-600 hover:border-blue-400 hover:bg-gradient-to-br hover:from-gray-800/50 hover:to-blue-500/10'
            } ${uploading ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            <input {...getInputProps()} disabled={uploading} />
            <div className="relative">
              <Upload className="h-16 w-16 text-blue-400 mx-auto mb-4 float-animation" />
              <div className="absolute inset-0 rounded-full bg-gradient-to-r from-blue-500/20 to-purple-500/20 animate-pulse"></div>
            </div>
            {uploading ? (
              <div className="space-y-2">
                <p className="text-blue-400 font-medium">Uploading...</p>
                <div className="w-32 h-2 bg-gray-700 rounded-full mx-auto overflow-hidden">
                  <div className="h-full bg-gradient-to-r from-blue-400 to-purple-400 rounded-full animate-pulse"></div>
                </div>
              </div>
            ) : isDragActive ? (
              <div className="space-y-2">
                <p className="text-blue-400 font-medium text-lg">Drop the Python file here...</p>
                <p className="text-sm text-blue-300">Release to upload</p>
              </div>
            ) : (
              <div className="space-y-2">
                <p className="text-white font-medium text-lg">
                  Drag & drop a Python file here
                </p>
                <p className="text-gray-400">or click to select a file</p>
                <p className="text-xs text-gray-500 bg-gray-800/50 px-3 py-1 rounded-full inline-block">
                  Only .py files are allowed
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Control Buttons */}
        <div className="card">
          <h3 className="text-lg font-semibold mb-4 flex items-center space-x-2">
            <Zap className="h-5 w-5 text-yellow-400" />
            <span className="glow-text">Field Control</span>
          </h3>
          <div className="space-y-4">
            <button
              onClick={handleRun}
              disabled={!hasActiveBooking || !selectedCar || uploading}
              className="btn btn-success w-full flex items-center justify-center space-x-2"
            >
              <Play className="h-4 w-4" />
              <span>Run Code</span>
            </button>
            
            <button
              onClick={handleStop}
              disabled={!executionStatus?.executionStatus?.is_running}
              className="btn btn-danger w-full flex items-center justify-center space-x-2"
            >
              <Square className="h-4 w-4" />
              <span>Stop Code</span>
            </button>
            
            <button
              onClick={handleReset}
              disabled={!hasActiveBooking || !selectedCar}
              className="btn btn-warning w-full flex items-center justify-center space-x-2"
            >
              <RotateCcw className="h-4 w-4" />
              <span>Reset Field</span>
            </button>
          </div>
          
          {!hasActiveBooking && (
            <div className="mt-4 p-3 bg-yellow-500/10 border border-yellow-500/20 rounded-lg">
              <div className="flex items-center space-x-2">
                <AlertCircle className="h-4 w-4 text-yellow-400" />
                <p className="text-sm text-yellow-300">
                  You need an active booking to control the field. Book a slot first.
                </p>
              </div>
            </div>
          )}
          
          {hasActiveBooking && !selectedCar && (
            <div className="mt-4 p-3 bg-blue-500/10 border border-blue-500/20 rounded-lg">
              <div className="flex items-center space-x-2">
                <Bot className="h-4 w-4 text-blue-400" />
                <p className="text-sm text-blue-300">
                  Please select a robot car to control the field.
                </p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Uploads List */}
      <div className="card mt-8">
        <h3 className="text-lg font-semibold mb-4 flex items-center space-x-2">
          <FileCode className="h-5 w-5 text-blue-400" />
          <span className="glow-text">Your Uploads</span>
        </h3>
        {uploads.length > 0 ? (
          <div className="space-y-3">
            {uploads.map((upload) => (
              <div key={upload.id} className="flex items-center justify-between p-4 bg-gray-800/50 border border-gray-700 rounded-lg hover:border-blue-400/30 transition-all">
                <div className="flex items-center space-x-3">
                  <FileCode className="h-5 w-5 text-blue-400" />
                  <div>
                    <p className="text-sm font-medium text-white">
                      {upload.original_filename}
                    </p>
                    <p className="text-xs text-gray-400">
                      {formatFileSize(upload.file_size)} • {new Date(upload.uploaded_at).toLocaleDateString()}
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => handleDeleteUpload(upload.id)}
                  className="text-red-400 hover:text-red-300 transition-colors"
                  title="Delete upload"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-8">
            <FileCode className="h-12 w-12 text-gray-400 mx-auto mb-4" />
            <p className="text-gray-400">No uploads yet. Upload your first Python file to get started.</p>
          </div>
        )}
      </div>
    </PageLayout>
  );
};

export default Control;
