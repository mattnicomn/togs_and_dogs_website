import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
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
            <div className="logo">Tog & Dogs</div>
            <nav className="main-nav">
              <Link to="/" className="nav-link">Book Now</Link>
              <Link to="/my-bookings" className="nav-link">My Bookings</Link>
              <Link to="/admin" className="nav-link nav-admin">Staff Portal</Link>
              <ThemeToggle />
            </nav>
          </div>
        </header>

        <main className="content-area">
          <Routes>
            <Route path="/" element={<IntakeForm />} />
            <Route path="/my-bookings" element={<ClientPortal />} />
            <Route path="/admin" element={<AdminDashboard />} />
            <Route path="/admin/auth/callback" element={<GoogleCallback />} />
            <Route path="*" element={
              <div className="card error-page">
                <h2>404 - Not Found</h2>
                <p>We couldn't find the page you're looking for.</p>
                <Link to="/" className="button-primary">Go Home</Link>
              </div>
            } />
          </Routes>
        </main>

        <footer className="main-footer">
          <div className="footer-content">
            <p>&copy; 2026 Tog and Dogs Pet Sitting Services</p>
            <div className="footer-badges">
              <span className="badge">Pet Tech CPR Certified</span>
              <span className="badge">First-Aid Trained</span>
            </div>
          </div>
        </footer>
      </div>
    </Router>
  );
}

export default App;
