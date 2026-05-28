import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { submitRequest, submitClientRequest, getStaffOptions } from '../api/client';
import { getSession, getEffectiveRole } from '../api/auth';
import { TERMS_VERSION, PRIVACY_VERSION } from '../constants/policy';
import DatePickerGrid from './DatePickerGrid';
import './IntakeForm.css';

const IntakeForm = () => {
  const [step, setStep] = useState(1);
  const [formData, setFormData] = useState({
    client_name: '',
    client_email: '',
    selected_dates: [],
    range_start: '',
    range_end: '',
    // Release 2: Multi-select visit windows (array)
    visit_windows: ['ANYTIME'],
    visit_window: 'ANYTIME', // Legacy field for backward compat
    preferred_time: '',
    timing_notes: '',
    // Release 2: Preferred sitter (informational only, does NOT auto-assign)
    preferred_sitter: '',
    preferred_sitter_name: '',
    // Release 4: Multi-pet structured data
    pets: [{name: '', species: 'DOG', breed: '', age: '', feeding_notes: '', medication_notes: '', behavior_notes: ''}],
    pet_names: '', // Legacy — auto-generated from pets array on submit
    pet_info: '',
    // Release 4: Household-level vet/emergency
    vet_info: {},
    emergency_contact: {},
    service_type: 'PET_SITTING',
    accepted_terms: false
  });
  const [status, setStatus] = useState({ type: '', message: '', requestId: '' });
  const [isSubmitting, setIsSubmitting] = useState(false);
  // Release 2: Staff options for preferred sitter dropdown
  const [staffOptions, setStaffOptions] = useState([]);
  const [staffOptionsLoading, setStaffOptionsLoading] = useState(false);

  useEffect(() => {
    getSession().then(s => {
      if (s && getEffectiveRole(s) === 'client') {
        setFormData(prev => ({
          ...prev,
          client_email: s.idToken.payload.email || '',
          client_name: s.idToken.payload.name || ''
        }));
      }
    }).catch(() => {});
    
    // Release 2: Load staff options for preferred sitter dropdown.
    // Uses a sanitized public endpoint that only returns display names.
    setStaffOptionsLoading(true);
    getStaffOptions()
      .then(data => {
        setStaffOptions(data.staff_options || []);
      })
      .catch(() => {
        // Fail gracefully — preferred sitter is optional
        setStaffOptions([]);
      })
      .finally(() => setStaffOptionsLoading(false));
  }, []);

  const validateStep = () => {
    if (step === 1) {
      return formData.client_name && formData.client_email;
    }
    if (step === 2) {
      if (!formData.service_type) return false;
      return formData.selected_dates && formData.selected_dates.length > 0;
    }
    if (step === 3) {
      // Release 4: Validate at least one pet has a name
      const pets = formData.pets || [];
      return pets.some(p => p.name && p.name.trim());
    }
    return true;
  };

  const nextStep = () => {
    if (validateStep()) {
      setStep(step + 1);
      window.scrollTo(0, 0);
    } else {
      alert("Please fill in all required fields.");
    }
  };

  const prevStep = () => {
    setStep(step - 1);
    window.scrollTo(0, 0);
  };

  const handleSubmit = async (e) => {
    if (e) e.preventDefault();
    if (!validateStep()) return;

    setIsSubmitting(true);
    setStatus({ type: 'info', message: 'Submitting your request...' });
    
    try {
      const s = await getSession();
      const role = getEffectiveRole(s);
      
      let payload = { ...formData };
      
      const sorted = [...(payload.selected_dates || [])].sort();
      payload.selected_dates = sorted;
      payload.start_date = sorted[0];
      if (sorted.length > 1) {
        payload.end_date = sorted[sorted.length - 1];
      } else {
        payload.end_date = '';
      }
      
      let result;
      if (s && role === 'client') {
        result = await submitClientRequest(payload);
      } else {
        const fullPayload = {
          ...payload,
          accepted_terms: true,
          accepted_privacy: true,
          terms_version: TERMS_VERSION,
          privacy_version: PRIVACY_VERSION,
          accepted_at: new Date().toISOString(),
          accepted_by_email: formData.client_email,
          source: 'public_intake'
        };
        result = await submitRequest(fullPayload);
      }
      
      setStatus({ 
        type: 'success', 
        message: "Request Received!", 
        requestId: result.request_id 
      });
      setStep(4); // Success step
    } catch (error) {
      setStatus({ type: 'error', message: error.message });
      setIsSubmitting(false);
    }
  };

  const renderStepIndicator = () => (
    <div className="intake-stepper">
      {[
        { n: 1, label: 'Contact' },
        { n: 2, label: 'Schedule' },
        { n: 3, label: 'Pets' }
      ].map((s) => (
        <div 
          key={s.n} 
          className={`step-indicator ${step === s.n ? 'active' : ''} ${step > s.n ? 'completed' : ''}`}
        >
          <div className="step-number">{step > s.n ? '✓' : s.n}</div>
          <span className="step-label">{s.label}</span>
        </div>
      ))}
    </div>
  );

  return (
    <div className="section intake-section">
      <div className="container" style={{ maxWidth: '700px' }}>
        
        {step < 4 && (
          <div className="intake-header" style={{ marginBottom: '40px', textAlign: 'center' }}>
            <span className="badge">Service Request</span>
            <h1 style={{ marginTop: '16px', fontSize: '2.5rem' }}>Let's get started</h1>
            <p className="subtitle" style={{ color: 'var(--text-muted)', marginTop: '12px' }}>
              Complete these 3 quick steps to request care for your pets.
            </p>
          </div>
        )}

        <div className="card intake-card" style={{ padding: '48px' }}>
          {step < 4 && renderStepIndicator()}

          <form onSubmit={(e) => e.preventDefault()} className="premium-form">
            
            {step === 1 && (
              <div className="form-step-content">
                <h3 style={{ marginBottom: '24px' }}>How can we reach you?</h3>
                <div className="grid">
                  <div className="field">
                    <label>Full Name *</label>
                    <input 
                      type="text" 
                      value={formData.client_name} 
                      onChange={(e) => setFormData({...formData, client_name: e.target.value})} 
                      placeholder="Alex Barker"
                      required 
                    />
                  </div>
                  <div className="field">
                    <label>Email Address *</label>
                    <input 
                      type="email" 
                      value={formData.client_email} 
                      onChange={(e) => setFormData({...formData, client_email: e.target.value})} 
                      placeholder="alex@example.com"
                      required 
                    />
                  </div>
                </div>
                {/* Release 4C: Client phone — optional, persisted on REQ and propagated to Client Management */}
                <div className="field" style={{ marginTop: '16px' }}>
                  <label>Phone Number (Optional)</label>
                  <input 
                    type="tel" 
                    value={formData.client_phone || ''} 
                    onChange={(e) => setFormData({...formData, client_phone: e.target.value})} 
                    placeholder="555-123-4567"
                  />
                </div>
                <div className="form-actions">
                  <Link to="/" className="button-secondary">Cancel</Link>
                  <button type="button" onClick={nextStep} className="button-primary">Next: Schedule →</button>
                </div>
              </div>
            )}

            {step === 2 && (
              <div className="form-step-content">
                <h3 style={{ marginBottom: '24px' }}>When do you need care?</h3>
                <div className="field" style={{ marginBottom: '24px' }}>
                  <label>Service Type *</label>
                  <select 
                    value={formData.service_type}
                    onChange={(e) => setFormData({...formData, service_type: e.target.value})}
                  >
                    <option value="PET_SITTING">Pet Sitting (Check-ins)</option>
                    <option value="DOG_WALKING">Daily Dog Walking</option>
                    <option value="OVERNIGHT">Overnight Care</option>
                  </select>
                </div>

                <div className="field" style={{ marginBottom: '24px' }}>
                  <label>Visit Dates *</label>
                  <div style={{ marginTop: '8px', background: 'var(--card-bg-muted, #f8f9fa)', padding: '16px', borderRadius: 'var(--radius-md, 8px)', border: '1px solid var(--border-color, #dee2e6)' }}>
                    
                    {/* Client-friendly Range Helper */}
                    <div style={{ paddingBottom: '16px', borderBottom: '1px solid var(--border-soft, #e9ecef)', marginBottom: '16px' }}>
                      <p style={{ fontSize: '0.85rem', color: 'var(--text-muted, #6c757d)', marginBottom: '12px' }}>
                        Need care for multiple days in a row? Choose a start and end date to auto-fill the calendar below.
                      </p>
                      <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-end', flexWrap: 'wrap' }}>
                        <div className="field" style={{ flex: '1 1 120px', marginBottom: 0 }}>
                          <label style={{ fontSize: '0.75rem', marginBottom: '4px' }}>Start Date</label>
                          <input
                            type="date"
                            value={formData.range_start || ''}
                            onChange={(e) => setFormData(prev => ({ ...prev, range_start: e.target.value }))}
                            style={{ width: '100%', padding: '10px', borderRadius: '8px', border: '1px solid var(--border-soft, #dee2e6)' }}
                          />
                        </div>
                        <div className="field" style={{ flex: '1 1 120px', marginBottom: 0 }}>
                          <label style={{ fontSize: '0.75rem', marginBottom: '4px' }}>End Date</label>
                          <input
                            type="date"
                            value={formData.range_end || ''}
                            onChange={(e) => setFormData(prev => ({ ...prev, range_end: e.target.value }))}
                            style={{ width: '100%', padding: '10px', borderRadius: '8px', border: '1px solid var(--border-soft, #dee2e6)' }}
                          />
                        </div>
                        <button 
                          className="button-secondary" 
                          style={{ padding: '10px 16px', whiteSpace: 'nowrap', borderRadius: '8px', flex: '0 0 auto' }}
                          onClick={(e) => {
                            e.preventDefault();
                            if (!formData.range_start || !formData.range_end) return;
                            const start = new Date(formData.range_start + 'T00:00:00');
                            const end = new Date(formData.range_end + 'T00:00:00');
                            if (end < start) return;
                            const dates = [];
                            let curr = new Date(start);
                            while (curr <= end && dates.length < 14) {
                              const y = curr.getFullYear();
                              const m = String(curr.getMonth() + 1).padStart(2, '0');
                              const d = String(curr.getDate()).padStart(2, '0');
                              dates.push(`${y}-${m}-${d}`);
                              curr.setDate(curr.getDate() + 1);
                            }
                            setFormData(prev => {
                              const existing = new Set(prev.selected_dates || []);
                              dates.forEach(d => existing.add(d));
                              return { ...prev, selected_dates: Array.from(existing).sort().slice(0, 14), range_start: '', range_end: '' };
                            });
                          }}
                        >
                          Auto-fill Calendar
                        </button>
                      </div>
                    </div>

                    <DatePickerGrid
                      selectedDates={formData.selected_dates || []}
                      onDateToggle={(dateStr) => {
                        setFormData(prev => {
                          const current = prev.selected_dates || [];
                          if (current.includes(dateStr)) {
                            return { ...prev, selected_dates: current.filter(d => d !== dateStr) };
                          }
                          if (current.length >= 14) return prev;
                          return { ...prev, selected_dates: [...current, dateStr] };
                        });
                      }}
                      maxSelections={14}
                    />
                    <div className="date-picker-summary" style={{ display: 'flex', flexDirection: 'column', gap: '8px', background: 'var(--bg-muted, #f1f3f5)', padding: '12px', borderRadius: 'var(--radius-sm, 6px)', marginTop: '12px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ fontSize: '0.85rem', fontWeight: '700', color: 'var(--text-primary, #333)' }}>
                          {(formData.selected_dates || []).length}/14 days selected
                        </span>
                        {(formData.selected_dates || []).length > 0 && (
                          <button 
                            type="button"
                            onClick={() => setFormData(prev => ({ ...prev, selected_dates: [] }))}
                            style={{ background: 'none', border: 'none', color: 'var(--primary, #007bff)', fontSize: '0.8rem', fontWeight: '600', cursor: 'pointer' }}
                          >
                            Start Over
                          </button>
                        )}
                      </div>
                      {(formData.selected_dates || []).length > 0 && (
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                          {[...(formData.selected_dates || [])].sort().map(d => {
                            const dateObj = new Date(d + 'T00:00:00');
                            const shortStr = dateObj.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
                            return <span key={d} className="date-chip" style={{ fontSize: '0.75rem', background: 'var(--card-bg, #fff)', border: '1px solid var(--border-soft, #dee2e6)', padding: '2px 8px', borderRadius: '12px', color: 'var(--text-main, #495057)' }}>{shortStr}</span>;
                          })}
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                {/* Release 2: Multi-select visit window checkboxes */}
                <div className="field" style={{ marginBottom: '24px' }}>
                  <label>Preferred Visit Windows</label>
                  <p className="field-hint" style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '12px' }}>
                    Select one or more time windows that work for you.
                  </p>
                  <div className="visit-window-checkboxes" style={{ display: 'flex', flexWrap: 'wrap', gap: '10px' }}>
                    {[
                      { value: 'MORNING', label: 'Morning (7–10 AM)' },
                      { value: 'MIDDAY', label: 'Midday (11 AM–2 PM)' },
                      { value: 'AFTERNOON', label: 'Afternoon (3–6 PM)' },
                      { value: 'EVENING', label: 'Evening (7–10 PM)' },
                      { value: 'ANYTIME', label: 'Anytime (Flexible)' },
                    ].map(opt => {
                      const isChecked = formData.visit_windows.includes(opt.value);
                      return (
                        <label 
                          key={opt.value} 
                          className={`visit-window-chip ${isChecked ? 'selected' : ''}`}
                        >
                          <input
                            type="checkbox"
                            checked={isChecked}
                            onChange={() => {
                              let newWindows;
                              if (opt.value === 'ANYTIME') {
                                // ANYTIME is mutually exclusive — selecting it clears others
                                newWindows = isChecked ? [] : ['ANYTIME'];
                              } else {
                                // Selecting a specific window clears ANYTIME
                                const withoutAnytime = formData.visit_windows.filter(w => w !== 'ANYTIME');
                                if (isChecked) {
                                  newWindows = withoutAnytime.filter(w => w !== opt.value);
                                } else {
                                  newWindows = [...withoutAnytime, opt.value];
                                }
                              }
                              // Default to ANYTIME if nothing selected
                              if (newWindows.length === 0) newWindows = ['ANYTIME'];
                              setFormData({
                                ...formData, 
                                visit_windows: newWindows,
                                visit_window: newWindows.includes('ANYTIME') ? 'ANYTIME' : newWindows[0]
                              });
                            }}
                            style={{ display: 'none' }}
                          />
                          <span>{isChecked ? '✓' : ''}</span>
                          <span>{opt.label}</span>
                        </label>
                      );
                    })}
                  </div>
                </div>

                {/* Release 2: Preferred Sitter — informational only, does NOT auto-assign */}
                {staffOptions.length > 0 && (
                  <div className="field" style={{ marginBottom: '24px' }}>
                    <label>Preferred Sitter (Optional)</label>
                    <p className="field-hint" style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '8px' }}>
                      Let us know if you have a preference. We'll do our best to accommodate.
                    </p>
                    <select
                      value={formData.preferred_sitter}
                      onChange={(e) => {
                        const selected = staffOptions.find(s => s.id === e.target.value);
                        setFormData({
                          ...formData,
                          preferred_sitter: e.target.value,
                          preferred_sitter_name: selected ? selected.name : ''
                        });
                      }}
                    >
                      <option value="">No preference</option>
                      {staffOptions.map(s => (
                        <option key={s.id} value={s.id}>{s.name}</option>
                      ))}
                    </select>
                  </div>
                )}

                {/* Timing notes — already supported by payload structure */}
                <div className="field">
                  <label>Timing Notes (Optional)</label>
                  <input
                    type="text"
                    value={formData.timing_notes}
                    onChange={(e) => setFormData({...formData, timing_notes: e.target.value})}
                    placeholder="e.g. After 9am preferred, key under mat..."
                  />
                </div>

                <div className="form-actions">
                  <button type="button" onClick={prevStep} className="button-secondary">← Back</button>
                  <button type="button" onClick={nextStep} className="button-primary">Next: Pet Info →</button>
                </div>
              </div>
            )}

            {step === 3 && (
              <div className="form-step-content">
                <h3 style={{ marginBottom: '24px' }}>Tell us about your pets</h3>
                
                {/* Release 4: Multi-pet repeatable entry */}
                {(formData.pets || [{name: '', species: 'DOG', breed: '', age: '', feeding_notes: '', medication_notes: '', behavior_notes: ''}]).map((pet, idx) => (
                  <div key={idx} style={{ marginBottom: '24px', padding: '20px', border: '1px solid var(--border)', borderRadius: '12px', position: 'relative' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                      <h4 style={{ margin: 0 }}>Pet {idx + 1}</h4>
                      {(formData.pets || []).length > 1 && (
                        <button type="button" onClick={() => {
                          const updated = [...(formData.pets || [])];
                          updated.splice(idx, 1);
                          setFormData({...formData, pets: updated});
                        }} style={{ background: 'none', border: 'none', color: 'var(--danger, #dc3545)', cursor: 'pointer', fontSize: '0.85rem' }}>Remove</button>
                      )}
                    </div>
                    <div className="grid" style={{ marginBottom: '12px' }}>
                      <div className="field">
                        <label>Pet Name *</label>
                        <input type="text" value={pet.name} onChange={(e) => {
                          const updated = [...(formData.pets || [])];
                          updated[idx] = {...updated[idx], name: e.target.value};
                          setFormData({...formData, pets: updated});
                        }} placeholder="e.g. Luna" required />
                      </div>
                      <div className="field">
                        <label>Species</label>
                        <select value={pet.species || 'DOG'} onChange={(e) => {
                          const updated = [...(formData.pets || [])];
                          updated[idx] = {...updated[idx], species: e.target.value};
                          setFormData({...formData, pets: updated});
                        }}>
                          <option value="DOG">Dog</option>
                          <option value="CAT">Cat</option>
                          <option value="OTHER">Other</option>
                        </select>
                      </div>
                    </div>
                    <div className="grid" style={{ marginBottom: '12px' }}>
                      <div className="field">
                        <label>Breed</label>
                        <input type="text" value={pet.breed || ''} onChange={(e) => {
                          const updated = [...(formData.pets || [])];
                          updated[idx] = {...updated[idx], breed: e.target.value};
                          setFormData({...formData, pets: updated});
                        }} placeholder="e.g. Golden Retriever" />
                      </div>
                      <div className="field">
                        <label>Age (years)</label>
                        <input type="number" min="0" max="30" value={pet.age || ''} onChange={(e) => {
                          const updated = [...(formData.pets || [])];
                          updated[idx] = {...updated[idx], age: e.target.value ? parseInt(e.target.value) : ''};
                          setFormData({...formData, pets: updated});
                        }} placeholder="e.g. 3" />
                      </div>
                    </div>
                    <div className="field" style={{ marginBottom: '8px' }}>
                      <label>Feeding Notes</label>
                      <input type="text" value={pet.feeding_notes || ''} onChange={(e) => {
                        const updated = [...(formData.pets || [])];
                        updated[idx] = {...updated[idx], feeding_notes: e.target.value};
                        setFormData({...formData, pets: updated});
                      }} placeholder="Food type, schedule, portions..." />
                    </div>
                    <div className="field" style={{ marginBottom: '8px' }}>
                      <label>Medication Notes</label>
                      <input type="text" value={pet.medication_notes || ''} onChange={(e) => {
                        const updated = [...(formData.pets || [])];
                        updated[idx] = {...updated[idx], medication_notes: e.target.value};
                        setFormData({...formData, pets: updated});
                      }} placeholder="Medications, dosage, timing..." />
                    </div>
                    <div className="field">
                      <label>Behavior Notes</label>
                      <input type="text" value={pet.behavior_notes || ''} onChange={(e) => {
                        const updated = [...(formData.pets || [])];
                        updated[idx] = {...updated[idx], behavior_notes: e.target.value};
                        setFormData({...formData, pets: updated});
                      }} placeholder="Temperament, triggers, social notes..." />
                    </div>
                  </div>
                ))}

                <button type="button" onClick={() => {
                  const current = formData.pets || [{name: '', species: 'DOG', breed: '', age: '', feeding_notes: '', medication_notes: '', behavior_notes: ''}];
                  setFormData({...formData, pets: [...current, {name: '', species: 'DOG', breed: '', age: '', feeding_notes: '', medication_notes: '', behavior_notes: ''}]});
                }} style={{ marginBottom: '24px', padding: '10px 16px', border: '2px dashed var(--border)', borderRadius: '8px', background: 'none', cursor: 'pointer', width: '100%', color: 'var(--text-muted)' }}>
                  + Add Another Pet
                </button>

                {/* Release 4: Household-level vet/emergency */}
                <div style={{ marginBottom: '24px', padding: '20px', backgroundColor: 'var(--bg-muted, #f8f9fa)', borderRadius: '12px' }}>
                  <h4 style={{ marginBottom: '12px' }}>Vet & Emergency (Optional)</h4>
                  <div className="grid" style={{ marginBottom: '12px' }}>
                    <div className="field">
                      <label>Vet / Clinic Name</label>
                      <input type="text" value={(formData.vet_info || {}).vet_name || ''} onChange={(e) => {
                        setFormData({...formData, vet_info: {...(formData.vet_info || {}), vet_name: e.target.value}});
                      }} placeholder="Dr. Smith / Happy Paws Vet" />
                    </div>
                    <div className="field">
                      <label>Vet Phone</label>
                      <input type="tel" value={(formData.vet_info || {}).clinic_phone || ''} onChange={(e) => {
                        setFormData({...formData, vet_info: {...(formData.vet_info || {}), clinic_phone: e.target.value}});
                      }} placeholder="555-123-4567" />
                    </div>
                  </div>
                  <div className="grid">
                    <div className="field">
                      <label>Emergency Contact Name</label>
                      <input type="text" value={(formData.emergency_contact || {}).name || ''} onChange={(e) => {
                        setFormData({...formData, emergency_contact: {...(formData.emergency_contact || {}), name: e.target.value}});
                      }} placeholder="Jane Doe" />
                    </div>
                    <div className="field">
                      <label>Emergency Contact Phone</label>
                      <input type="tel" value={(formData.emergency_contact || {}).phone || ''} onChange={(e) => {
                        setFormData({...formData, emergency_contact: {...(formData.emergency_contact || {}), phone: e.target.value}});
                      }} placeholder="555-987-6543" />
                    </div>
                  </div>
                </div>

                {/* Terms & Privacy Acceptance */}
                <div className="field" style={{ marginTop: '24px', marginBottom: '24px' }}>
                  <label className="checkbox-label" style={{ display: 'flex', gap: '8px', alignItems: 'flex-start' }}>
                    <input
                      type="checkbox"
                      className="terms-checkbox"
                      checked={formData.accepted_terms}
                      onChange={(e) => setFormData({...formData, accepted_terms: e.target.checked})}
                      style={{ marginTop: '4px' }}
                    />
                    <span>
                      I agree to the{' '}
                      <Link to="/terms" target="_blank" rel="noopener noreferrer">Terms of Use</Link>
                      {' '}and acknowledge the{' '}
                      <Link to="/privacy" target="_blank" rel="noopener noreferrer">Privacy Policy</Link>.
                    </span>
                  </label>
                  {!formData.accepted_terms && (
                    <p className="field-error" style={{ color: 'var(--danger, #dc3545)', fontSize: '0.85rem', marginTop: '8px' }}>
                      You must accept the Terms of Use and Privacy Policy to continue.
                    </p>
                  )}
                </div>

                <div className="form-actions">
                  <button type="button" onClick={prevStep} className="button-secondary">← Back</button>
                  <button 
                    type="button" 
                    onClick={handleSubmit} 
                    className="button-primary"
                    disabled={isSubmitting || !formData.accepted_terms}
                  >
                    {isSubmitting ? 'Sending...' : 'Submit Request'}
                  </button>
                </div>
              </div>
            )}

            {step === 4 && (
              <div className="confirmation-screen">
                <span className="success-icon">🎉</span>
                <h2>Request Received!</h2>
                <p style={{ color: 'var(--text-muted)', marginTop: '16px', fontSize: '1.1rem' }}>
                  Thank you, {formData.client_name.split(' ')[0]}! We've received your request for {(formData.pets || []).filter(p => p.name).map(p => p.name).join(', ') || formData.pet_names || 'your pets'}.
                </p>
                
                <div style={{ 
                  background: 'var(--bg-muted)', 
                  padding: '24px', 
                  borderRadius: '16px', 
                  margin: '32px 0',
                  textAlign: 'left'
                }}>
                  <h4 style={{ marginBottom: '12px' }}>What's next?</h4>
                  <ol style={{ paddingLeft: '20px', margin: 0, fontSize: '0.95rem', color: 'var(--text-secondary)' }}>
                    <li style={{ marginBottom: '8px' }}>Ryan will review your request and reach out via email.</li>
                    <li style={{ marginBottom: '8px' }}>We'll schedule your free <strong>Meet & Greet</strong> visit.</li>
                    <li>Once approved, you'll receive a link to your secure client portal.</li>
                  </ol>
                </div>

                <p className="micro-text" style={{ fontSize: '0.8rem', opacity: 0.6 }}>
                  Reference ID: {status.requestId}
                </p>

                <div className="confirmation-actions">
                  <Link to="/" className="button-primary">Back to Portal Home</Link>
                </div>
              </div>
            )}

          </form>

          {status.type === 'error' && (
            <div className="card status-msg error" style={{ 
              marginTop: '24px', 
              padding: '16px', 
              backgroundColor: '#fee2e2',
              color: '#b91c1c',
              borderRadius: '8px',
              fontSize: '0.9rem'
            }}>
              <strong>Error:</strong> {status.message}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default IntakeForm;

