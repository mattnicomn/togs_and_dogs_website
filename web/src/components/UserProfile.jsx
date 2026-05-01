import React, { useState, useEffect, useRef } from 'react';
import { getSession, getEffectiveRole, signOut } from '../api/auth';

const UserProfile = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [user, setUser] = useState(null);
  const [role, setRole] = useState('unknown');
  const dropdownRef = useRef(null);

  useEffect(() => {
    const loadUser = async () => {
      try {
        const session = await getSession();
        if (session) {
          const payload = session.getIdToken().payload;
          setUser({
            email: payload.email,
            name: payload.name || payload['custom:display_name'] || null,
          });
          setRole(getEffectiveRole(session));
        }
      } catch (err) {
        console.error('Failed to load user session', err);
      }
    };

    loadUser();

    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleLogout = () => {
    signOut();
    window.location.reload(); // Refresh to clear state
  };

  if (!user) return null;

  const displayName = user.name || user.email;
  const initials = displayName.split(' ').map(n => n[0]).join('').toUpperCase().substring(0, 2);

  return (
    <div className="user-profile-container" ref={dropdownRef}>
      <button 
        className="profile-trigger" 
        onClick={() => setIsOpen(!isOpen)}
        aria-haspopup="true"
        aria-expanded={isOpen}
        aria-label="User profile menu"
      >
        <span className="profile-name">{user.name || user.email}</span>
        <div className="profile-avatar">
          {initials}
        </div>
      </button>

      {isOpen && (
        <div className="profile-dropdown card">
          <div className="dropdown-header">
            <div className="user-info">
              <span className="user-name">{user.name || 'User'}</span>
              <span className="user-email">{user.email}</span>
            </div>
            <span className={`role-badge role-${role.toLowerCase()}`}>
              {role.charAt(0).toUpperCase() + role.slice(1)}
            </span>
          </div>
          
          <div className="dropdown-divider"></div>
          
          <div className="dropdown-body">
            <div className="company-info">
              <span className="label">Company</span>
              <span className="value">Tog and Dogs</span>
            </div>
          </div>

          <div className="dropdown-divider"></div>

          <div className="dropdown-footer">
            <button onClick={handleLogout} className="logout-action">
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
                <polyline points="16 17 21 12 16 7"></polyline>
                <line x1="21" y1="12" x2="9" y2="12"></line>
              </svg>
              Sign out
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default UserProfile;
