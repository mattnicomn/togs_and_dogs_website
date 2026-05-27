import React from 'react';
import { TERMS_VERSION, TERMS_CONTENT } from '../constants/policy';

const TermsOfUse = () => {
  return (
    <div className="section">
      <div className="container" style={{ maxWidth: '800px' }}>
        <span className="badge">Version {TERMS_VERSION}</span>
        <h1>Terms of Use</h1>
        {TERMS_CONTENT.map((section, index) => (
          <div key={index} style={{ marginBottom: '24px' }}>
            <h2>{section.title}</h2>
            <p>{section.body}</p>
          </div>
        ))}
      </div>
    </div>
  );
};

export default TermsOfUse;
