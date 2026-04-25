import { Link } from 'react-router-dom';
import { siteContent } from '../config/siteContent';


const Home = () => {
  return (
    <div className="home-page">
      {/* Hero Section */}
      <section className="section hero">
        <div className="container">
          <span className="badge">Professional Care for Your Best Friend</span>
          <h1>Quality Pet Care, <br/>Total Peace of Mind</h1>
          <p className="hero-subtext">
            Reliable, certified pet sitting and dog walking services from {siteContent.brandName}. 
            Whether you're at work or on vacation, we treat your pets like family.
          </p>
          <div className="hero-actions">
            <Link to="/book" className="button-primary">
              Get Started
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="5" y1="12" x2="19" y2="12"></line><polyline points="12 5 19 12 12 19"></polyline></svg>
            </Link>
            <Link to="/my-bookings" className="button-secondary">Client Portal</Link>
          </div>
          <p style={{ marginTop: '24px', fontSize: '0.9rem', color: 'var(--text-muted)' }}>
            <strong>New Client?</strong> Start with a free Meet & Greet.
          </p>
        </div>
      </section>

      {/* Trust Row */}
      <section className="trust-row">
        <div className="container">
          <div className="grid grid-3">
            <div className="trust-item">
              <div className="trust-icon">🛡️</div>
              <h3>Insured & Bonded</h3>
              <p>Your pet and home are fully covered by our comprehensive insurance policy.</p>
            </div>
            <div className="trust-item">
              <div className="trust-icon">📱</div>
              <h3>Real-Time Updates</h3>
              <p>Receive photos and visit notes directly to your phone after every visit.</p>
            </div>
            <div className="trust-item">
              <div className="trust-icon">❤️</div>
              <h3>Certified Care</h3>
              <p>Our team is CPR and First-Aid trained for maximum safety and care.</p>
            </div>
          </div>
        </div>
      </section>

      {/* Services Section */}
      <section className="section services" id="services">
        <div className="container">
          <span className="badge">What We Do</span>
          <h2 style={{ marginTop: '16px' }}>Tailored Services for Every Pet</h2>
          <div className="grid grid-3" style={{ marginTop: '48px' }}>
            {siteContent.services.map((service) => (
              <div key={service.id} className="card service-card">
                <div className="service-emoji">{service.emoji}</div>
                <h3>{service.title}</h3>
                <p>{service.description}</p>
                <div className="price-tag">{service.price} / {service.unit.split(' ')[1]}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* How it Works */}
      <section className="section how-it-works" id="how-it-works" style={{ background: 'var(--bg-muted)' }}>
        <div className="container">
          <h2>Getting Started</h2>
          <p className="subtitle" style={{ maxWidth: '600px', margin: '16px auto 48px' }}>We've made it simple to join the {siteContent.brandName} family.</p>
          <div className="steps-container">
            <div className="step">
              <div className="step-number">1</div>
              <h3>Request Service</h3>
              <p>Tell us about your pet's needs through our simple intake form.</p>
            </div>
            <div className="step">
              <div className="step-number">2</div>
              <h3>Meet & Greet</h3>
              <p>We'll visit you at home to ensure we're the perfect fit for your pet.</p>
            </div>
            <div className="step">
              <div className="step-number">3</div>
              <h3>Relax & Reassure</h3>
              <p>Book your visits and enjoy peace of mind with regular photo updates.</p>
            </div>
          </div>
          <Link to="/book" className="button-primary" style={{ marginTop: '48px' }}>Book Your Meet & Greet</Link>
        </div>
      </section>

      {/* Areas We Serve */}
      <section className="section service-area" id="areas">
        <div className="container">
          <span className="badge">Where We Are</span>
          <h2 style={{ marginTop: '16px' }}>Service Areas</h2>
          <p className="subtitle" style={{ maxWidth: '600px', margin: '16px auto 48px' }}>
            We are currently accepting new clients in the following areas. Not in our zone? Contact us anyway—we're expanding!
          </p>
          <div className="grid grid-3" style={{ textAlign: 'left' }}>
            <div className="area-list">
              <h4>Neighborhoods</h4>
              <ul style={{ listStyle: 'none', padding: 0, marginTop: '16px', color: 'var(--text-muted)' }}>
                {siteContent.serviceAreas.neighborhoods.map((area, idx) => (
                  <li key={idx} style={{ marginBottom: '8px' }}>📍 {area.name} ({area.status})</li>
                ))}
              </ul>
            </div>
            <div className="area-list">
              <h4>Zip Codes (Sample)</h4>
              <p style={{ marginTop: '16px', color: 'var(--text-muted)', lineHeight: '1.8' }}>
                Currently serving select homes in: {siteContent.serviceAreas.zipCodes.join(', ')}. <br/>
                <em>*Subject to sitter availability.</em>
              </p>
            </div>
            <div className="area-list">
              <h4>Availability</h4>
              <p style={{ marginTop: '16px', color: 'var(--text-muted)' }}>
                {siteContent.serviceAreas.availability}
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Testimonials */}
      <section className="section testimonials" id="testimonials" style={{ background: 'var(--bg-warm)' }}>
        <div className="container">
          <span className="badge">Kind Words</span>
          <h2 style={{ marginTop: '16px' }}>What Our Clients Say</h2>
          <div className="grid grid-3" style={{ marginTop: '48px' }}>
            {siteContent.testimonials.map((t, idx) => (
              <div key={idx} className="card testimonial-card">
                <p>"{t.text}"</p>
                <div className="testimonial-author">— {t.author}</div>
              </div>
            ))}
          </div>
          <p style={{ marginTop: '32px', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            <em>Real client reviews coming soon!</em>
          </p>
        </div>
      </section>


      {/* FAQ Section */}
      <section className="section faq" id="faq">
        <div className="container" style={{ maxWidth: '900px' }}>
          <span className="badge">Questions?</span>
          <h2 style={{ marginTop: '16px' }}>General Information</h2>
          <div className="faq-grid" style={{ marginTop: '48px', textAlign: 'left' }}>
            <div style={{ marginBottom: '32px' }}>
              <h4>What is a Meet & Greet?</h4>
              <p style={{ color: 'var(--text-muted)', marginTop: '8px' }}>
                It's a free introductory visit where we meet you and your pet to ensure we're the perfect fit before any service begins.
              </p>
            </div>
            <div style={{ marginBottom: '32px' }}>
              <h4>How do you access my home?</h4>
              <p style={{ color: 'var(--text-muted)', marginTop: '8px' }}>
                We discuss entry methods (lockboxes, codes, or keys) during the Meet & Greet. Safety and security are our top priorities.
              </p>
            </div>
            <div style={{ marginBottom: '32px' }}>
              <h4>Will I get updates during the visit?</h4>
              <p style={{ color: 'var(--text-muted)', marginTop: '8px' }}>
                Yes! Every visit includes a status update and photo, accessible via your client portal.
              </p>
            </div>
            <div style={{ marginBottom: '32px' }}>
              <h4>Can you administer medication?</h4>
              <p style={{ color: 'var(--text-muted)', marginTop: '8px' }}>
                We can provide basic medication support. Please discuss your pet's specific requirements during the onboarding process.
              </p>
            </div>
            <div style={{ marginBottom: '32px' }}>
              <h4>What is your cancellation policy?</h4>
              <p style={{ color: 'var(--text-muted)', marginTop: '8px' }}>
                We typically request 24 hours notice. Detailed policy terms will be provided during your initial setup.
              </p>
            </div>
          </div>
        </div>
      </section>


      <style dangerouslySetInnerHTML={{ __html: `
        .home-page {
          display: flex;
          flex-direction: column;
        }
        .hero {
          padding: 120px 24px;
          background: linear-gradient(135deg, var(--bg-surface) 0%, var(--bg-warm) 100%);
        }
        .hero h1 {
          max-width: 800px;
          margin: 24px auto;
        }
        .hero-subtext {
          font-size: 1.25rem;
          color: var(--text-muted);
          max-width: 600px;
          margin: 0 auto 40px;
        }
        .hero-actions {
          display: flex;
          gap: 16px;
          justify-content: center;
          flex-wrap: wrap;
        }
        .trust-row {
          padding: 60px 24px;
          background: var(--primary);
          color: white;
        }
        .trust-row h3 {
          color: white;
          margin: 16px 0 8px;
        }
        .trust-row p {
          color: hsla(0, 0%, 100%, 0.8);
          font-size: 0.95rem;
        }
        .trust-icon {
          font-size: 2.5rem;
        }
        .service-emoji {
          font-size: 3rem;
          margin-bottom: 20px;
        }
        .price-tag {
          margin-top: 20px;
          font-weight: 700;
          color: var(--primary);
          font-size: 1.1rem;
        }
        .steps-container {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 40px;
          margin-top: 20px;
        }
        .step-number {
          width: 50px;
          height: 50px;
          background: var(--accent);
          color: white;
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 1.5rem;
          font-weight: 800;
          margin: 0 auto 20px;
        }
        .testimonial-card p {
          font-style: italic;
          font-size: 1.1rem;
          margin-bottom: 16px;
        }
        .testimonial-author {
          font-weight: 700;
          color: var(--primary);
          font-size: 0.9rem;
        }
        .faq-grid {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 40px;
        }
        @media (max-width: 768px) {
          .steps-container, .faq-grid {
            grid-template-columns: 1fr;
          }
        }
      `}} />
    </div>
  );
};


export default Home;
