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
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <strong style={{ color: 'var(--text-primary)' }}>Status:</strong>
              <span className="badge" style={{ textTransform: 'none', padding: '2px 10px', fontSize: '0.8rem', backgroundColor: 'rgba(74, 124, 89, 0.1)', color: 'var(--success-color)' }}>
                Paid
              </span>
            </div>
          </div>
          <div style={{ textAlign: 'left', width: '100%' }}>
            <h4 style={{ marginBottom: '8px', fontFamily: 'var(--sans)', fontSize: '1rem', fontWeight: 'bold' }}>Next Steps:</h4>
            <ul style={{ margin: 0, paddingLeft: '20px', color: 'var(--text-secondary)', fontSize: '0.95rem', display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <li>A confirmation receipt from Stripe has been sent to your email.</li>
              <li>Our team is preparing for your pet's visits, and you will receive scheduling and visit updates as they are finalized.</li>
              <li>Please note that payment confirms your booking request; visits and staff assignments are officially scheduled once confirmed by our administration.</li>
            </ul>
            <p style={{ marginTop: '16px', fontSize: '0.9rem', color: 'var(--text-secondary)', margin: '16px 0 0 0' }}>
              Questions? Reach out to us at <span style={{ fontWeight: '500', color: 'var(--primary)' }}>[billing/support email to be confirmed]</span>.
            </p>
          </div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', width: '100%', textAlign: 'center' }}>
            Request Reference: {requestId}
          </div>
          <div style={{ display: 'flex', gap: '16px', width: '100%', marginTop: '8px' }}>
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
