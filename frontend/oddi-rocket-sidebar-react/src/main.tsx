import React from 'react';
import ReactDOM from 'react-dom/client';
import Sidebar from './Sidebar';
import './sidebar.css';

function mountSidebar() {
  let root = document.getElementById('oddi-react-sidebar-root');

  if (!root) {
    root = document.createElement('div');
    root.id = 'oddi-react-sidebar-root';
    document.body.appendChild(root);
  }

  ReactDOM.createRoot(root).render(
    <React.StrictMode>
      <Sidebar />
    </React.StrictMode>
  );
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', mountSidebar);
} else {
  mountSidebar();
}