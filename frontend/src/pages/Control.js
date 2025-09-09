import React, { useState, useEffect } from 'react';
import { toast } from 'react-toastify';
import axios from 'axios';
import { useDropzone } from 'react-dropzone';
import PageLayout from '../components/PageLayout';
import { 
  Upload, 
  Play, 
  Square, 
  RotateCcw, 
  FileCode, 
  CheckCircle,
  AlertCircle,
  Clock,
  Trash2
} from 'lucide-react';

const Control = () => {
  const [uploads, setUploads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [executionStatus, setExecutionStatus] = useState(null);
  const [hasActiveBooking, setHasActiveBooking] = useState(false);

  useEffect(() => {
    fetchUploads();
    checkExecutionStatus();
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

      {/* Status Card */}
      <div className="card mb-8">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Current Status</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="flex items-center space-x-3">
            {hasActiveBooking ? (
              <CheckCircle className="h-5 w-5 text-green-500" />
            ) : (
              <AlertCircle className="h-5 w-5 text-yellow-500" />
            )}
            <div>
              <p className="text-sm font-medium text-gray-600">Booking Status</p>
              <p className="text-sm text-gray-900">
                {hasActiveBooking ? 'Active' : 'No active booking'}
              </p>
            </div>
          </div>
          <div className="flex items-center space-x-3">
            {executionStatus?.executionStatus?.is_running ? (
              <Play className="h-5 w-5 text-green-500" />
            ) : (
              <Square className="h-5 w-5 text-gray-500" />
            )}
            <div>
              <p className="text-sm font-medium text-gray-600">Execution Status</p>
              <p className="text-sm text-gray-900">
                {executionStatus?.executionStatus?.is_running ? 'Running' : 'Stopped'}
              </p>
            </div>
          </div>
          <div className="flex items-center space-x-3">
            <FileCode className="h-5 w-5 text-blue-500" />
            <div>
              <p className="text-sm font-medium text-gray-600">Total Uploads</p>
              <p className="text-sm text-gray-900">{uploads.length}</p>
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Upload Section */}
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Upload Python Code</h3>
          
          <div
            {...getRootProps()}
            className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all duration-300 ${
              isDragActive
                ? 'border-blue-500 bg-gradient-to-br from-blue-50 to-blue-100 scale-105'
                : 'border-gray-300 hover:border-blue-400 hover:bg-gradient-to-br hover:from-gray-50 hover:to-blue-50'
            } ${uploading ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            <input {...getInputProps()} disabled={uploading} />
            <div className="relative">
              <Upload className="h-16 w-16 text-gray-400 mx-auto mb-4 float-animation" />
              <div className="absolute inset-0 rounded-full bg-gradient-to-r from-blue-500/20 to-purple-500/20 animate-pulse"></div>
            </div>
            {uploading ? (
              <div className="space-y-2">
                <p className="text-gray-600 font-medium">Uploading...</p>
                <div className="w-32 h-2 bg-gray-200 rounded-full mx-auto overflow-hidden">
                  <div className="h-full bg-gradient-to-r from-blue-500 to-purple-500 rounded-full animate-pulse"></div>
                </div>
              </div>
            ) : isDragActive ? (
              <div className="space-y-2">
                <p className="text-blue-600 font-medium text-lg">Drop the Python file here...</p>
                <p className="text-sm text-blue-500">Release to upload</p>
              </div>
            ) : (
              <div className="space-y-2">
                <p className="text-gray-700 font-medium text-lg">
                  Drag & drop a Python file here
                </p>
                <p className="text-gray-500">or click to select a file</p>
                <p className="text-xs text-gray-400 bg-gray-100 px-3 py-1 rounded-full inline-block">
                  Only .py files are allowed
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Control Buttons */}
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Field Control</h3>
          <div className="space-y-4">
            <button
              onClick={handleRun}
              disabled={!hasActiveBooking || uploading}
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
              disabled={!hasActiveBooking}
              className="btn btn-warning w-full flex items-center justify-center space-x-2"
            >
              <RotateCcw className="h-4 w-4" />
              <span>Reset Field</span>
            </button>
          </div>
          
          {!hasActiveBooking && (
            <div className="mt-4 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
              <div className="flex items-center space-x-2">
                <AlertCircle className="h-4 w-4 text-yellow-600" />
                <p className="text-sm text-yellow-800">
                  You need an active booking to control the field. Book a slot first.
                </p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Uploads List */}
      <div className="card mt-8">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Your Uploads</h3>
        {uploads.length > 0 ? (
          <div className="space-y-3">
            {uploads.map((upload) => (
              <div key={upload.id} className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                <div className="flex items-center space-x-3">
                  <FileCode className="h-5 w-5 text-gray-500" />
                  <div>
                    <p className="text-sm font-medium text-gray-900">
                      {upload.original_filename}
                    </p>
                    <p className="text-xs text-gray-500">
                      {formatFileSize(upload.file_size)} • {new Date(upload.uploaded_at).toLocaleDateString()}
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => handleDeleteUpload(upload.id)}
                  className="text-red-600 hover:text-red-800"
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
            <p className="text-gray-500">No uploads yet. Upload your first Python file to get started.</p>
          </div>
        )}
      </div>
    </PageLayout>
  );
};

export default Control;
