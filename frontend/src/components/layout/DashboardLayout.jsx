import { useState } from 'react';
import { Outlet } from 'react-router-dom';
import Navbar from './Navbar';
import Sidebar from './Sidebar';

const DashboardLayout = () => {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="app-shell dashboard-shell">
      <Navbar onToggleSidebar={() => setSidebarOpen((open) => !open)} />
      <div className="app-body">
        <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />
        <main className="main-content">
          <div className="content-wrap"><Outlet /></div>
          <footer className="app-footer">Government Post Graduate College Mardan · Computer Science Department</footer>
        </main>
      </div>
    </div>
  );
};

export default DashboardLayout;
