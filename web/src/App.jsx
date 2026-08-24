import { createBrowserRouter, RouterProvider, Routes, Route, Link, Navigate, matchPath, useLocation, useParams } from 'react-router-dom';
import React, { useState, useEffect, useRef } from 'react';
import { getSession, getEffectiveRole } from './api/auth';
import { getTenantInfo } from './api/client';
import { shouldExposePlatformAdminNavigation } from './utils/tenantContext';
import PortalGateway from './components/PortalGateway';
import About from './components/About';
import Services from './components/Services';
import IntakeForm from './components/IntakeForm';
import ClientPortal from './components/ClientPortal';
import MyPets from './components/MyPets';
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
import PlatformAdminOnboarding from './components/PlatformAdminOnboarding';
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

export function TenantAdminRoute() {
  const { tenantSlug } = useParams();
  return <AdminDashboard key={tenantSlug} expectedTenantSlug={tenantSlug} />;
}

function TenantLandingRoute() {
  const { tenantSlug } = useParams();
  return <Navigate to={`/t/${encodeURIComponent(tenantSlug)}/admin`} replace />;
}

export function AppContent() {
  const [isPlatformAdmin, setIsPlatformAdmin] = useState(false);
  const [hasClientSession, setHasClientSession] = useState(false);
  const [tenantInfo, setTenantInfo] = useState(null);
  const location = useLocation();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const toggleRef = useRef(null);
  const closeBtnRef = useRef(null);
  
  const tenantRouteMatch = matchPath('/t/:tenantSlug/*', location.pathname);
  const isTenantRoute = Boolean(tenantRouteMatch);
  const isAdminRoute = isTenantRoute || location.pathname.startsWith('/admin') || location.pathname.startsWith('/platform-admin');

  // Close mobile drawer on navigation
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setIsMobileMenuOpen(false);
  }, [location.pathname]);

  // Lock body scroll when mobile drawer is open
  useEffect(() => {
    if (isMobileMenuOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [isMobileMenuOpen]);

  // Escape key support to close drawer
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        setIsMobileMenuOpen(false);
      }
    };
    if (isMobileMenuOpen) {
      window.addEventListener('keydown', handleKeyDown);
    }
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [isMobileMenuOpen]);

  // Auto-close mobile drawer when window is resized above mobile breakpoint (767px)
  useEffect(() => {
    const mediaQuery = window.matchMedia('(min-width: 768px)');
    const handleMediaChange = (e) => {
      if (e.matches) {
        setIsMobileMenuOpen(false);
      }
    };
    mediaQuery.addEventListener('change', handleMediaChange);
    return () => {
      mediaQuery.removeEventListener('change', handleMediaChange);
    };
  }, []);

  // Manage focus transitions when mobile drawer opens and closes
  useEffect(() => {
    if (isMobileMenuOpen) {
      closeBtnRef.current?.focus();
    } else {
      // Return focus to toggle, but avoid focusing on initial page render
      if (toggleRef.current && document.activeElement !== document.body) {
        toggleRef.current.focus();
      }
    }
  }, [isMobileMenuOpen]);

  // Focus trap inside the mobile drawer
  useEffect(() => {
    if (!isMobileMenuOpen) return;

    const drawerEl = document.getElementById('mobile-nav-drawer');
    if (!drawerEl) return;

    const focusableSelector = 'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';
    
    const handleKeyDown = (e) => {
      if (e.key !== 'Tab') return;

      const focusables = Array.from(drawerEl.querySelectorAll(focusableSelector))
        .filter(el => {
          return !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
        });

      if (focusables.length === 0) return;

      const firstEl = focusables[0];
      const lastEl = focusables[focusables.length - 1];

      // If activeElement is not inside the drawer, redirect focus to the first element
      if (!drawerEl.contains(document.activeElement)) {
        firstEl.focus();
        e.preventDefault();
        return;
      }

      if (e.shiftKey) {
        if (document.activeElement === firstEl) {
          lastEl.focus();
          e.preventDefault();
        }
      } else {
        if (document.activeElement === lastEl) {
          firstEl.focus();
          e.preventDefault();
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [isMobileMenuOpen]);

  useEffect(() => {
    const checkUserSession = async () => {
      try {
        const session = await getSession();
        if (session) {
          const payload = session.getIdToken().payload;
          const groups = payload['cognito:groups'] || [];
          const groupArray = Array.isArray(groups) ? groups : [groups];
          const normalizedGroups = groupArray.map(g => String(g).toLowerCase());
          if (normalizedGroups.includes('platform_admin')) {
            setIsPlatformAdmin(true);
          } else {
            setIsPlatformAdmin(false);
          }

          const role = getEffectiveRole(session);
          if (['client', 'owner', 'admin'].includes(role)) {
            setHasClientSession(true);
            return;
          }
        }
      } catch (e) {
        // Ignore
      }
      setIsPlatformAdmin(false);
      setHasClientSession(false);
    };
    checkUserSession();
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
    if (isAdminRoute && !isTenantRoute) {
      fetchTenant();
    } else {
      setTenantInfo(null);
    }
  }, [location.pathname, isAdminRoute, isTenantRoute]);

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
          {/* Desktop Navigation */}
          <nav className="main-nav desktop-only">
            {!isTenantRoute && <Link to="/" className="nav-link">Portal</Link>}
            {!isTenantRoute && hasClientSession && <Link to="/my-pets" className="nav-link">My Pets</Link>}
            {!isTenantRoute && <Link to="/my-bookings" className="nav-link">My Bookings</Link>}
            {shouldExposePlatformAdminNavigation(isTenantRoute, isPlatformAdmin) && (
              <Link to="/platform-admin" className="nav-link" style={{ fontWeight: 'bold', color: 'var(--primary)' }}>
                Platform Admin
              </Link>
            )}
            {!isTenantRoute && <Link to="/book" className="nav-link nav-cta">Request Care</Link>}
            <ThemeToggle />
          </nav>

          {/* Mobile Navigation Controls */}
          <div className="mobile-controls">
            <ThemeToggle />
            <button 
              ref={toggleRef}
              className={`hamburger-toggle ${isMobileMenuOpen ? 'open' : ''}`}
              onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
              aria-label="Toggle menu"
              aria-expanded={isMobileMenuOpen}
              aria-controls="mobile-nav-drawer"
            >
              <span className="hamburger-bar"></span>
              <span className="hamburger-bar"></span>
              <span className="hamburger-bar"></span>
            </button>
          </div>
        </div>

        {/* Mobile Navigation Drawer */}
        <div 
          id="mobile-nav-drawer"
          className={`mobile-drawer ${isMobileMenuOpen ? 'open' : ''}`}
          aria-hidden={!isMobileMenuOpen}
          role="dialog"
          aria-modal="true"
          aria-label="Navigation drawer"
        >
          <div className="mobile-drawer-backdrop" onClick={() => setIsMobileMenuOpen(false)}></div>
          <nav className="mobile-drawer-content">
            <div className="mobile-drawer-header">
              <span className="drawer-title">Navigation</span>
              <button 
                ref={closeBtnRef}
                className="close-drawer-button" 
                onClick={() => setIsMobileMenuOpen(false)}
                aria-label="Close menu"
              >
                &times;
              </button>
            </div>
            <div className="mobile-drawer-links">
              {!isTenantRoute && <Link to="/" className="drawer-link" onClick={() => setIsMobileMenuOpen(false)}>Portal</Link>}
              {!isTenantRoute && hasClientSession && <Link to="/my-pets" className="drawer-link" onClick={() => setIsMobileMenuOpen(false)}>My Pets</Link>}
              {!isTenantRoute && <Link to="/my-bookings" className="drawer-link" onClick={() => setIsMobileMenuOpen(false)}>My Bookings</Link>}
              {shouldExposePlatformAdminNavigation(isTenantRoute, isPlatformAdmin) && (
                <Link to="/platform-admin" className="drawer-link platform-admin-link" onClick={() => setIsMobileMenuOpen(false)}>
                  Platform Admin
                </Link>
              )}
              {!isTenantRoute && <Link to="/book" className="drawer-link drawer-cta" onClick={() => setIsMobileMenuOpen(false)}>Request Care</Link>}
              {isTenantRoute && (
                <Link to={location.pathname} className="drawer-link" onClick={() => setIsMobileMenuOpen(false)}>
                  Tenant Operations
                </Link>
              )}
            </div>
          </nav>
        </div>
      </header>

      <main className="content-area">
        <Routes>
          <Route path="/" element={<PortalGateway />} />
          <Route path="/about" element={<About />} />
          <Route path="/services" element={<Services />} />
          <Route path="/book" element={<IntakeForm />} />
          <Route path="/my-pets" element={<MyPets />} />
          <Route path="/my-bookings" element={<ClientPortal />} />
          <Route path="/admin" element={<AdminDashboard />} />
          <Route path="/admin/auth/callback" element={<GoogleCallback />} />
          <Route path="/t/:tenantSlug" element={<TenantLandingRoute />} />
          <Route path="/t/:tenantSlug/admin" element={<TenantAdminRoute />} />
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
          <Route path="/platform-admin/onboarding" element={
            <PlatformAdminGuard>
              <PlatformAdminOnboarding />
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

const router = createBrowserRouter([
  {
    path: '*',
    element: <AppContent />
  }
]);

function App() {
  return (
    <RouterProvider router={router} />
  );
}

export default App;

