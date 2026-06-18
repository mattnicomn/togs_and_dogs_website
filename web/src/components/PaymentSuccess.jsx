import { useParams, Link } from 'react-router-dom';
import React from 'react';

function PaymentSuccess() {
  const { requestId } = useParams();

  return (
    <div className="section">
      <div className="container" style={{ maxWidth: '600px' }}>
        <div className="card" style={{ padding: '48px 32px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '24px' }}>
          <div style={{
            width: '80px',
            height: '80px',
            borderRadius: '50%',
            backgroundColor: 'rgba(74, 124, 89, 0.1)',
            color: 'var(--success-color)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '3rem',
            marginBottom: '8px'
          }}>
            ✓
          </div>
          <h2>Payment Received!</h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '1.05rem', margin: 0 }}>
            Thank you! Your payment has been successfully processed and recorded.
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
            <div style={{ marginBottom: '8px' }}>
              <strong style={{ color: 'var(--text-primary)' }}>Request ID:</strong>
              <code style={{ marginLeft: '8px', fontSize: '0.95rem', wordBreak: 'break-all', color: 'var(--primary)' }}>
                {requestId}
              </code>
            </div>
            <div>
              <strong style={{ color: 'var(--text-primary)' }}>Status:</strong>
              <span className="badge" style={{ marginLeft: '8px', textTransform: 'none', padding: '2px 10px', fontSize: '0.8rem', backgroundColor: 'rgba(74, 124, 89, 0.1)', color: 'var(--success-color)' }}>
                Paid
              </span>
            </div>
          </div>
          <div style={{ textAlign: 'left', width: '100%' }}>
            <h4 style={{ marginBottom: '8px', fontFamily: 'var(--sans)', fontSize: '1rem', fontWeight: 'bold' }}>Next Steps:</h4>
            <ul style={{ margin: 0, paddingLeft: '20px', color: 'var(--text-secondary)', fontSize: '0.95rem', display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <li>Our team is preparing for your pet's visits.</li>
              <li>Your booking details are now being finalized with our staff.</li>
              <li>You will receive an email confirmation once scheduling is complete.</li>
            </ul>
          </div>
          <div style={{ display: 'flex', gap: '16px', width: '100%', marginTop: '16px' }}>
            <Link to="/my-bookings" className="button-primary" style={{ flex: 1, padding: '14px' }}>
              Go to My Bookings
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}

export default PaymentSuccess;
