import React from 'react';
import { Link } from 'react-router-dom';

const About = () => {
  return (
    <div className="about-page">
      <section className="section">
        <div className="container" style={{ maxWidth: '800px' }}>
          <span className="badge">Our Story</span>
          <h1>Passion for Pets, <br/>Driven by Care</h1>
          <p style={{ fontSize: '1.2rem', marginTop: '32px' }}>
            At Tog and Dogs, we believe that pets aren't just animals—they're family. 
            Our mission is to provide the highest standard of professional care, giving 
            pet parents the freedom to work or travel without worry.
          </p>

          <div style={{ textAlign: 'left', marginTop: '64px' }}>
            <h3>Our Values</h3>
            <div className="grid" style={{ gridTemplateColumns: '1fr 1fr', gap: '32px', marginTop: '24px' }}>
              <div>
                <h4>Trust & Transparency</h4>
                <p>We provide detailed updates and photos after every visit, so you're always in the loop.</p>
              </div>
              <div>
                <h4>Safety First</h4>
                <p>All our sitters are Pet Tech CPR and First-Aid trained and fully insured.</p>
              </div>
              <div>
                <h4>Local Love</h4>
                <p>We're proud to be a part of our local community and treat every neighbor like a friend.</p>
              </div>
              <div>
                <h4>Professionalism</h4>
                <p>We take our commitment seriously, showing up on time and following your routines to the letter.</p>
              </div>
            </div>
          </div>

          <div style={{ marginTop: '80px' }}>
            <h2>Experience the difference</h2>
            <Link to="/book" className="button-primary" style={{ marginTop: '24px' }}>Join the Tog and Dogs Family</Link>
          </div>
        </div>
      </section>
    </div>
  );
};

export default About;
