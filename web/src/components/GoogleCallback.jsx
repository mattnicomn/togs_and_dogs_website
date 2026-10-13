import { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { completeGoogleAuth } from '../api/client';

const GoogleCallback = () => {
    const location = useLocation();
    const navigate = useNavigate();

    // Derive the code/state once from the callback URL. Seeding the initial
    // status from these params lets the "missing parameters" case be the initial
    // render state rather than a synchronous setState inside the effect
    // (react-hooks/set-state-in-effect). Lazy initializers run once per mount.
    const [{ code, state }] = useState(() => {
        const params = new URLSearchParams(location.search);
        return { code: params.get('code'), state: params.get('state') };
    });
    const [status, setStatus] = useState(() => (code && state ? 'processing' : 'error'));
    const [, setError] = useState(() => (code && state ? null : 'Missing code or state in callback.'));

    // Complete the OAuth exchange on mount when both parameters are present. The
    // async worker is defined INSIDE the effect so it has no forward reference
    // (react-hooks/immutability) and the dependency array stays honest
    // (react-hooks/exhaustive-deps). A per-run `active` flag plus timeout cleanup
    // prevent a late completion or the 3-second redirect from updating state or
    // navigating after unmount. Note: `active` guards state/navigation only — it
    // does not cancel the in-flight completeGoogleAuth request, and the component
    // holds no persistent "already exchanged" state, so this does not dedup a
    // genuine double-mount exchange.
    useEffect(() => {
        if (!(code && state)) {
            return undefined;
        }
        let active = true;
        let redirectTimer = null;
        const runExchange = async () => {
            try {
                await completeGoogleAuth(code, state);
                if (!active) return;
                setStatus('success');
                redirectTimer = setTimeout(() => {
                    navigate('/admin');
                }, 3000);
            } catch (err) {
                console.error("Token exchange failed", err);
                if (!active) return;
                setStatus('error');
                setError(err.message);
            }
        };
        runExchange();
        return () => {
            active = false;
            if (redirectTimer) clearTimeout(redirectTimer);
        };
    }, [code, state, navigate]);

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
