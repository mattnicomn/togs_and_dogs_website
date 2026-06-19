import { useParams, Link } from 'react-router-dom';
import React from 'react';

function PaymentCancel() {
  const { requestId } = useParams();

  return (
    <div className="section">
      <div className="container" style={{ maxWidth: '600px' }}>
        <div className="card" style={{ padding: '48px 32px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '24px' }}>
          <div style={{
            width: '80px',
            height: '80px',
            borderRadius: '50%',
            backgroundColor: 'rgba(214, 73, 51, 0.1)',
            color: 'var(--warning-color)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '3.5rem',
            fontWeight: '300',
            lineHeight: '1',
            marginBottom: '8px'
          }}>
            ×
          </div>
          <h2>Payment Not Completed</h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '1.05rem', margin: 0 }}>
            No charges were made. Your booking request remains active.
          </p>
          <div style={{
            backgroundColor: 'var(--bg-muted)',
            padding: '16px 20px',
            borderRadius: 'var(--radius-md)',
            width: '100%',
            boxSizing: 'border-box',
            textAlign: 'left',
            fontSize: '0.9rem',
            border: '1px solid var(--border-soft)'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <strong style={{ color: 'var(--text-primary)' }}>Status:</strong>
              <span className="badge" style={{ textTransform: 'none', padding: '2px 10px', fontSize: '0.8rem', backgroundColor: 'rgba(214, 73, 51, 0.1)', color: 'var(--warning-color)' }}>
                Unpaid
              </span>
            </div>
          </div>
          <div style={{ textAlign: 'left', width: '100%' }}>
            <h4 style={{ marginBottom: '8px', fontFamily: 'var(--sans)', fontSize: '1rem', fontWeight: 'bold' }}>Next Steps:</h4>
            <ul style={{ margin: 0, paddingLeft: '20px', color: 'var(--text-secondary)', fontSize: '0.95rem', display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <li>Your booking request is still active and is being held.</li>
              <li>Please use the secure payment link sent to your email to complete the payment.</li>
              <li>If the payment link has expired or you need a new one sent, please contact support.</li>
            </ul>
            <p style={{ marginTop: '16px', fontSize: '0.9rem', color: 'var(--text-secondary)', margin: '16px 0 0 0' }}>
              Need help? Reach out to us at <a href="mailto:support@usmissionhero.com" style={{ color: 'var(--primary)', fontWeight: '600', textDecoration: 'none' }}>support@usmissionhero.com</a>.
            </p>
          </div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', width: '100%', textAlign: 'center' }}>
            Request Reference: {requestId}
          </div>
          <div style={{ display: 'flex', gap: '16px', width: '100%', marginTop: '8px' }}>
            <Link to="/my-bookings" className="button-secondary" style={{ flex: 1, padding: '12px' }}>
              Return to My Bookings
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}

export default PaymentCancel;
