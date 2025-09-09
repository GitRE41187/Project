import React from 'react';
import { 
  Menu, 
  Flag, 
  Maximize2, 
  Search, 
  Bookmark, 
  Mail,
  Bell
} from 'lucide-react';

const Header = () => {
  return (
    <header className="header">
      <div className="header-left">
        <Menu className="header-icon" />
      </div>
      <div className="header-right">
        <div className="header-icon-group">
          <Flag className="header-icon" />
          <Maximize2 className="header-icon" />
          <Search className="header-icon" />
          <Bookmark className="header-icon" />
          <div className="notification-badge">
            <Mail className="header-icon" />
            <span className="badge">5</span>
          </div>
        </div>
      </div>
    </header>
  );
};

export default Header;
