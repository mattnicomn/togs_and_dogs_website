import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import PortalGateway from './components/PortalGateway';
import About from './components/About';
import Services from './components/Services';
import IntakeForm from './components/IntakeForm';
import ClientPortal from './components/ClientPortal';
import AdminDashboard from './components/AdminDashboard';
import GoogleCallback from './components/GoogleCallback';
import ThemeToggle from './components/ThemeToggle';
import './App.css';

function App() {
  return (
    <Router>
      <div className="app-container">
        <header className="main-header">
          <div className="header-content">
            <Link to="/" className="logo-link">
              <div className="logo">Tog&Dogs</div>
            </Link>
            <nav className="main-nav">
              <Link to="/" className="nav-link">Portal</Link>
              <Link to="/my-bookings" className="nav-link">My Bookings</Link>
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
          <div className="footer-content">
            <div className="footer-brand">
              <div className="logo">Tog&Dogs</div>
              <p>Premium, local pet care services providing peace of mind for you and personalized attention for your pets.</p>
              <div className="footer-badges">
                <span className="badge">Pet Tech CPR Certified</span>
                <span className="badge">First-Aid Trained</span>
              </div>
              <div className="usmh-attribution" style={{ marginTop: '24px', fontSize: '0.8rem', opacity: 0.7 }}>
                Powered by <strong>US Mission Hero</strong>
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
                <Link to="/" style={{ color: 'inherit', textDecoration: 'none' }}>Privacy Policy</Link>
                <Link to="/" style={{ color: 'inherit', textDecoration: 'none' }}>Terms of Service</Link>
              </div>
            </div>
          </div>
        </footer>
      </div>
    </Router>
  );
}


export default App;

