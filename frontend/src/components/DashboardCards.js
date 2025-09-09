import React from 'react';
import { MoreVertical } from 'lucide-react';

const DashboardCards = ({ stats = {} }) => {
  const cards = [
    {
      title: 'Uploads',
      number: stats.totalUploads || '0',
      label: 'Total Files',
      color: 'blue',
      subtext: `Active: ${stats.activeBookings || 0}`
    },
    {
      title: 'Bookings',
      number: stats.totalBookings || '0',
      label: 'Total Slots',
      color: 'red',
      subtext: `Completed: ${stats.completedBookings || 0}`
    },
    {
      title: 'Active',
      number: stats.activeBookings || '0',
      label: 'Current',
      color: 'orange',
      subtext: 'Running now'
    },
    {
      title: 'Completed',
      number: stats.completedBookings || '0',
      label: 'Finished',
      color: 'green',
      subtext: 'All time'
    }
  ];

  return (
    <div className="dashboard-cards">
      {cards.map((card, index) => (
        <div key={index} className="dashboard-card">
          <div className="card-header">
            <h3 className="card-title">{card.title}</h3>
            <MoreVertical className="card-menu" />
          </div>
          <div className="card-content">
            <div className={`card-number ${card.color}`}>{card.number}</div>
            <div className={`card-label ${card.color}`}>{card.label}</div>
            <div className="card-subtext">{card.subtext}</div>
          </div>
        </div>
      ))}
    </div>
  );
};

export default DashboardCards;
