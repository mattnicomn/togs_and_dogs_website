import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { submitRequest, submitClientRequest, getStaffOptions } from '../api/client';
import { getSession, getEffectiveRole } from '../api/auth';
import { TERMS_VERSION, PRIVACY_VERSION } from '../constants/policy';
import { SERVICE_TYPES } from '../generated/contracts';
import DatePickerGrid from './DatePickerGrid';
import './IntakeForm.css';

// Web and Mobile share the canonical new-booking eligibility interpretation.
// The contract does not currently expose a Web-specific support flag; unlike
// Mobile, Web therefore needs no additional platform-capability predicate.
const intakeServiceTypes = Object.entries(SERVICE_TYPES.services)
  .filter(([, service]) => (
    service.lifecycle === 'active'
    && service.newBookingEligibility === 'eligible'
  ));

const initialServiceType = intakeServiceTypes[0]?.[0] || '';

const formatCanonicalTime = (value) => {
  if (!value) return '';
  const [hourValue, minute] = value.split(':');
  const hour = Number(hourValue);
  return `${hour % 12 || 12}:${minute} ${hour >= 12 ? 'PM' : 'AM'}`;
};

const getCanonicalWindowModel = (serviceType) => {
  const service = SERVICE_TYPES.services[serviceType];
  if (!['match_visits_per_day', 'exactly_one'].includes(service?.windowSelectionMode)) return null;

  const windows = service.allowedWindowIds
    .map((id) => ({ id, ...SERVICE_TYPES.windows[id] }))
    .filter((window) => (
      window.label
      && window.lifecycle === 'active'
      && window.newBookingEligibility === 'eligible'
    ));

  return { service, windows };
};

