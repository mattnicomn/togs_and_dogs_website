import React from 'react';
import { PRIVACY_VERSION, PRIVACY_CONTENT } from '../constants/policy';
import { Link } from 'react-router-dom';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="section">
          <div className="container" style={{ maxWidth: '800px', textAlign: 'center' }}>
            <h2>Something went wrong loading the Privacy Policy.</h2>
            <Link to="/" className="btn btn-primary">Return to Home</Link>
          </div>
        </div>
      );
    }

    return this.props.children; 
  }
}

const PrivacyPolicyContent = () => {
  return (
    <div className="section">
      <div className="container" style={{ maxWidth: '800px' }}>
        <span className="badge">Version {PRIVACY_VERSION}</span>
        <h1>Privacy Policy</h1>
        {PRIVACY_CONTENT.map((section, index) => (
          <div key={index} style={{ marginBottom: '24px' }}>
            <h2>{section.title}</h2>
            <p style={{ fontSize: '16px' }}>{section.body}</p>
          </div>
        ))}
      </div>
    </div>
  );
};

const PrivacyPolicy = () => (
  <ErrorBoundary>
    <PrivacyPolicyContent />
  </ErrorBoundary>
);

export default PrivacyPolicy;
