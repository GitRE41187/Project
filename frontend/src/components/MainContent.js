import React, { useState, useEffect } from 'react';
import { Bell, Mail, Settings, ChevronDown } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import DashboardCards from './DashboardCards';

const MainContent = () => {
  const { user } = useAuth();
  const [stats, setStats] = useState({
    totalUploads: 0,
    activeBookings: 0,
    completedBookings: 0,
    totalBookings: 0
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async () => {
    try {
      const [uploadsRes, bookingsRes] = await Promise.all([
        axios.get('/api/uploads/my-uploads'),
        axios.get('/api/queue/my-bookings')
      ]);

      const uploads = uploadsRes.data.uploads || [];
      const bookings = bookingsRes.data.bookings || [];
      
      setStats({
        totalUploads: uploads.length,
        activeBookings: bookings.filter(b => b.status === 'active').length,
        completedBookings: bookings.filter(b => b.status === 'done').length,
        totalBookings: bookings.length
      });
    } catch (error) {
      console.error('Error fetching dashboard data:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="main-content">
      {/* Welcome Section */}
      <div className="welcome-section">
        <h1 className="welcome-title">Welcome back, {user?.username || 'User'}!</h1>
        <div className="welcome-subtitle">
          <Bell className="bell-icon" />
          <span>You have {stats.activeBookings} active bookings and {stats.totalUploads} uploads</span>
        </div>
      </div>

      {/* Action Buttons */}
      <div className="action-buttons">
        <button className="btn btn-secondary">
          <Mail className="btn-icon" />
          Messages
        </button>
        <button className="btn btn-primary">
          <Settings className="btn-icon" />
          Settings
        </button>
      </div>

      {/* Application Selector */}
      <div className="app-selector">
        <button className="app-dropdown">
          ACME Corp. Backend App
          <ChevronDown className="dropdown-icon" />
        </button>
      </div>

      {/* Tab Navigation */}
      <div className="tab-navigation">
        <button className="tab active">Home</button>
        <button className="tab">Budget</button>
        <button className="tab">Team</button>
      </div>

      {/* Dashboard Cards */}
      <DashboardCards stats={stats} />

      {/* Github Issues Summary */}
      <div className="github-section">
        <h2 className="section-title">Github Issues Summary</h2>
        <div className="github-content">
          <div className="github-headers">
            <h3 className="github-subtitle">New vs. Closed</h3>
            <h3 className="github-subtitle">Overview</h3>
          </div>
          <div className="timeframe-selector">
            <button className="timeframe-btn">Last Week</button>
            <button className="timeframe-btn active">This Week</button>
          </div>
          <div className="chart-placeholder">
            <div className="chart-line">
              <div className="chart-point" style={{left: '10%', top: '60%'}}></div>
              <div className="chart-point" style={{left: '30%', top: '50%'}}></div>
              <div className="chart-point" style={{left: '50%', top: '40%'}}></div>
              <div className="chart-point" style={{left: '70%', top: '45%'}}></div>
              <div className="chart-point" style={{left: '90%', top: '35%'}}></div>
            </div>
            <div className="chart-data">
              <span>45</span>
              <span>43</span>
              <span>42</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default MainContent;
