import React from 'react';
import PageLayout from '../components/PageLayout';
import MainContent from '../components/MainContent';
import '../components/Dashboard.css';

const Dashboard = () => {
  return (
    <PageLayout title="Dashboard" subtitle="Welcome to your control center">
      <MainContent />
    </PageLayout>
  );
};

export default Dashboard;
