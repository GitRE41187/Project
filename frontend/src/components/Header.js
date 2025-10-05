import React from 'react';
import { 
  Menu, 
  Cpu, 
  Maximize2, 
  Search, 
  Bookmark, 
  Mail,
  Bell,
  Zap
} from 'lucide-react';

const Header = () => {
  return (
    <header className="header">
      <div className="header-left">
        <Menu className="header-icon" />
      </div>
      <div className="header-right">
        <div className="header-icon-group">
          <Cpu className="header-icon" />
          <Maximize2 className="header-icon" />
          <Search className="header-icon" />
          <Bookmark className="header-icon" />
          <div className="notification-badge">
            <Zap className="header-icon" />
            <span className="badge">Live</span>
          </div>
        </div>
      </div>
    </header>
  );
};

export default Header;
