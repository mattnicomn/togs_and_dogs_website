import { useState } from 'react';
import { Link } from 'react-router-dom';
import { submitRequest } from '../api/client';
import './IntakeForm.css';

const IntakeForm = () => {
  const [step, setStep] = useState(1);
  const [formData, setFormData] = useState({
    client_name: '',
    client_email: '',
    start_date: '',
    end_date: '',
    visit_window: 'ANYTIME',
    preferred_time: '',
    timing_notes: '',
    pet_names: '',
    pet_info: '',
    service_type: 'PET_SITTING'
  });
  const [status, setStatus] = useState({ type: '', message: '', requestId: '' });
  const [isSubmitting, setIsSubmitting] = useState(false);

  const validateStep = () => {
    if (step === 1) {
      return formData.client_name && formData.client_email;
    }
    if (step === 2) {
      return formData.service_type && formData.start_date;
    }
    if (step === 3) {
      return formData.pet_names;
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
      const result = await submitRequest(formData);
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

                <div className="grid" style={{ marginBottom: '24px' }}>
                  <div className="field">
                    <label>Start Date *</label>
                    <input 
                      type="date" 
                      value={formData.start_date} 
                      onChange={(e) => setFormData({...formData, start_date: e.target.value})} 
                      required 
                    />
                  </div>
                  <div className="field">
                    <label>End Date (Optional)</label>
                    <input 
                      type="date" 
                      value={formData.end_date} 
                      onChange={(e) => setFormData({...formData, end_date: e.target.value})} 
                    />
                  </div>
                </div>

                <div className="grid">
                  <div className="field">
                    <label>Preferred Visit Window</label>
                    <select 
                      value={formData.visit_window}
                      onChange={(e) => setFormData({...formData, visit_window: e.target.value})}
                    >
                      <option value="MORNING">Morning (7 AM - 10 AM)</option>
                      <option value="MIDDAY">Midday (11 AM - 2 PM)</option>
                      <option value="AFTERNOON">Afternoon (3 PM - 6 PM)</option>
                      <option value="EVENING">Evening (7 PM - 10 PM)</option>
                      <option value="ANYTIME">Anytime (Flexible)</option>
                    </select>
                  </div>
                  <div className="field">
                    <label>Specific Time Requests</label>
                    <input 
                      type="text" 
                      value={formData.preferred_time} 
                      onChange={(e) => setFormData({...formData, preferred_time: e.target.value})} 
                      placeholder="e.g. Exactly 12:30 PM"
                    />
                  </div>
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
                <div className="field" style={{ marginBottom: '24px' }}>
                  <label>Pet Names *</label>
                  <input 
                    type="text" 
                    value={formData.pet_names} 
                    onChange={(e) => setFormData({...formData, pet_names: e.target.value})} 
                    placeholder="e.g. Luna and Milo"
                    required
                  />
                </div>

                <div className="field">
                  <label>Care Instructions & Details</label>
                  <textarea 
                    rows="5"
                    value={formData.pet_info} 
                    onChange={(e) => setFormData({...formData, pet_info: e.target.value})} 
                    placeholder="Routines, medications, favorite toys, or special needs..."
                  />
                </div>

                <div className="form-actions">
                  <button type="button" onClick={prevStep} className="button-secondary">← Back</button>
                  <button 
                    type="button" 
                    onClick={handleSubmit} 
                    className="button-primary"
                    disabled={isSubmitting}
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
                  Thank you, {formData.client_name.split(' ')[0]}! We've received your request for {formData.pet_names}.
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

