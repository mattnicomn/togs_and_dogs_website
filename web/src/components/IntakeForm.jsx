import { useState } from 'react';
import { Link } from 'react-router-dom';
import { submitRequest } from '../api/client';

const IntakeForm = () => {
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
  const [status, setStatus] = useState({ type: '', message: '' });

  const handleSubmit = async (e) => {
    e.preventDefault();
    setStatus({ type: 'info', message: 'Sending request...' });
    try {
      const result = await submitRequest(formData);
      setStatus({ 
        type: 'success', 
        message: `Success! We've received your request. We'll be in touch shortly to confirm and schedule your meet-and-greet. Support ID: ${result.request_id}` 
      });
      setFormData({ 
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
    } catch (error) {
      setStatus({ type: 'error', message: error.message });
    }
  };

  return (
    <div className="section intake-section">
      <div className="container" style={{ maxWidth: '800px' }}>
        <div className="intake-header" style={{ marginBottom: '48px' }}>
          <span className="badge">New Client Intake</span>
          <h1 style={{ marginTop: '16px' }}>Ready to get started?</h1>
          <p className="subtitle" style={{ fontSize: '1.2rem', color: 'var(--text-muted)', marginTop: '16px' }}>
            Tell us a bit about you and your pets. We'll reach out to schedule your free meet-and-greet.
          </p>
        </div>

        <div className="card intake-card">
          <div style={{ marginBottom: '32px', paddingBottom: '24px', borderBottom: '1px solid var(--border-soft)' }}>
            <h3 style={{ marginBottom: '8px' }}>Booking Request</h3>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.95rem', margin: 0 }}>
                Already a client? <Link to="/my-bookings" style={{ color: 'var(--primary)', fontWeight: '700', textDecoration: 'none' }}>Log in to your portal</Link> to request visits faster.
              </p>
              <div style={{ background: 'var(--bg-muted)', padding: '8px 16px', borderRadius: '8px', fontSize: '0.85rem', fontWeight: 600 }}>
                ⏱️ Takes about 2 minutes
              </div>
            </div>
          </div>

          <div style={{ background: 'var(--bg-surface)', padding: '24px', borderRadius: '12px', border: '1px solid var(--border-soft)', marginBottom: '32px' }}>
            <h4 style={{ marginBottom: '12px' }}>What happens next?</h4>
            <ol style={{ paddingLeft: '20px', color: 'var(--text-muted)', fontSize: '0.9rem', lineHeight: '1.6' }}>
              <li>Submit this form with your pet's basic info.</li>
              <li>Ryan will review your request and reach out within 24 hours.</li>
              <li>We'll schedule your <strong>free Meet & Greet</strong> to ensure we're the perfect fit.</li>
              <li>Once confirmed, you'll get portal access to manage all future bookings.</li>
            </ol>
          </div>
          
          <form onSubmit={handleSubmit} className="premium-form">
            <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))' }}>
              <div className="field">
                <label>Your Name</label>
                <input 
                  type="text" 
                  value={formData.client_name} 
                  onChange={(e) => setFormData({...formData, client_name: e.target.value})} 
                  placeholder="Alex Barker"
                  required 
                />
              </div>
              <div className="field">
                <label>Email Address</label>
                <input 
                  type="email" 
                  value={formData.client_email} 
                  onChange={(e) => setFormData({...formData, client_email: e.target.value})} 
                  placeholder="alex@example.com"
                  required 
                />
              </div>
            </div>

            <div className="field">
              <label>Service Type</label>
              <select 
                value={formData.service_type}
                onChange={(e) => setFormData({...formData, service_type: e.target.value})}
              >
                <option value="PET_SITTING">Pet Sitting (Check-ins)</option>
                <option value="DOG_WALKING">Daily Dog Walking</option>
                <option value="OVERNIGHT">Overnight Care</option>
              </select>
            </div>

            <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))' }}>
              <div className="field">
                <label>Start Date</label>
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

            <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))' }}>
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

            <div className="field">
              <label>Pet Names</label>
              <input 
                type="text" 
                value={formData.pet_names} 
                onChange={(e) => setFormData({...formData, pet_names: e.target.value})} 
                placeholder="e.g. Luna and Milo"
                required
              />
            </div>

            <div className="field">
              <label>About Your Pets</label>
              <textarea 
                rows="4"
                value={formData.pet_info} 
                onChange={(e) => setFormData({...formData, pet_info: e.target.value})} 
                placeholder="Routines, medications, favorite toys, or special needs..."
              />
            </div>

            <button type="submit" className="button-primary">Submit Request</button>
          </form>

          {status.message && (
            <div className={`card status-msg ${status.type}`} style={{ 
              marginTop: '24px', 
              padding: '20px', 
              backgroundColor: status.type === 'success' ? 'hsla(173, 80%, 31%, 0.1)' : status.type === 'error' ? '#fee2e2' : 'var(--bg-muted)',
              color: status.type === 'success' ? 'var(--primary)' : status.type === 'error' ? '#b91c1c' : 'var(--text-main)',
              fontWeight: '600'
            }}>
              {status.message}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default IntakeForm;