const IntakeForm = () => {
  const [step, setStep] = useState(1);
  const [formData, setFormData] = useState({
    client_name: '',
    client_email: '',
    selected_dates: [],
    range_start: '',
    range_end: '',
    // Release 2: Multi-select visit windows (array)
    visit_windows: [],
    visit_window: '', // Legacy field for backward compat
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
    service_type: initialServiceType,
    visits_per_day: null,
    accepted_terms: false
  });
  const [status, setStatus] = useState({ type: '', message: '', requestId: '' });
  const [validationErrors, setValidationErrors] = useState({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  // Release 2: Staff options for preferred sitter dropdown
  const [staffOptions, setStaffOptions] = useState([]);
  const [staffOptionsLoading, setStaffOptionsLoading] = useState(false);
  const selectedService = SERVICE_TYPES.services[formData.service_type];
  const canonicalWindowModel = getCanonicalWindowModel(formData.service_type);
  const usesCheckInSchedule = selectedService?.windowSelectionMode === 'match_visits_per_day';
  const usesExactWindowSchedule = selectedService?.windowSelectionMode === 'exactly_one';
  const hasValidationErrors = Object.values(validationErrors).some(Boolean);

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

  const validateStep = (currentStep = step) => {
    const errors = {};
    if (currentStep === 1) {
      if (!formData.client_name || !formData.client_name.trim()) errors.client_name = "Full Name is required.";
      if (!formData.client_email || !formData.client_email.trim()) errors.client_email = "Email Address is required.";
    }
    if (currentStep === 2) {
      if (!formData.service_type) errors.service_type = "Service Type is required.";
      if (!formData.selected_dates || formData.selected_dates.length === 0) {
        const hasRange = formData.range_start && formData.range_end;
        errors.selected_dates = hasRange
          ? "You entered a date range, but no visit dates are selected yet. Click 'Select Dates from Range' or select dates manually on the calendar below."
          : "Please select at least one visit date on the calendar, or enter a Start Date and End Date and click 'Select Dates from Range'.";
      }
      if (usesCheckInSchedule) {
        const visitsPerDayOptions = canonicalWindowModel.service.visitsPerDayOptions;
        if (!visitsPerDayOptions.includes(formData.visits_per_day)) {
          errors.visits_per_day = "Choose how many Check-In visits you need each day.";
        } else if (formData.visit_windows.length !== formData.visits_per_day) {
          errors.visit_windows = `Choose exactly ${formData.visits_per_day} visit window${formData.visits_per_day === 1 ? '' : 's'}.`;
        }
      }
      if (usesExactWindowSchedule && formData.visit_windows.length !== 1) {
        errors.visit_windows = "Choose exactly one visit window.";
      }
    }
    if (currentStep === 3) {
      const pets = formData.pets || [];
      if (!pets.some(p => p.name && p.name.trim())) {
        errors.pets = "At least one pet name is required.";
      }
    }
    setValidationErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const nextStep = () => {
    if (validateStep(step)) {
      setValidationErrors({});
      setStep(step + 1);
      window.scrollTo(0, 0);
    } else {
      setTimeout(() => {
        const firstErrorEl = document.querySelector('.field-error, .error-highlight, .validation-error-alert, .validation-summary-error');
        if (firstErrorEl) {
          firstErrorEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
          const input = firstErrorEl.querySelector('input, select, textarea');
          if (input) input.focus();
        }
      }, 50);
    }
  };

  const prevStep = () => {
    setValidationErrors({});
    setStep(step - 1);
    window.scrollTo(0, 0);
  };

  const handleServiceChange = (serviceType) => {
    setFormData((previous) => ({
      ...previous,
      service_type: serviceType,
      visits_per_day: null,
      visit_windows: [],
      visit_window: ''
    }));
    setValidationErrors((previous) => ({
      ...previous,
      service_type: null,
      visits_per_day: null,
      visit_windows: null
    }));
  };

  const handleVisitsPerDayChange = (count) => {
    if (!canonicalWindowModel?.service.visitsPerDayOptions.includes(count)) return;

    const allowedWindowIds = canonicalWindowModel.windows.map((window) => window.id);
    setFormData((previous) => {
      const retainedWindows = allowedWindowIds
        .filter((windowId) => previous.visit_windows.includes(windowId))
        .slice(0, count);
      return {
        ...previous,
        visits_per_day: count,
        visit_windows: count === allowedWindowIds.length
          ? allowedWindowIds
          : retainedWindows,
        visit_window: ''
      };
    });
    setValidationErrors((previous) => ({
      ...previous,
      visits_per_day: null,
      visit_windows: null
    }));
  };

  const handleVisitWindowChange = (windowId) => {
    if (!canonicalWindowModel || !formData.visits_per_day) return;

    const allowedWindowIds = canonicalWindowModel.windows.map((window) => window.id);
    if (!allowedWindowIds.includes(windowId)) return;

    setFormData((previous) => {
      const isSelected = previous.visit_windows.includes(windowId);
      const selected = new Set(isSelected
        ? previous.visit_windows.filter((id) => id !== windowId)
        : [...previous.visit_windows, windowId]);
      if (!isSelected && previous.visit_windows.length >= previous.visits_per_day) return previous;
      return {
        ...previous,
        visit_windows: allowedWindowIds.filter((id) => selected.has(id)),
        visit_window: ''
      };
    });
    setValidationErrors((previous) => ({ ...previous, visit_windows: null }));
  };

  const handleExactVisitWindowChange = (windowId) => {
    if (!usesExactWindowSchedule || !canonicalWindowModel) return;
    if (!canonicalWindowModel.windows.some((window) => window.id === windowId)) return;
    setFormData((previous) => ({
      ...previous,
      visits_per_day: null,
      visit_windows: [windowId],
      visit_window: ''
    }));
    setValidationErrors((previous) => ({ ...previous, visit_windows: null }));
  };

  const handleSubmit = async (e) => {
    if (e) e.preventDefault();
    if (!validateStep(step)) {
      setTimeout(() => {
        const firstErrorEl = document.querySelector('.field-error, .error-highlight, .validation-error-alert, .validation-summary-error');
        if (firstErrorEl) {
          firstErrorEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
      }, 50);
      return;
    }

    setIsSubmitting(true);
    setStatus({ type: 'info', message: 'Submitting your request...' });
    
    try {
      const s = await getSession();
      const role = getEffectiveRole(s);
      
      let payload = { ...formData };

      if (canonicalWindowModel) {
        const allowedWindowIds = canonicalWindowModel.windows.map((window) => window.id);
        payload.visit_windows = allowedWindowIds.filter((windowId) => payload.visit_windows.includes(windowId));
        delete payload.visit_window;
        if (!usesCheckInSchedule) delete payload.visits_per_day;
      } else {
        delete payload.visits_per_day;
        delete payload.visit_windows;
        delete payload.visit_window;
      }
      
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
                {hasValidationErrors && (
                  <div className="validation-summary-error" style={{ color: 'var(--accent-red, #f44336)', backgroundColor: 'rgba(244, 67, 54, 0.1)', border: '1px solid var(--accent-red, #f44336)', padding: '12px 16px', borderRadius: '8px', marginBottom: '20px', fontSize: '0.9rem', fontWeight: '500' }}>
                    ⚠️ Please fill in all required contact fields below.
                  </div>
                )}
                <div className="grid">
                  <div className={`field ${validationErrors.client_name ? 'field-error' : ''}`}>
                    <label>Full Name *</label>
                    <input 
                      type="text" 
                      value={formData.client_name} 
                      onChange={(e) => {
                        setFormData({...formData, client_name: e.target.value});
                        if (validationErrors.client_name) setValidationErrors(prev => ({ ...prev, client_name: null }));
                      }} 
                      placeholder="Alex Barker"
                      required 
                    />
                    {validationErrors.client_name && <span className="error-text" style={{ color: 'var(--accent-red, #f44336)', fontSize: '0.8rem', marginTop: '4px', display: 'block' }}>{validationErrors.client_name}</span>}
                  </div>
                  <div className={`field ${validationErrors.client_email ? 'field-error' : ''}`}>
                    <label>Email Address *</label>
                    <input 
                      type="email" 
                      value={formData.client_email} 
                      onChange={(e) => {
                        setFormData({...formData, client_email: e.target.value});
                        if (validationErrors.client_email) setValidationErrors(prev => ({ ...prev, client_email: null }));
                      }} 
                      placeholder="alex@example.com"
                      required 
                    />
                    {validationErrors.client_email && <span className="error-text" style={{ color: 'var(--accent-red, #f44336)', fontSize: '0.8rem', marginTop: '4px', display: 'block' }}>{validationErrors.client_email}</span>}
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
                {hasValidationErrors && (
                  <div className="validation-summary-error" style={{ color: 'var(--accent-red, #f44336)', backgroundColor: 'rgba(244, 67, 54, 0.1)', border: '1px solid var(--accent-red, #f44336)', padding: '12px 16px', borderRadius: '8px', marginBottom: '20px', fontSize: '0.9rem', fontWeight: '500' }}>
                    <div style={{ fontWeight: '600', marginBottom: validationErrors.selected_dates && validationErrors.visit_windows ? '8px' : '0' }}>
                      ⚠️ Please complete the highlighted schedule fields below.
                    </div>
                    {validationErrors.selected_dates && (validationErrors.visits_per_day || validationErrors.visit_windows) && (
                      <ul style={{ margin: '0 0 0 20px', padding: '0', listStyleType: 'disc' }}>
                        <li>Visit Dates</li>
                        {validationErrors.visits_per_day && <li>Visits per Day</li>}
                        {validationErrors.visit_windows && <li>Preferred Visit Windows</li>}
                      </ul>
                    )}
                  </div>
                )}
                <div className={`field ${validationErrors.service_type ? 'field-error' : ''}`} style={{ marginBottom: '24px' }}>
                  <label htmlFor="intake-service-type">Service Type *</label>
                  <select 
                    id="intake-service-type"
                    value={formData.service_type}
                    onChange={(e) => handleServiceChange(e.target.value)}
                    aria-invalid={Boolean(validationErrors.service_type)}
                    aria-describedby={validationErrors.service_type ? 'service-type-error' : undefined}
                  >
                    {intakeServiceTypes.map(([identifier, service]) => (
                      <option key={identifier} value={identifier}>{service.labelLong}</option>
                    ))}
                  </select>
                  {validationErrors.service_type && <span id="service-type-error" className="error-text" style={{ color: 'var(--accent-red, #f44336)', fontSize: '0.8rem', marginTop: '4px', display: 'block' }}>{validationErrors.service_type}</span>}
                </div>

                <div className={`field ${validationErrors.selected_dates ? 'field-error' : ''}`} style={{ marginBottom: '24px' }}>
                  <label>Visit Dates *</label>
                  {validationErrors.selected_dates && (
                    <div className="validation-error-alert" style={{ color: 'var(--accent-red, #f44336)', fontSize: '0.9rem', marginBottom: '10px', fontWeight: '500' }}>
                      ⚠️ {validationErrors.selected_dates}
                    </div>
                  )}
                  <div className={`intake-date-picker-card ${validationErrors.selected_dates ? 'error-highlight' : ''}`} style={{ border: validationErrors.selected_dates ? '2px solid var(--accent-red, #f44336)' : undefined }}>
                    
                    {/* Client-friendly Range Helper */}
                    <div className="range-helper-container">
                      <p style={{ fontSize: '0.85rem', color: 'var(--text-muted, #6c757d)', marginBottom: '12px' }}>
                        Need care for multiple days in a row? Choose a start and end date to auto-fill the calendar below.
                      </p>
                      <div className="range-helper-row">
                        <div className="field range-helper-field">
                          <label style={{ fontSize: '0.75rem', marginBottom: '4px' }}>Start Date</label>
                          <input
                            type="date"
                            value={formData.range_start || ''}
                            onChange={(e) => setFormData(prev => ({ ...prev, range_start: e.target.value }))}
                            className="range-helper-input"
                          />
                        </div>
                        <div className="field range-helper-field">
                          <label style={{ fontSize: '0.75rem', marginBottom: '4px' }}>End Date</label>
                          <input
                            type="date"
                            value={formData.range_end || ''}
                            onChange={(e) => setFormData(prev => ({ ...prev, range_end: e.target.value }))}
                            className="range-helper-input"
                          />
                        </div>
                        <button 
                          type="button"
                          className="button-primary btn-range-autofill" 
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
                            setValidationErrors(prev => ({ ...prev, selected_dates: null }));
                            setFormData(prev => {
                              const existing = new Set(prev.selected_dates || []);
                              dates.forEach(d => existing.add(d));
                              return { ...prev, selected_dates: Array.from(existing).sort().slice(0, 14), range_start: '', range_end: '' };
                            });
                          }}
                        >
                          Select Dates from Range
                        </button>
                      </div>
                    </div>

                    <DatePickerGrid
                      selectedDates={formData.selected_dates || []}
                      onDateToggle={(dateStr) => {
                        setValidationErrors(prev => ({ ...prev, selected_dates: null }));
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
                    <div className="date-picker-summary-container">
                      <div className="date-picker-summary-header">
                        <span className="date-picker-summary-title">
                          {(formData.selected_dates || []).length}/14 days selected
                        </span>
                        {(formData.selected_dates || []).length > 0 && (
                          <button 
                            type="button"
                            onClick={() => setFormData(prev => ({ ...prev, selected_dates: [] }))}
                            className="btn-clear-dates"
                          >
                            Start Over
                          </button>
                        )}
                      </div>
                      {(formData.selected_dates || []).length > 0 && (
                        <div className="date-chip-list">
                          {[...(formData.selected_dates || [])].sort().map(d => {
                            const dateObj = new Date(d + 'T00:00:00');
                            const shortStr = dateObj.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
                            return <span key={d} className="date-chip">{shortStr}</span>;
                          })}
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                {usesCheckInSchedule && (
                  <div className="check-in-schedule" aria-label="Check-In schedule">
                    <fieldset
                      className={`field check-in-fieldset ${validationErrors.visits_per_day ? 'field-error error-highlight' : ''}`}
                      aria-describedby={validationErrors.visits_per_day ? 'visits-per-day-error' : 'visits-per-day-hint'}
                    >
                      <legend>Visits per Day *</legend>
                      <p id="visits-per-day-hint" className="field-hint">
                        Choose how many Check-In visits you need each day.
                      </p>
                      {validationErrors.visits_per_day && (
                        <div id="visits-per-day-error" className="validation-error-alert" role="alert">
                          ⚠️ {validationErrors.visits_per_day}
                        </div>
                      )}
                      <div className="visits-per-day-options">
                        {canonicalWindowModel.service.visitsPerDayOptions.map((count) => (
                          <label
                            key={count}
                            className={`selection-chip ${formData.visits_per_day === count ? 'selected' : ''}`}
                          >
                            <input
                              className="selection-chip-input"
                              type="radio"
                              name="visits-per-day"
                              value={count}
                              checked={formData.visits_per_day === count}
                              onChange={() => handleVisitsPerDayChange(count)}
                              aria-label={`${count} visit${count === 1 ? '' : 's'} per day`}
                            />
                            <span>{count}</span>
                            <span className="sr-only"> visit{count === 1 ? '' : 's'} per day</span>
                          </label>
                        ))}
                      </div>
                    </fieldset>

                    <fieldset
                      className={`field check-in-fieldset ${validationErrors.visit_windows ? 'field-error error-highlight' : ''}`}
                      aria-describedby={validationErrors.visit_windows ? 'visit-windows-error' : 'visit-windows-hint'}
                    >
                      <legend>Preferred Visit Window{formData.visits_per_day === 1 ? '' : 's'} *</legend>
                      <p id="visit-windows-hint" className="field-hint">
                        {!formData.visits_per_day
                          ? 'Choose visits per day first.'
                          : formData.visits_per_day === canonicalWindowModel.windows.length
                            ? 'All daily windows are selected automatically.'
                            : `Choose exactly ${formData.visits_per_day} window${formData.visits_per_day === 1 ? '' : 's'} (${formData.visit_windows.length} selected).`}
                      </p>
                      {validationErrors.visit_windows && (
                        <div id="visit-windows-error" className="validation-error-alert" role="alert">
                          ⚠️ {validationErrors.visit_windows}
                        </div>
                      )}
                      <div className="visit-window-checkboxes">
                        {canonicalWindowModel.windows.map((window) => {
                          const isChecked = formData.visit_windows.includes(window.id);
                          const allWindowsSelected = formData.visits_per_day === canonicalWindowModel.windows.length;
                          const isDisabled = !formData.visits_per_day
                            || allWindowsSelected
                            || (!isChecked && formData.visit_windows.length >= formData.visits_per_day);
                          const timeRange = `${formatCanonicalTime(window.start)}–${formatCanonicalTime(window.end)}`;
                          return (
                            <label
                              key={window.id}
                              className={`visit-window-chip ${isChecked ? 'selected' : ''} ${isDisabled ? 'disabled' : ''}`}
                            >
                              <input
                                className="selection-chip-input"
                                type="checkbox"
                                checked={isChecked}
                                disabled={isDisabled}
                                onChange={() => handleVisitWindowChange(window.id)}
                                aria-label={`${window.label}, ${timeRange.replace('–', ' to ')}`}
                              />
                              <span aria-hidden="true">{isChecked ? '✓' : ''}</span>
                              <span>
                                <strong>{window.label}</strong>
                                <small>{timeRange}</small>
                              </span>
                            </label>
                          );
                        })}
                      </div>
                    </fieldset>
                  </div>
                )}

                {usesExactWindowSchedule && canonicalWindowModel && (
                  <fieldset
                    className={`field check-in-fieldset ${validationErrors.visit_windows ? 'field-error error-highlight' : ''}`}
                    aria-describedby={validationErrors.visit_windows ? 'walk-window-error' : 'walk-window-hint'}
                  >
                    <legend>Preferred Visit Window *</legend>
                    <p id="walk-window-hint" className="field-hint">
                      Choose one window. It applies to every selected date.
                    </p>
                    {validationErrors.visit_windows && (
                      <div id="walk-window-error" className="validation-error-alert" role="alert">
                        ⚠️ {validationErrors.visit_windows}
                      </div>
                    )}
                    <div className="visit-window-checkboxes">
                      {canonicalWindowModel.windows.map((window) => {
                        const isChecked = formData.visit_windows[0] === window.id;
                        const timeRange = `${formatCanonicalTime(window.start)}–${formatCanonicalTime(window.end)}`;
                        return (
                          <label key={window.id} className={`visit-window-chip ${isChecked ? 'selected' : ''}`}>
                            <input
                              className="selection-chip-input"
                              type="radio"
                              name="walk-visit-window"
                              value={window.id}
                              checked={isChecked}
                              onChange={() => handleExactVisitWindowChange(window.id)}
                              aria-label={`${window.label}, ${timeRange.replace('–', ' to ')}`}
                            />
                            <span aria-hidden="true">{isChecked ? '✓' : ''}</span>
                            <span>
                              <strong>{window.label}</strong>
                              <small>{timeRange}</small>
                            </span>
                          </label>
                        );
                      })}
                    </div>
                  </fieldset>
                )}

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
                <section className="request-review-card" aria-labelledby="request-review-heading">
                  <h4 id="request-review-heading">Request Summary</h4>
                  <dl className="request-review-list">
                    <div>
                      <dt>Service</dt>
                      <dd>{selectedService?.label || formData.service_type}</dd>
                    </div>
                    {selectedService?.durationStatus === 'confirmed' && (
                      <div>
                        <dt>Duration</dt>
                        <dd>{selectedService.durationMinutes} minutes</dd>
                      </div>
                    )}
                    {usesCheckInSchedule && (
                      <>
                        <div>
                          <dt>Visits per day</dt>
                          <dd>{formData.visits_per_day}</dd>
                        </div>
                        <div>
                          <dt>Visit windows</dt>
                          <dd>
                            <ul>
                              {canonicalWindowModel.windows
                                .filter((window) => formData.visit_windows.includes(window.id))
                                .map((window) => (
                                  <li key={window.id}>
                                    {window.label} <span>({formatCanonicalTime(window.start)}–{formatCanonicalTime(window.end)})</span>
                                  </li>
                                ))}
                            </ul>
                          </dd>
                        </div>
                      </>
                    )}
                    {usesExactWindowSchedule && canonicalWindowModel && (
                      <div>
                        <dt>Visit window</dt>
                        <dd>
                          {canonicalWindowModel.windows
                            .filter((window) => formData.visit_windows.includes(window.id))
                            .map((window) => `${window.label} (${formatCanonicalTime(window.start)}–${formatCanonicalTime(window.end)})`)
                            .join('')}
                        </dd>
                      </div>
                    )}
                    <div>
                      <dt>Visit dates</dt>
                      <dd>{[...(formData.selected_dates || [])].sort().join(', ')}</dd>
                    </div>
                  </dl>
                </section>
                {hasValidationErrors && (
                  <div className="validation-summary-error" style={{ color: 'var(--accent-red, #f44336)', backgroundColor: 'rgba(244, 67, 54, 0.1)', border: '1px solid var(--accent-red, #f44336)', padding: '12px 16px', borderRadius: '8px', marginBottom: '20px', fontSize: '0.9rem', fontWeight: '500' }}>
                    ⚠️ Please provide details for at least one pet.
                  </div>
                )}
                {validationErrors.pets && (
                  <div className="validation-error-alert" style={{ color: 'var(--accent-red, #f44336)', fontSize: '0.9rem', marginBottom: '16px', fontWeight: '500' }}>
                    ⚠️ {validationErrors.pets}
                  </div>
                )}
                
                {/* Release 4: Multi-pet repeatable entry */}
                {(formData.pets || [{name: '', species: 'DOG', breed: '', age: '', feeding_notes: '', medication_notes: '', behavior_notes: ''}]).map((pet, idx) => (
                  <div key={idx} style={{ marginBottom: '24px', padding: '20px', border: validationErrors.pets ? '1px solid var(--accent-red, #f44336)' : '1px solid var(--border)', borderRadius: '12px', position: 'relative' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                      <h4 style={{ margin: 0 }}>Pet {idx + 1}</h4>
                      {(formData.pets || []).length > 1 && (
                        <button type="button" onClick={() => {
                          const updated = [...(formData.pets || [])];
                          updated.splice(idx, 1);
                          setFormData({...formData, pets: updated});
                          if (validationErrors.pets) setValidationErrors(prev => ({ ...prev, pets: null }));
                        }} style={{ background: 'none', border: 'none', color: 'var(--danger, #dc3545)', cursor: 'pointer', fontSize: '0.85rem' }}>Remove</button>
                      )}
                    </div>
                    <div className="grid" style={{ marginBottom: '12px' }}>
                      <div className={`field ${validationErrors.pets ? 'field-error' : ''}`}>
                        <label>Pet Name *</label>
                        <input type="text" value={pet.name} onChange={(e) => {
                          const updated = [...(formData.pets || [])];
                          updated[idx] = {...updated[idx], name: e.target.value};
                          setFormData({...formData, pets: updated});
                          if (validationErrors.pets) setValidationErrors(prev => ({ ...prev, pets: null }));
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

