import React, { useState, useEffect } from 'react';
import { toast } from 'react-toastify';
import axios from 'axios';
import { 
  Bot, 
  CheckCircle, 
  AlertCircle, 
  Wifi, 
  WifiOff,
  Loader2,
  Zap
} from 'lucide-react';

const RobotCarSelector = ({ onCarSelected, selectedCar, onCarReleased }) => {
  const [availableCars, setAvailableCars] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selecting, setSelecting] = useState(false);

  useEffect(() => {
    fetchAvailableCars();
    
    // Set up polling for robot status updates every 30 seconds
    const interval = setInterval(() => {
      fetchAvailableCars();
    }, 30000);
    
    return () => {
      clearInterval(interval);
    };
  }, []);

  const fetchAvailableCars = async () => {
    try {
      console.log('🔍 Fetching available cars...');
      console.log('🔐 Auth token:', localStorage.getItem('token') ? 'Present' : 'Missing');
      console.log('🌐 API URL:', '/api/robots/available');
      
      const response = await axios.get('/api/robots/available');
      
      console.log('✅ API Response:', response.data);
      console.log('📊 Available cars count:', response.data.availableCars?.length || 0);
      console.log('🤖 Available cars:', response.data.availableCars);
      
      setAvailableCars(response.data.availableCars || []);
      
      if (response.data.availableCars?.length === 0) {
        console.log('⚠️ No available cars found. Possible reasons:');
        console.log('   - No robots connected to server');
        console.log('   - All robots are in use');
        console.log('   - Robots need to register first');
      }
    } catch (error) {
      console.error('❌ Error fetching available cars:', error);
      console.error('📊 Error details:', {
        status: error.response?.status,
        statusText: error.response?.statusText,
        data: error.response?.data,
        message: error.message
      });
      
      if (error.response?.status === 401) {
        toast.error('Authentication required. Please log in.');
      } else if (error.response?.status === 403) {
        toast.error('Access denied. Please check your permissions.');
      } else {
        toast.error('Failed to load available robot cars');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleSelectCar = async (carId) => {
    setSelecting(true);
    try {
      const response = await axios.post('/api/robots/select', { carId });
      toast.success(`Selected robot car: ${response.data.selectedCar.name}`);
      onCarSelected(response.data.selectedCar);
    } catch (error) {
      toast.error(error.response?.data?.error || 'Failed to select robot car');
    } finally {
      setSelecting(false);
    }
  };

  const handleReleaseCar = async () => {
    if (!selectedCar) return;
    
    try {
      await axios.post('/api/robots/release', { carId: selectedCar.id });
      toast.success('Robot car released');
      onCarReleased();
    } catch (error) {
      toast.error(error.response?.data?.error || 'Failed to release robot car');
    }
  };

  const getStatusIcon = (car) => {
    const now = new Date();
    const lastSeen = new Date(car.lastSeen);
    const timeDiff = now - lastSeen;
    
    if (timeDiff > 5 * 60 * 1000) { // 5 minutes
      return <WifiOff className="h-4 w-4 text-red-400" />;
    }
    return <Wifi className="h-4 w-4 text-green-400" />;
  };

  const getStatusText = (car) => {
    const now = new Date();
    const lastSeen = new Date(car.lastSeen);
    const timeDiff = now - lastSeen;
    
    if (timeDiff > 5 * 60 * 1000) {
      return 'Offline';
    }
    return 'Online';
  };

  const getConnectionType = (car) => {
    return car.connectionType || 'HTTP';
  };

  const handleDebugRefresh = () => {
    console.log('🔄 Manual refresh triggered');
    setLoading(true);
    fetchAvailableCars();
  };

  if (loading) {
    return (
      <div className="card">
        <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center space-x-2">
          <Bot className="h-5 w-5 text-blue-400" />
          <span>Robot Car Selection</span>
        </h3>
        <div className="flex items-center justify-center py-8">
          <Loader2 className="h-8 w-8 animate-spin text-blue-400" />
          <span className="ml-2 text-gray-400">Loading robot cars...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold flex items-center space-x-2">
          <Bot className="h-5 w-5 text-blue-400 floating-animation" />
          <span className="glow-text">Robot Car Selection</span>
        </h3>
        
        {/* Debug Panel */}
        <div className="flex items-center space-x-2">
          <button
            onClick={handleDebugRefresh}
            className="px-3 py-1 text-xs bg-gray-700 hover:bg-gray-600 text-white rounded transition-colors"
            title="Debug: Refresh available cars"
          >
            🔄 Debug
          </button>
          <div className="text-xs text-gray-400">
            Cars: {availableCars.length}
          </div>
        </div>
      </div>

      {selectedCar ? (
        <div className="mb-6">
          <div className="robot-card">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center space-x-3">
                <div className="status-indicator status-in-use"></div>
                <div>
                  <h4 className="text-lg font-semibold text-white">{selectedCar.name}</h4>
                  <p className="text-sm text-gray-400">Currently Selected</p>
                </div>
              </div>
              <div className="flex items-center space-x-2">
                <Zap className="h-4 w-4 text-yellow-400" />
                <span className="text-sm text-yellow-400">Active</span>
              </div>
            </div>
            
            <div className="grid grid-cols-2 gap-4 mb-4">
              <div>
                <p className="text-xs text-gray-400 uppercase tracking-wide">IP Address</p>
                <p className="text-sm text-white font-mono">{selectedCar.ip}</p>
              </div>
              <div>
                <p className="text-xs text-gray-400 uppercase tracking-wide">Port</p>
                <p className="text-sm text-white font-mono">{selectedCar.port}</p>
              </div>
            </div>

            <button
              onClick={handleReleaseCar}
              className="btn btn-danger w-full flex items-center justify-center space-x-2"
            >
              <AlertCircle className="h-4 w-4" />
              <span>Release Robot Car</span>
            </button>
          </div>
        </div>
      ) : (
        <div className="mb-6">
          <div className="flex items-center space-x-2 mb-4">
            <AlertCircle className="h-4 w-4 text-yellow-400" />
            <p className="text-sm text-gray-400">
              Please select a robot car to control the field
            </p>
          </div>
        </div>
      )}

      <div className="space-y-3">
        <h4 className="text-sm font-medium text-gray-300 uppercase tracking-wide">
          Available Robot Cars ({availableCars.length})
        </h4>
        
        {availableCars.length > 0 ? (
          <div className="space-y-3">
            {availableCars.map((car) => (
              <div key={car.id} className="robot-card">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <div className="status-indicator status-available"></div>
                    <div>
                      <h5 className="text-white font-medium">{car.name}</h5>
                      <div className="flex items-center space-x-2 text-sm text-gray-400">
                        {getStatusIcon(car)}
                        <span>{getStatusText(car)}</span>
                        <span>•</span>
                        <span className="font-mono">{car.ip}:{car.port}</span>
                        <span>•</span>
                        <span className="text-xs bg-gray-700 px-2 py-1 rounded">
                          {getConnectionType(car)}
                        </span>
                        {car.battery && (
                          <>
                            <span>•</span>
                            <span className="text-xs text-yellow-400">
                              {car.battery}%
                            </span>
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                  
                  <button
                    onClick={() => handleSelectCar(car.id)}
                    disabled={selecting}
                    className="btn btn-primary flex items-center space-x-2"
                  >
                    {selecting ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <CheckCircle className="h-4 w-4" />
                    )}
                    <span>{selecting ? 'Selecting...' : 'Select'}</span>
                  </button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-8">
            <Bot className="h-12 w-12 text-gray-400 mx-auto mb-4" />
            <p className="text-gray-400">No robot cars available</p>
            <p className="text-sm text-gray-500 mt-2">
              Make sure robot cars are connected and registered
            </p>
            
            {/* Debug Information */}
            <div className="mt-6 p-4 bg-gray-800 rounded-lg text-left">
              <h4 className="text-sm font-medium text-yellow-400 mb-2">🔍 Debug Information:</h4>
              <div className="text-xs space-y-1 text-gray-300">
                <div>• Available cars from API: {availableCars.length}</div>
                <div>• Auth token: {localStorage.getItem('token') ? '✅ Present' : '❌ Missing'}</div>
                <div>• API endpoint: /api/robots/available</div>
                <div className="mt-2 text-yellow-300">
                  <strong>Note:</strong> The API returns robots connected to the server with status 'available'
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default RobotCarSelector;

