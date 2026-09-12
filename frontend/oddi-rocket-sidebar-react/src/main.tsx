import React from 'react';
import ReactDOM from 'react-dom/client';
import MemoryManagement from './app/memory-management-screen/components/MemoryManagement';
import './sidebar.css';

function mountMemory() {
  let root = document.getElementById('oddi-react-memory-root');

  if (!root) {
    root = document.createElement('div');
    root.id = 'oddi-react-memory-root';
    document.body.appendChild(root);
  }

  ReactDOM.createRoot(root).render(
    <React.StrictMode>
      <MemoryManagement />
    </React.StrictMode>
  );
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', mountMemory);
} else {
  mountMemory();
} 