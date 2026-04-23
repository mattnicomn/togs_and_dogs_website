import { useState } from 'react';
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
      setStatus({ type: 'success', message: `Great! We've received your request. Support ID: ${result.request_id}` });
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
      <div className="intake-header">
        <h1>Your best friend's<br/>new friend.</h1>
        <p className="subtitle">Professional, certified pet sitting and walking services in Warner Robins. We treat every pet like family.</p>
      </div>

      <div className="card intake-card">
        <h2>Book Your Visit</h2>
        <p className="card-description">New to Tog & Dogs? We'll reach out to schedule a free meet-and-greet after you submit your booking request.</p>
        
        <form onSubmit={handleSubmit} className="premium-form">
          <div className="field-group">
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
              <option value="PET_SITTING">Pet Sitting (Vacation/Check-ins)</option>
              <option value="DOG_WALKING">Daily Dog Walking</option>
              <option value="OVERNIGHT">Overnight Stays</option>
            </select>
          </div>

          <div className="field-group">
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

          <div className="field-group">
            <div className="field">
              <label>Visit Window</label>
              <select 
                value={formData.visit_window}
                onChange={(e) => setFormData({...formData, visit_window: e.target.value})}
              >
                <option value="MORNING">Morning (7 AM - 10 AM)</option>
                <option value="MIDDAY">Midday (11 AM - 2 PM)</option>
                <option value="AFTERNOON">Afternoon (3 PM - 6 PM)</option>
                <option value="EVENING">Evening (7 PM - 10 PM)</option>
                <option value="ANYTIME">Anytime (Best Effort)</option>
              </select>
            </div>
            <div className="field">
              <label>Preferred Exact Time</label>
              <input 
                type="text" 
                value={formData.preferred_time} 
                onChange={(e) => setFormData({...formData, preferred_time: e.target.value})} 
                placeholder="e.g. 12:30 PM"
              />
            </div>
          </div>

          <div className="field">
            <label>Timing / Arrival Notes</label>
            <input 
              type="text" 
              value={formData.timing_notes} 
              onChange={(e) => setFormData({...formData, timing_notes: e.target.value})} 
              placeholder="e.g. Please hide key under mat"
            />
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
            <label>Tell us about your furry friends (Special needs, routines, etc.)</label>
            <textarea 
              rows="4"
              value={formData.pet_info} 
              onChange={(e) => setFormData({...formData, pet_info: e.target.value})} 
              placeholder="Names, breeds, special needs, or favorite treats..."
            />
          </div>

          <button type="submit" className="button-primary">Request Booking</button>
        </form>

        {status.message && (
          <div className={`status-msg ${status.type}`}>
            {status.message}
          </div>
        )}
      </div>
    </div>
  );
};

export default IntakeForm;
