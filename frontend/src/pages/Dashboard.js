import React from 'react';
import PageLayout from '../components/PageLayout';
import RobotCarSelector from '../components/RobotCarSelector';
import '../components/Dashboard.css';

const Dashboard = () => {
  const handleCarSelected = (car) => {
    console.log('Car selected:', car);
  };

  const handleCarReleased = () => {
    console.log('Car released');
  };

  return (
    <PageLayout title="Dashboard" subtitle="Welcome to your control center">
      <div className="space-y-6">
        <RobotCarSelector 
          onCarSelected={handleCarSelected}
          onCarReleased={handleCarReleased}
        />
      </div>
    </PageLayout>
  );
};

export default Dashboard;
