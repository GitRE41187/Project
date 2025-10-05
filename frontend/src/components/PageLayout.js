import React from 'react';
import Sidebar from './Sidebar';
import Header from './Header';
import FloatingActionButton from './FloatingActionButton';
import '../components/Dashboard.css';

const PageLayout = ({ children, title, subtitle, showFAB = true }) => {
  return (
    <div className="dashboard-layout">
      <Sidebar />
      <div className="dashboard-main">
        <Header />
        <div className="main-content">
          {/* Page Header */}
          <div className="welcome-section">
            <h1 className="welcome-title science-lab-gradient">{title}</h1>
            {subtitle && (
              <div className="welcome-subtitle">
                <span className="text-gray-300">{subtitle}</span>
              </div>
            )}
          </div>
          
          {/* Page Content */}
          {children}
        </div>
        {showFAB && <FloatingActionButton />}
      </div>
    </div>
  );
};

export default PageLayout;
