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
          <h2>Payment Cancelled</h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '1.05rem', margin: 0 }}>
            The payment process was not completed. No charges were made.
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
              <code style={{ marginLeft: '8px', fontSize: '0.95rem', wordBreak: 'break-all', color: 'var(--text-muted)' }}>
                {requestId}
              </code>
            </div>
            <div>
              <strong style={{ color: 'var(--text-primary)' }}>Status:</strong>
              <span className="badge" style={{ marginLeft: '8px', textTransform: 'none', padding: '2px 10px', fontSize: '0.8rem', backgroundColor: 'rgba(214, 73, 51, 0.1)', color: 'var(--warning-color)' }}>
                Unpaid
              </span>
            </div>
          </div>
          <div style={{ textAlign: 'left', width: '100%' }}>
            <h4 style={{ marginBottom: '8px', fontFamily: 'var(--sans)', fontSize: '1rem', fontWeight: 'bold' }}>Need Help?</h4>
            <p style={{ margin: 0, color: 'var(--text-secondary)', fontSize: '0.95rem' }}>
              If you experienced an issue with payment, you can try again from the My Bookings portal or contact us directly at <a href="mailto:support@toganddogs.com" style={{ color: 'var(--primary)', fontWeight: '600' }}>support@toganddogs.com</a> for assistance.
            </p>
          </div>
          <div style={{ display: 'flex', gap: '16px', width: '100%', marginTop: '16px' }}>
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
