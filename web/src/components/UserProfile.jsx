import React, { useState, useEffect, useRef } from 'react';
import { getSession, getEffectiveRole, signOut } from '../api/auth';

const UserProfile = ({ staffProfile, externalCurrentUser }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [user, setUser] = useState(null);
  const [role, setRole] = useState('unknown');
  const dropdownRef = useRef(null);

  useEffect(() => {
    const loadUser = async () => {
      try {
        if (externalCurrentUser) {
          setUser(externalCurrentUser);
        }
        
        const session = await getSession();
        if (session) {
          const payload = session.getIdToken().payload;
          if (!externalCurrentUser) {
            setUser({
              email: payload.email,
              sub: payload.sub,
              name: payload.name || payload['custom:display_name'] || null,
            });
          }
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
  }, [externalCurrentUser]);

  const handleLogout = () => {
    signOut();
    window.location.reload(); // Refresh to clear state
  };

  if (!user) return null;

  // Prefer staff profile display name from DynamoDB
  const effectiveDisplayName = staffProfile?.display_name || user.name || user.email;
  const initials = effectiveDisplayName.split(' ').map(n => n[0]).join('').toUpperCase().substring(0, 2);

  // Protection Logic (Sync with backend/AdminDashboard)
  const PROTECTED_SUBS = ["74b86488-1011-7029-bb6d-dad984e1463c"];
  const PROTECTED_EMAILS = ["admin@toganddogs.com"];
  const isProtected = staffProfile && (PROTECTED_SUBS.includes(staffProfile.cognito_sub) || PROTECTED_EMAILS.includes(staffProfile.email));

  return (
    <div className="user-profile-container" ref={dropdownRef}>
      <button 
        className="profile-trigger" 
        onClick={() => setIsOpen(!isOpen)}
        aria-haspopup="true"
        aria-expanded={isOpen}
        aria-label="User profile menu"
      >
        <span className="profile-name">{effectiveDisplayName}</span>
        <div className="profile-avatar">
          {initials}
        </div>
      </button>

      {isOpen && (
        <div className="profile-dropdown card">
          <div className="dropdown-header">
            <div className="user-info">
              <span className="user-name">
                {effectiveDisplayName}
                {isProtected && <span style={{ fontSize: '10px', color: 'var(--accent-teal)', marginLeft: '8px', backgroundColor: 'rgba(0, 188, 212, 0.1)', padding: '2px 6px', borderRadius: '4px', fontWeight: 'bold' }}>PROTECTED</span>}
              </span>
              <div className="user-details" style={{ fontSize: '0.85em', marginTop: '6px', lineHeight: '1.4' }}>
                 <div style={{ color: 'var(--text-secondary)' }}>Login: <span style={{ color: 'var(--text-primary)', fontWeight: '500' }}>{user.email}</span></div>
                 {staffProfile?.email && staffProfile.email !== user.email && (
                   <div style={{ color: 'var(--text-secondary)' }}>Contact: <span style={{ color: 'var(--text-primary)', fontWeight: '500' }}>{staffProfile.email}</span></div>
                 )}
              </div>
            </div>
            <span className={`role-badge role-${role.toLowerCase()}`} style={{ alignSelf: 'flex-start' }}>
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
