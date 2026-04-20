import { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { completeGoogleAuth } from '../api/client';

const GoogleCallback = () => {
    const [status, setStatus] = useState('processing');
    const [error, setError] = useState(null);
    const navigate = useNavigate();
    const location = useLocation();

    useEffect(() => {
        const params = new URLSearchParams(location.search);
        const code = params.get('code');
        const state = params.get('state');

        if (code && state) {
            handleComplete(code, state);
        } else {
            setStatus('error');
            setError('Missing code or state in callback.');
        }
    }, [location, navigate]);

    const handleComplete = async (code, state) => {
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
                        <p>Your Google Calendar is now connected to Tog and Dogs.</p>
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
