import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { 
  Home, 
  BarChart3, 
  FileText, 
  DollarSign, 
  GraduationCap, 
  Calendar, 
  MessageCircle,
  Bell,
  User,
  Check,
  Settings,
  LogOut
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';

const Sidebar = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  return (
    <div className="sidebar">
      {/* User Profile Section */}
      <div className="user-profile">
        <div className="profile-info">
          <h3 className="profile-name">{user?.username || 'User'}</h3>
          <p className="profile-email">{user?.email || 'user@example.com'}</p>
        </div>
      </div>

      {/* Navigation Sections */}
      <div className="sidebar-nav">
        {/* DASHBOARDS Section */}
        <div className="nav-section">
          <h4 className="nav-section-title">DASHBOARDS</h4>
          <p className="nav-section-subtitle">Main application sections</p>
          <ul className="nav-list">
            <li 
              className={`nav-item ${location.pathname === '/dashboard' ? 'active' : ''}`}
              onClick={() => navigate('/dashboard')}
            >
              <Check className="nav-icon" />
              <span>Dashboard</span>
            </li>
            <li 
              className={`nav-item ${location.pathname === '/queue' ? 'active' : ''}`}
              onClick={() => navigate('/queue')}
            >
              <Calendar className="nav-icon" />
              <span>Queue</span>
            </li>
            <li 
              className={`nav-item ${location.pathname === '/control' ? 'active' : ''}`}
              onClick={() => navigate('/control')}
            >
              <Settings className="nav-icon" />
              <span>Control</span>
            </li>
            {user?.role === 'admin' && (
              <li 
                className={`nav-item ${location.pathname === '/admin' ? 'active' : ''}`}
                onClick={() => navigate('/admin')}
              >
                <BarChart3 className="nav-icon" />
                <span>Admin</span>
              </li>
            )}
          </ul>
        </div>

        {/* ACTIONS Section */}
        <div className="nav-section">
          <h4 className="nav-section-title">ACTIONS</h4>
          <p className="nav-section-subtitle">Quick actions and settings</p>
          <ul className="nav-list">
            <li className="nav-item" onClick={() => navigate('/queue')}>
              <Calendar className="nav-icon" />
              <div className="nav-item-content">
                <span>Book Slot</span>
                <span className="nav-subtext">Reserve field time</span>
              </div>
            </li>
            <li className="nav-item" onClick={() => navigate('/control')}>
              <Settings className="nav-icon" />
              <div className="nav-item-content">
                <span>Upload Code</span>
                <span className="nav-subtext">Python files</span>
              </div>
            </li>
            <li className="nav-item" onClick={logout}>
              <LogOut className="nav-icon" />
              <span>Logout</span>
            </li>
          </ul>
        </div>
      </div>
    </div>
  );
};

export default Sidebar;

