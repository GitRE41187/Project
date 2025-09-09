import React from 'react';
import Sidebar from './Sidebar';
import Header from './Header';
import MainContent from './MainContent';
import FloatingActionButton from './FloatingActionButton';

const DashboardLayout = () => {
  return (
    <div className="dashboard-layout">
      <Sidebar />
      <div className="dashboard-main">
        <Header />
        <MainContent />
        <FloatingActionButton />
      </div>
    </div>
  );
};

export default DashboardLayout;
