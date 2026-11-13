import { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { completeGoogleAuth } from '../api/client';

const GoogleCallback = () => {
    const [completionStatus, setStatus] = useState('processing');
    // The error detail is recorded but (as before) not rendered.
    const [, setError] = useState(null);
    const navigate = useNavigate();
    const location = useLocation();

    // A callback without both `code` and `state` is invalid: it is shown as an error
    // and never reaches the token exchange (derived during render, no effect needed).
    const callbackParams = new URLSearchParams(location.search);
    const hasCallbackParams = Boolean(callbackParams.get('code') && callbackParams.get('state'));
    const status = hasCallbackParams ? completionStatus : 'error';

    useEffect(() => {
        const params = new URLSearchParams(location.search);
        const code = params.get('code');
        const state = params.get('state');
        if (!(code && state)) return;

        // Only used by this effect, so it is declared here. State is set only after
        // the token exchange settles.
        const handleComplete = async () => {
            try {
                await completeGoogleAuth(code, state);
                setStatus('success');
                setTimeout(() => {
                    navigate('/admin');
                }, 3000);
            } catch (err) {
                console.error("Token exchange failed", err);
                setStatus('error');
                setError(err.message);
            }
        };
        handleComplete();
    }, [location, navigate]);

    return (
        <div className="section google-callback-section">
            <div className="premium-card text-center">
                {status === 'processing' && (
                    <>
                        <div className="spinner"></div>
                        <h2>Finishing Connection...</h2>
                        <p>Validating your Google Calendar link.</p>
                    </>
                )}
                
                {status === 'success' && (
                    <>
                        <div className="success-icon">✅</div>
                        <h2>Successfully Linked!</h2>
                        <p>Your Google Calendar is now connected to your pet care operations portal.</p>
                        <p className="sub-text">Redirecting you back to the dashboard...</p>
                    </>
                )}

                {status === 'error' && (
                    <>
                        <div className="error-icon">❌</div>
                        <h2>Connection Failed</h2>
                        <p>We couldn't verify the authorization code. Please try again.</p>
                        <button onClick={() => navigate('/admin')} className="button-primary">
                            Back to Dashboard
                        </button>
                    </>
                )}
            </div>
        </div>
    );
};

export default GoogleCallback;
