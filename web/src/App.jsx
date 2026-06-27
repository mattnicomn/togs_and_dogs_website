import { BrowserRouter as Router, Routes, Route, Link, Navigate, useLocation } from 'react-router-dom';
import React, { useState, useEffect } from 'react';
import { getSession } from './api/auth';
import { getTenantInfo } from './api/client';
import PortalGateway from './components/PortalGateway';
import About from './components/About';
import Services from './components/Services';
import IntakeForm from './components/IntakeForm';
import ClientPortal from './components/ClientPortal';
import AdminDashboard from './components/AdminDashboard';
import GoogleCallback from './components/GoogleCallback';
import ThemeToggle from './components/ThemeToggle';
import TermsOfUse from './components/TermsOfUse';
import PrivacyPolicy from './components/PrivacyPolicy';
import PaymentSuccess from './components/PaymentSuccess';
import PaymentCancel from './components/PaymentCancel';
import PlatformAdmin from './components/PlatformAdmin';
import PlatformTenantDetail from './components/PlatformTenantDetail';
import PlatformAuditLog from './components/PlatformAuditLog';
import usmhLogo from './assets/usmh-logo.png';
import './App.css';

// Route guard: check Cognito groups for platform_admin
function PlatformAdminGuard({ children }) {
  const [loading, setLoading] = useState(true);
  const [authorized, setAuthorized] = useState(false);

  useEffect(() => {
    const verifyAccess = async () => {
      try {
        const session = await getSession();
        if (session) {
          const payload = session.getIdToken().payload;
          const groups = payload['cognito:groups'] || [];
          const groupArray = Array.isArray(groups) ? groups : [groups];
          const normalizedGroups = groupArray.map(g => String(g).toLowerCase());
          if (normalizedGroups.includes('platform_admin')) {
            setAuthorized(true);
          }
        }
      } catch (e) {
        console.error('Guard authorization verification failed:', e);
      } finally {
        setLoading(false);
      }
    };
    verifyAccess();
  }, []);

  if (loading) {
    return (
      <div className="platform-loading-container" style={{ minHeight: '100vh', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
        <div className="platform-spinner"></div>
        <p style={{ marginLeft: '12px' }}>Verifying permissions...</p>
      </div>
    );
  }

  if (!authorized) {
    // Redirect to login or staff dashboard
    return <Navigate to="/admin" replace />;
  }

  return children;
}

function AppContent() {
  const [isPlatformAdmin, setIsPlatformAdmin] = useState(false);
  const [tenantInfo, setTenantInfo] = useState(null);
  const location = useLocation();
  
  const isAdminRoute = location.pathname.startsWith('/admin') || location.pathname.startsWith('/platform-admin');

  useEffect(() => {
    const checkPlatformAdmin = async () => {
      try {
        const session = await getSession();
        if (session) {
          const payload = session.getIdToken().payload;
          const groups = payload['cognito:groups'] || [];
          const groupArray = Array.isArray(groups) ? groups : [groups];
          const normalizedGroups = groupArray.map(g => String(g).toLowerCase());
          if (normalizedGroups.includes('platform_admin')) {
            setIsPlatformAdmin(true);
            return;
          }
        }
      } catch (e) {
        // Ignore
      }
      setIsPlatformAdmin(false);
    };
    checkPlatformAdmin();
  }, [location.pathname]);

  useEffect(() => {
    const fetchTenant = async () => {
      try {
        const session = await getSession();
        if (session) {
          const info = await getTenantInfo();
          setTenantInfo(info);
        } else {
          setTenantInfo(null);
        }
      } catch (e) {
        console.error('Failed to fetch tenant info for App shell:', e);
        setTenantInfo(null);
      }
    };
    if (isAdminRoute) {
      fetchTenant();
    } else {
      setTenantInfo(null);
    }
  }, [location.pathname, isAdminRoute]);

  return (
    <div className="app-container">
      <header className="main-header">
        <div className="header-content">
          <Link 
            to={isAdminRoute ? "#" : "/"} 
            className="logo-link" 
            style={{ pointerEvents: isAdminRoute ? 'none' : 'auto' }}
          >
            <div className="logo">
              {isAdminRoute 
                ? `${tenantInfo?.display_name || "Pet Care Admin"}: A Pet Business Platform` 
                : "Tog&Dogs"}
            </div>
          </Link>
          <nav className="main-nav">
            <Link to="/" className="nav-link">Portal</Link>
            <Link to="/my-bookings" className="nav-link">My Bookings</Link>
            {isPlatformAdmin && (
              <Link to="/platform-admin" className="nav-link" style={{ fontWeight: 'bold', color: 'var(--primary)' }}>
                Platform Admin
              </Link>
            )}
            <Link to="/book" className="nav-link nav-cta">Request Care</Link>
            <ThemeToggle />
          </nav>
        </div>
      </header>

      <main className="content-area">
        <Routes>
          <Route path="/" element={<PortalGateway />} />
          <Route path="/about" element={<About />} />
          <Route path="/services" element={<Services />} />
          <Route path="/book" element={<IntakeForm />} />
          <Route path="/my-bookings" element={<ClientPortal />} />
          <Route path="/admin" element={<AdminDashboard />} />
          <Route path="/admin/auth/callback" element={<GoogleCallback />} />
          <Route path="/terms" element={<TermsOfUse />} />
          <Route path="/privacy" element={<PrivacyPolicy />} />
          <Route path="/booking/:requestId/success" element={<PaymentSuccess />} />
          <Route path="/booking/:requestId/cancel" element={<PaymentCancel />} />
          
          {/* Platform Admin Console Routes */}
          <Route path="/platform-admin" element={
            <PlatformAdminGuard>
              <PlatformAdmin />
            </PlatformAdminGuard>
          } />
          <Route path="/platform-admin/tenants/:companyId" element={
            <PlatformAdminGuard>
              <PlatformTenantDetail />
            </PlatformAdminGuard>
          } />
          <Route path="/platform-admin/audit" element={
            <PlatformAdminGuard>
              <PlatformAuditLog />
            </PlatformAdminGuard>
          } />

          <Route path="*" element={
            <div className="section error-page">
              <div className="container">
                <h2>404 - Page Not Found</h2>
                <p>We couldn't find the page you're looking for.</p>
                <Link to="/" className="button-primary" style={{ marginTop: '24px' }}>Back to Portal</Link>
              </div>
            </div>
          } />
        </Routes>
      </main>

      <footer className="main-footer">
        {isAdminRoute ? (
          <div className="footer-bottom">
            <div className="container" style={{ display: 'flex', justifyContent: 'space-between', width: '100%', flexWrap: 'wrap', gap: '16px' }}>
              <p>&copy; 2026 {tenantInfo?.display_name || "Pet Care Admin"}. Powered by usmissionhero.</p>
              <div className="legal-links" style={{ display: 'flex', gap: '24px' }}>
                <Link to="/privacy" style={{ color: 'inherit', textDecoration: 'none' }}>Privacy Policy</Link>
                <Link to="/terms" style={{ color: 'inherit', textDecoration: 'none' }}>Terms of Service</Link>
              </div>
            </div>
          </div>
        ) : (
          <>
            <div className="footer-content">
              <div className="footer-brand">
                <div className="logo">Tog&Dogs</div>
                <p>Premium, local pet care services providing peace of mind for you and personalized attention for your pets.</p>
                <div className="footer-badges">
                  <span className="badge">Pet Tech CPR Certified</span>
                  <span className="badge">First-Aid Trained</span>
                </div>
                <div className="usmh-attribution" style={{ marginTop: '24px', fontSize: '0.8rem', opacity: 0.7, display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <img src={usmhLogo} alt="US Mission Hero logo" style={{ height: '24px', width: 'auto', objectFit: 'contain' }} />
                  <span>Powered by <strong>US Mission Hero</strong></span>
                </div>
              </div>
              <div className="footer-links">
                <h4>Portal</h4>
                <Link to="/my-bookings">Client Login</Link>
                <Link to="/book">Request Care</Link>
                <Link to="/admin">Staff Portal</Link>
              </div>
              <div className="footer-links">
                <h4>External</h4>
                <a href="https://toganddogs.com">Main Website</a>
                <Link to="/about">About Us</Link>
                <Link to="/services">Services List</Link>
              </div>
            </div>
            <div className="footer-bottom">
              <div className="container" style={{ display: 'flex', justifyContent: 'space-between', width: '100%', flexWrap: 'wrap', gap: '16px' }}>
                <p>&copy; 2026 Tog and Dogs Pet Sitting Services</p>
                <div className="legal-links" style={{ display: 'flex', gap: '24px' }}>
                  <Link to="/privacy" style={{ color: 'inherit', textDecoration: 'none' }}>Privacy Policy</Link>
                  <Link to="/terms" style={{ color: 'inherit', textDecoration: 'none' }}>Terms of Service</Link>
                </div>
              </div>
            </div>
          </>
        )}
      </footer>
    </div>
  );
}

function App() {
  return (
    <Router>
      <AppContent />
    </Router>
  );
}

export default App;

