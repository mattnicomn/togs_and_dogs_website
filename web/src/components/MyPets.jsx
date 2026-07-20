import React, { useState, useEffect } from 'react';
import { getSession, signIn, getEffectiveRole } from '../api/auth';
import { getClientPets } from '../api/client';
import UserProfile from './UserProfile';
import { sanitizePetsList } from '../utils/petHelpers';
import '../Portal.css';

const MyPets = () => {
  const [pets, setPets] = useState([]);
  const [loading, setLoading] = useState(false);
  const [session, setSession] = useState(null);
  const [userRole, setUserRole] = useState(null);
  const [loginData, setLoginData] = useState({ email: '', password: '' });
  const [error, setError] = useState(null);
  const [apiError, setApiError] = useState(null);

  useEffect(() => {
    checkSession();
  }, []);

  const checkSession = async () => {
    try {
      setLoading(true);
      const s = await getSession();
      if (s) {
        const role = getEffectiveRole(s);
        if (['owner', 'admin', 'client'].includes(role)) {
          setSession(s);
          setUserRole(role);
          await fetchMyPets();
        } else {
          setError("Access denied. Staff members must use the Staff Portal.");
          setSession(null);
        }
      }
    } catch (e) {
      console.error("No session", e);
    } finally {
      setLoading(false);
    }
  };

  const fetchMyPets = async () => {
    try {
      setLoading(true);
      setApiError(null);
      const data = await getClientPets();
      if (data.message === "No local profile linked") {
        setPets([]);
        setError("Your portal account is not yet linked to a client profile. Please contact support.");
      } else {
        setPets(sanitizePetsList(data.pets || []));
        setError(null);
      }
    } catch (err) {
      console.error("Fetch pets failed", err);
      setApiError(err.message || "Failed to load pets. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  if (!session) {
    return (
      <div className="card login-card" style={{ maxWidth: '400px', margin: '80px auto', padding: '40px' }}>
        <h2 style={{ textAlign: 'center', marginBottom: '12px' }}>Client Login</h2>
        {error && <p style={{ color: 'red', textAlign: 'center', marginBottom: '16px' }}>{error}</p>}
        <p style={{ textAlign: 'center', color: 'var(--text-muted)', marginBottom: '32px' }}>Sign in to view your pets.</p>

        <form onSubmit={async (e) => {
          e.preventDefault();
          try {
            setLoading(true);
            await signIn(loginData.email, loginData.password);
            const s = await getSession();
            const role = getEffectiveRole(s);
            if (['owner', 'admin', 'client'].includes(role)) {
              setSession(s);
              setUserRole(role);
              setError(null);
              // fetch pets will run in a separate step or directly here
              const data = await getClientPets();
              if (data.message === "No local profile linked") {
                setPets([]);
                setError("Your portal account is not yet linked to a client profile. Please contact support.");
              } else {
                setPets(sanitizePetsList(data.pets || []));
              }
            } else {
              setError("Access denied. Staff members must use the Staff Portal.");
            }
          } catch(err) {
            alert(err.message);
          } finally {
            setLoading(false);
          }
        }}>
          <div className="field" style={{ marginBottom: '16px' }}>
            <label>Email Address</label>
            <input
              type="email"
              placeholder="alex@example.com"
              value={loginData.email}
              onChange={e => setLoginData({...loginData, email: e.target.value})}
              required
              autoComplete="email"
            />
          </div>
          <div className="field" style={{ marginBottom: '24px' }}>
            <label>Password</label>
            <input
              type="password"
              placeholder="••••••••"
              value={loginData.password}
              onChange={e => setLoginData({...loginData, password: e.target.value})}
              required
              autoComplete="current-password"
            />
          </div>

          <button type="submit" className="button-primary" style={{ width: '100%', padding: '14px' }} disabled={loading}>
            {loading ? 'Signing in...' : 'Sign In'}
          </button>
        </form>
      </div>
    );
  }

  return (
    <div className="client-portal client-pets-page">
      <div className="portal-header">
        <div>
          <h1>My Pets</h1>
          <p className="subtitle">View your pet details and care profiles.</p>
        </div>
        <div className="portal-header-actions">
          <UserProfile />
        </div>
      </div>

      <div aria-live="polite" style={{ width: '100%' }}>
        {loading ? (
          <div className="card loading-card" style={{ padding: '40px', textAlign: 'center' }}>
            <p>Loading your pets...</p>
          </div>
        ) : apiError ? (
          <div className="card error-card" style={{ padding: '24px', textAlign: 'center' }}>
            <p className="error-text" style={{ color: 'var(--warning-color)', marginBottom: '16px' }}>{apiError}</p>
            <button onClick={fetchMyPets} className="button-secondary" style={{ padding: '8px 16px' }}>
              Retry
            </button>
          </div>
        ) : error ? (
          <div className="card error-card" style={{ padding: '24px', textAlign: 'center' }}>
            <p className="error-text">{error}</p>
          </div>
        ) : pets.length === 0 ? (
          <div className="card empty-bookings-card" style={{ padding: '40px', textAlign: 'center' }}>
            <div className="empty-bookings-icon" style={{ fontSize: '3rem', marginBottom: '16px' }}>🐾</div>
            <h3>No pets on file</h3>
            <p className="empty-bookings-text">We don't have any pet records linked to your account yet.</p>
          </div>
        ) : (
          <ul className="pet-grid" style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
            gap: '20px',
            listStyle: 'none',
            padding: 0,
            margin: 0
          }}>
            {pets.map(pet => (
              <li
                key={pet.pet_id || pet.PK || pet.SK}
                className="pet-card card"
                style={{
                  padding: '24px',
                  backgroundColor: 'var(--card-bg, white)',
                  borderRadius: '12px',
                  boxShadow: 'var(--shadow-soft)',
                  border: '1px solid var(--border-soft)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '12px'
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <h2 style={{ margin: 0, fontSize: '1.5rem', fontFamily: 'var(--serif)' }}>{pet.name}</h2>
                  {pet.is_active === false && (
                    <span className="access-badge status-offline" style={{ fontSize: '10px' }}>Archived</span>
                  )}
                </div>

                <div style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
                  {pet.species && <p style={{ margin: '4px 0' }}><strong>Species:</strong> {pet.species}</p>}
                  {pet.breed && <p style={{ margin: '4px 0' }}><strong>Breed:</strong> {pet.breed}</p>}
                  {pet.age && <p style={{ margin: '4px 0' }}><strong>Age:</strong> {pet.age}</p>}
                </div>

                <hr style={{ border: 0, borderTop: '1px solid var(--border-soft)', margin: '8px 0' }} />

                <div className="pet-notes-section" style={{ fontSize: '0.85rem', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {pet.care_instructions && (
                    <div>
                      <strong>Care Instructions:</strong>
                      <p style={{ margin: '2px 0', color: 'var(--text-muted)' }}>{pet.care_instructions}</p>
                    </div>
                  )}
                  {pet.feeding_notes && (
                    <div>
                      <strong>Feeding Notes:</strong>
                      <p style={{ margin: '2px 0', color: 'var(--text-muted)' }}>{pet.feeding_notes}</p>
                    </div>
                  )}
                  {pet.medication_notes && (
                    <div>
                      <strong>Medication Notes:</strong>
                      <p style={{ margin: '2px 0', color: 'var(--text-muted)' }}>{pet.medication_notes}</p>
                    </div>
                  )}
                  {pet.behavior_notes && (
                    <div>
                      <strong>Behavior Notes:</strong>
                      <p style={{ margin: '2px 0', color: 'var(--text-muted)' }}>{pet.behavior_notes}</p>
                    </div>
                  )}

                  {!pet.care_instructions && !pet.feeding_notes && !pet.medication_notes && !pet.behavior_notes && (
                    <p style={{ fontStyle: 'italic', color: 'var(--text-muted)', margin: 0 }}>No care notes recorded.</p>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
};

export default MyPets;
