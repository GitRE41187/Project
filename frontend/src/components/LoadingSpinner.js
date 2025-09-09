import React from 'react';
import { Loader2 } from 'lucide-react';

const LoadingSpinner = ({ size = 24, className = '' }) => {
  return (
    <div className="flex items-center justify-center min-h-screen">
      <div className="relative">
        <div className="absolute inset-0 rounded-full border-4 border-transparent bg-gradient-to-r from-blue-500 to-purple-500 animate-spin"></div>
        <div className="relative rounded-full border-4 border-white bg-white p-2">
          <Loader2 
            size={size} 
            className={`animate-spin text-blue-600 ${className}`}
          />
        </div>
      </div>
    </div>
  );
};

export default LoadingSpinner;
