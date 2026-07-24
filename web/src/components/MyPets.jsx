import React, { useState, useEffect } from 'react';
import { getSession, signIn, getEffectiveRole } from '../api/auth';
import { getClientPets, updateClientPet } from '../api/client';
import UserProfile from './UserProfile';
import { sanitizePetsList } from '../utils/petHelpers';
import { useBlocker } from 'react-router-dom';
import '../Portal.css';

const MyPets = () => {
  const [pets, setPets] = useState([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [session, setSession] = useState(null);
  const [userRole, setUserRole] = useState(null);
  const [loginData, setLoginData] = useState({ email: '', password: '' });
  const [error, setError] = useState(null);
  const [apiError, setApiError] = useState(null);
  const [notification, setNotification] = useState(null);

  // Edit Mode state
  const [editingPetId, setEditingPetId] = useState(null);
  const [editForm, setEditForm] = useState({
    name: '',
    species: '',
    breed: '',
    age: '',
    care_instructions: '',
    feeding_notes: '',
    medication_notes: '',
    behavior_notes: '',
    health: { vet_name: '', vet_phone: '' }
  });
  const [initialFormValues, setInitialFormValues] = useState(null);
  const [reloadWarning, setReloadWarning] = useState(null);

  const checkIsDirty = (current, initial) => {
    if (!current || !initial) return false;
    if (current.name !== initial.name) return true;
    if (current.species !== initial.species) return true;
    if (current.breed !== initial.breed) return true;
    if (current.age !== initial.age) return true;
    if (current.care_instructions !== initial.care_instructions) return true;
    if (current.feeding_notes !== initial.feeding_notes) return true;
    if (current.medication_notes !== initial.medication_notes) return true;
    if (current.behavior_notes !== initial.behavior_notes) return true;
    if (current.health?.vet_name !== initial.health?.vet_name) return true;
    if (current.health?.vet_phone !== initial.health?.vet_phone) return true;
    return false;
  };

  const isDirty = !!editingPetId && checkIsDirty(editForm, initialFormValues);

  // React Router Navigation Blocker
  const blocker = useBlocker(
    ({ currentLocation, nextLocation }) =>
      isDirty && currentLocation.pathname !== nextLocation.pathname
  );

  useEffect(() => {
    if (blocker.state === "blocked") {
      const proceed = window.confirm("You have unsaved pet changes. Are you sure you want to discard them?");
      if (proceed) {
        blocker.proceed();
      } else {
        blocker.reset();
      }
    }
  }, [blocker, isDirty]);

  // Window beforeunload listener
  useEffect(() => {
    const handleBeforeUnload = (e) => {
      if (isDirty) {
        e.preventDefault();
        e.returnValue = "You have unsaved pet changes. Are you sure you want to discard them?";
        return e.returnValue;
      }
    };
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload);
    };
  }, [isDirty]);

  const showNotification = (message, type = 'info') => {
    setNotification({ message, type });
    setTimeout(() => setNotification(null), 5000);
  };

  const checkSession = async () => {
    try {
      setLoading(true);
      const s = await getSession();
      if (s) {
        const role = getEffectiveRole(s);
        if (['owner', 'admin', 'client'].includes(role)) {
          setSession(s);
          setUserRole(role);
          await fetchMyPets(role);
        } else {
          setError("Access denied. Staff members must use the Staff Portal.");
          setSession(null);
          setLoading(false);
        }
      } else {
        setLoading(false);
      }
    } catch (e) {
      console.error("No session", e);
      setLoading(false);
    }
  };

  const fetchMyPets = async (resolvedRole = null) => {
    try {
      setLoading(true);
      setApiError(null);
      const data = await getClientPets();
      if (data.message === "No local profile linked" || data.linked_profile === false) {
        setPets([]);
        const activeRole = resolvedRole || userRole;
        if (activeRole && ['owner', 'admin'].includes(activeRole)) {
          setError("You are signed in as an administrator. My Pets is for linked client accounts. Use Client Management to view and manage client pets.");
        } else {
          setError("Your portal account is not yet linked to a client profile. Please contact support.");
        }
      } else {
        setPets(sanitizePetsList(data.pets || []));
        setError(null);
      }
    } catch (err) {
      console.error("Fetch pets failed", err);
      setApiError("Failed to load pets. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    checkSession();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleStartEdit = (pet) => {
    const initialValues = {
      name: pet.name || '',
      species: pet.species || '',
      breed: pet.breed || '',
      age: pet.age || '',
      care_instructions: pet.care_instructions || '',
      feeding_notes: pet.feeding_notes || '',
      medication_notes: pet.medication_notes || '',
      behavior_notes: pet.behavior_notes || '',
      health: {
        vet_name: pet.health?.vet_name || '',
        vet_phone: pet.health?.vet_phone || ''
      }
    };

    if (editingPetId && checkIsDirty(editForm, initialFormValues)) {
      if (!window.confirm("You have unsaved pet changes. Are you sure you want to discard them?")) {
        return;
      }
    }

    setEditingPetId(pet.pet_id);
    setEditForm(JSON.parse(JSON.stringify(initialValues)));
    setInitialFormValues(initialValues);
    setReloadWarning(null);
  };

  const handleCancel = () => {
    if (editingPetId && checkIsDirty(editForm, initialFormValues)) {
      if (!window.confirm("You have unsaved pet changes. Are you sure you want to discard them?")) {
        return;
      }
    }
    setEditingPetId(null);
    setInitialFormValues(null);
    setReloadWarning(null);
  };

  const performReload = async (petId, petName) => {
    try {
      setSaving(true);
      const data = await getClientPets();
      
      if (data.message === "No local profile linked" || data.linked_profile === false) {
        throw new Error("No linked profile found.");
      }
      
      const reloadedPets = sanitizePetsList(data.pets || []);
      const isPresent = reloadedPets.some(p => p.pet_id === petId);
      if (!isPresent) {
        throw new Error("Updated pet not found in reloaded profile.");
      }

      setPets(reloadedPets);
      setEditingPetId(null);
      setInitialFormValues(null);
      setReloadWarning(null);
      showNotification(`Pet "${petName}" updated successfully.`, "success");
    } catch (reloadErr) {
      console.error("Authoritative reload failed:", reloadErr);
      setReloadWarning({
        message: "Pet updated successfully, but the latest profile could not be reloaded.",
        petId,
        petName
      });
    } finally {
      setSaving(false);
    }
  };

  const handleSave = async (petId) => {
    if (!editForm.name || !editForm.name.trim()) {
      showNotification("Name cannot be empty.", "error");
      return;
    }

    // Client-scoped and tenant-scoped duplicate detection
    const normalizedNewName = editForm.name.trim().toLowerCase();
    const hasDuplicate = pets.some(p => p.pet_id !== petId && p.name && p.name.trim().toLowerCase() === normalizedNewName);
    if (hasDuplicate) {
      const proceed = window.confirm(`Warning: You already have another pet named "${editForm.name.trim()}". Are you sure you want to continue?`);
      if (!proceed) return;
    }

    try {
      setSaving(true);
      setReloadWarning(null);
      await updateClientPet(petId, editForm);
      
      // Clear dirty state on successful save (PUT succeeds)
      setInitialFormValues(JSON.parse(JSON.stringify(editForm)));

      // Perform reload check
      await performReload(petId, editForm.name);
    } catch (err) {
      console.error(err);
      showNotification(err.message || "Failed to update pet. Please try again.", "error");
    } finally {
      setSaving(false);
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
              const data = await getClientPets();
              if (data.message === "No local profile linked" || data.linked_profile === false) {
                setPets([]);
                if (role && ['owner', 'admin'].includes(role)) {
                  setError("You are signed in as an administrator. My Pets is for linked client accounts. Use Client Management to view and manage client pets.");
                } else {
                  setError("Your portal account is not yet linked to a client profile. Please contact support.");
                }
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
      {notification && (
        <div className={`notification-banner ${notification.type}`}>
          <span className="msg">{notification.message}</span>
          <button onClick={() => setNotification(null)}>&times;</button>
        </div>
      )}
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
            <button onClick={() => fetchMyPets()} className="button-secondary" style={{ padding: '8px 16px' }}>
              Retry
            </button>
          </div>
        ) : error ? (
          <div className="card error-card" style={{ padding: '24px', textAlign: 'center' }}>
            <p className="error-text">{error}</p>
            {userRole && ['owner', 'admin'].includes(userRole) && (
              <div style={{ marginTop: '20px' }}>
                <a href="/admin" className="button-primary">Go to Admin Dashboard</a>
              </div>
            )}
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
            {pets.map(pet => {
              const isEditing = editingPetId === pet.pet_id;

              return (
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
                  {isEditing ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      <h3 style={{ margin: 0, fontSize: '1.25rem', fontFamily: 'var(--serif)', marginBottom: '8px' }}>Edit Pet Details</h3>
                      
                      <div className="field">
                        <label htmlFor={`edit-pet-name-${pet.pet_id}`} style={{ fontSize: '0.8rem', fontWeight: 'bold' }}>Name *</label>
                        <input
                          id={`edit-pet-name-${pet.pet_id}`}
                          type="text"
                          value={editForm.name}
                          onChange={e => setEditForm({ ...editForm, name: e.target.value })}
                          required
                          style={{ padding: '8px', fontSize: '0.9rem', width: '100%', boxSizing: 'border-box' }}
                        />
                      </div>

                      <div className="field">
                        <label htmlFor={`edit-pet-species-${pet.pet_id}`} style={{ fontSize: '0.8rem', fontWeight: 'bold' }}>Species</label>
                        <input
                          id={`edit-pet-species-${pet.pet_id}`}
                          type="text"
                          value={editForm.species}
                          onChange={e => setEditForm({ ...editForm, species: e.target.value })}
                          style={{ padding: '8px', fontSize: '0.9rem', width: '100%', boxSizing: 'border-box' }}
                        />
                      </div>

                      <div className="field">
                        <label htmlFor={`edit-pet-breed-${pet.pet_id}`} style={{ fontSize: '0.8rem', fontWeight: 'bold' }}>Breed</label>
                        <input
                          id={`edit-pet-breed-${pet.pet_id}`}
                          type="text"
                          value={editForm.breed}
                          onChange={e => setEditForm({ ...editForm, breed: e.target.value })}
                          style={{ padding: '8px', fontSize: '0.9rem', width: '100%', boxSizing: 'border-box' }}
                        />
                      </div>

                      <div className="field">
                        <label htmlFor={`edit-pet-age-${pet.pet_id}`} style={{ fontSize: '0.8rem', fontWeight: 'bold' }}>Age</label>
                        <input
                          id={`edit-pet-age-${pet.pet_id}`}
                          type="text"
                          value={editForm.age}
                          onChange={e => setEditForm({ ...editForm, age: e.target.value })}
                          style={{ padding: '8px', fontSize: '0.9rem', width: '100%', boxSizing: 'border-box' }}
                        />
                      </div>

                      <div className="field">
                        <label htmlFor={`edit-pet-care-instructions-${pet.pet_id}`} style={{ fontSize: '0.8rem', fontWeight: 'bold' }}>Care Instructions</label>
                        <textarea
                          id={`edit-pet-care-instructions-${pet.pet_id}`}
                          value={editForm.care_instructions}
                          onChange={e => setEditForm({ ...editForm, care_instructions: e.target.value })}
                          style={{ padding: '8px', fontSize: '0.9rem', width: '100%', boxSizing: 'border-box', minHeight: '60px' }}
                        />
                      </div>

                      <div className="field">
                        <label htmlFor={`edit-pet-feeding-notes-${pet.pet_id}`} style={{ fontSize: '0.8rem', fontWeight: 'bold' }}>Feeding Notes</label>
                        <textarea
                          id={`edit-pet-feeding-notes-${pet.pet_id}`}
                          value={editForm.feeding_notes}
                          onChange={e => setEditForm({ ...editForm, feeding_notes: e.target.value })}
                          style={{ padding: '8px', fontSize: '0.9rem', width: '100%', boxSizing: 'border-box', minHeight: '60px' }}
                        />
                      </div>

                      <div className="field">
                        <label htmlFor={`edit-pet-medication-notes-${pet.pet_id}`} style={{ fontSize: '0.8rem', fontWeight: 'bold' }}>Medication Notes</label>
                        <textarea
                          id={`edit-pet-medication-notes-${pet.pet_id}`}
                          value={editForm.medication_notes}
                          onChange={e => setEditForm({ ...editForm, medication_notes: e.target.value })}
                          style={{ padding: '8px', fontSize: '0.9rem', width: '100%', boxSizing: 'border-box', minHeight: '60px' }}
                        />
                      </div>

                      <div className="field">
                        <label htmlFor={`edit-pet-behavior-notes-${pet.pet_id}`} style={{ fontSize: '0.8rem', fontWeight: 'bold' }}>Behavior Notes</label>
                        <textarea
                          id={`edit-pet-behavior-notes-${pet.pet_id}`}
                          value={editForm.behavior_notes}
                          onChange={e => setEditForm({ ...editForm, behavior_notes: e.target.value })}
                          style={{ padding: '8px', fontSize: '0.9rem', width: '100%', boxSizing: 'border-box', minHeight: '60px' }}
                        />
                      </div>

                      <div className="field">
                        <label htmlFor={`edit-pet-vet-name-${pet.pet_id}`} style={{ fontSize: '0.8rem', fontWeight: 'bold' }}>Vet Name</label>
                        <input
                          id={`edit-pet-vet-name-${pet.pet_id}`}
                          type="text"
                          value={editForm.health?.vet_name || ''}
                          onChange={e => setEditForm({
                            ...editForm,
                            health: { ...(editForm.health || {}), vet_name: e.target.value }
                          })}
                          style={{ padding: '8px', fontSize: '0.9rem', width: '100%', boxSizing: 'border-box' }}
                        />
                      </div>

                      <div className="field">
                        <label htmlFor={`edit-pet-vet-phone-${pet.pet_id}`} style={{ fontSize: '0.8rem', fontWeight: 'bold' }}>Vet Phone</label>
                        <input
                          id={`edit-pet-vet-phone-${pet.pet_id}`}
                          type="text"
                          value={editForm.health?.vet_phone || ''}
                          onChange={e => setEditForm({
                            ...editForm,
                            health: { ...(editForm.health || {}), vet_phone: e.target.value }
                          })}
                          style={{ padding: '8px', fontSize: '0.9rem', width: '100%', boxSizing: 'border-box' }}
                        />
                      </div>

                      {reloadWarning && reloadWarning.petId === pet.pet_id && (
                        <div className="reload-warning-box" style={{ marginTop: '12px', padding: '12px', backgroundColor: 'var(--warning-bg, #fff3cd)', border: '1px solid var(--warning-border, #ffeeba)', borderRadius: '4px', color: 'var(--warning-text, #856404)' }}>
                          <p style={{ margin: 0, fontSize: '0.9rem' }}>{reloadWarning.message}</p>
                          <button
                            type="button"
                            className="button-secondary"
                            onClick={() => performReload(reloadWarning.petId, reloadWarning.petName)}
                            style={{ marginTop: '8px', padding: '6px 12px', fontSize: '0.85rem', width: '100%' }}
                            disabled={saving}
                          >
                            {saving ? 'Retrying...' : 'Retry Reload'}
                          </button>
                        </div>
                      )}

                      <div style={{ display: 'flex', gap: '8px', marginTop: '12px' }}>
                        <button
                          onClick={() => handleSave(pet.pet_id)}
                          className="button-primary"
                          style={{ flex: 1, padding: '10px' }}
                          disabled={saving}
                        >
                          {saving ? 'Saving...' : 'Save'}
                        </button>
                        <button
                          onClick={handleCancel}
                          className="button-secondary"
                          style={{ flex: 1, padding: '10px' }}
                          disabled={saving}
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    <>
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
                        {pet.health?.vet_name && <p style={{ margin: '4px 0' }}><strong>Vet Name:</strong> {pet.health.vet_name}</p>}
                        {pet.health?.vet_phone && <p style={{ margin: '4px 0' }}><strong>Vet Phone:</strong> {pet.health.vet_phone}</p>}
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

                      <button
                        onClick={() => handleStartEdit(pet)}
                        className="button-secondary"
                        style={{ marginTop: '12px', width: '100%' }}
                      >
                        Edit Pet
                      </button>
                    </>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
};

export default MyPets;
