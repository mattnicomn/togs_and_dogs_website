import { Link } from 'react-router-dom';
import { siteContent } from '../config/siteContent';


const Services = () => {
  return (
    <div className="services-page">
      <section className="section">
        <div className="container">
          <span className="badge">Our Expertise</span>
          <h1>Comprehensive Pet Care</h1>
          <p className="subtitle" style={{ maxWidth: '600px', margin: '24px auto' }}>
            {siteContent.brandName} offers a variety of services to meet the unique needs of your pets and your schedule.
          </p>

          <div className="grid grid-3" style={{ marginTop: '64px' }}>
            {siteContent.services.map((service) => (
              <div key={service.id} className="card service-detail-card">
                <div className="media-placeholder">{service.emoji}</div>
                <h3>{service.title}</h3>
                <p>{service.description}</p>
                <div className="price-block">
                  <span className="price">{service.price}</span>
                  <span className="unit">{service.unit}</span>
                </div>
                <ul className="feature-list">
                  {service.features.map((feature, idx) => (
                    <li key={idx}>{feature}</li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      </section>


      <section className="section" style={{ background: 'var(--bg-muted)' }}>
        <div className="container">
          <h2>Trust & Safety</h2>
          <div className="grid grid-2" style={{ textAlign: 'left', marginTop: '48px' }}>
            <div>
              <h4>CPR & First Aid Aware</h4>
              <p style={{ color: 'var(--text-muted)', marginTop: '12px' }}>
                We prioritize pet safety and are trained to handle common pet emergencies and first aid situations.
              </p>
            </div>
            <div>
              <h4>Fully Insured & Bonded</h4>
              <p style={{ color: 'var(--text-muted)', marginTop: '12px' }}>
                We carry comprehensive liability insurance and bonding for your absolute peace of mind.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="section">
        <div className="container">
          <h2>Ready to book?</h2>
          <p style={{ marginTop: '16px', color: 'var(--text-muted)' }}>Join hundreds of happy pets in our local community.</p>
          <Link to="/book" className="button-primary" style={{ marginTop: '32px' }}>Request Your Meet & Greet</Link>
        </div>
      </section>

      <style dangerouslySetInnerHTML={{ __html: `
        .media-placeholder {
          height: 160px;
          background: var(--bg-warm);
          border-radius: var(--radius-md);
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 4rem;
          margin-bottom: 24px;
          border: 1px dashed var(--border-soft);
        }
        .price-block {
          margin: 24px 0;
          padding: 16px;
          background: var(--bg-muted);
          border-radius: var(--radius-sm);
        }
        .price {
          font-size: 1.5rem;
          font-weight: 800;
          color: var(--primary);
          display: block;
        }
        .unit {
          font-size: 0.8rem;
          color: var(--text-muted);
          text-transform: uppercase;
          font-weight: 700;
        }
        .feature-list {
          text-align: left;
          padding-left: 20px;
          color: var(--text-muted);
          font-size: 0.95rem;
          line-height: 1.8;
        }
      `}} />
    </div>
  );
};

export default Services;
