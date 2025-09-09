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

      {/* Dashboard Cards */}
      <DashboardCards stats={stats} />

    </div>
  );
};

export default MainContent;
