import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import {
  DEFAULT_BRANDING,
  deriveTenantPresentation,
  updateDocumentTitle,
} from '../src/utils/tenantPresentation';

describe('TenantPresentation Unit Tests (PTM-3D)', () => {
  const originalTitle = document.title;

  afterEach(() => {
    document.title = originalTitle;
  });

  it('should return DEFAULT_BRANDING for primary tenant tog_and_dogs', () => {
    const info = { company_id: 'tog_and_dogs', display_name: 'Tog and Dogs' };
    const presentation = deriveTenantPresentation(info);

    expect(presentation.company_id).toBe('tog_and_dogs');
    expect(presentation.display_name).toBe('Tog and Dogs');
    expect(presentation.document_title).toBe('Tog and Dogs | Premium Pet Care & Dog Walking');
    expect(presentation.is_default_tenant).toBe(true);
  });

  it('should return DEFAULT_BRANDING when tenantInfo is null or missing company_id', () => {
    expect(deriveTenantPresentation(null)).toEqual(DEFAULT_BRANDING);
    expect(deriveTenantPresentation({})).toEqual(DEFAULT_BRANDING);
  });

  it('should derive tenant-aware presentation for non-default tenant test_tenant_alpha', () => {
    const info = {
      company_id: 'test_tenant_alpha',
      display_name: 'Test Tenant Alpha',
    };
    const presentation = deriveTenantPresentation(info);

    expect(presentation.company_id).toBe('test_tenant_alpha');
    expect(presentation.display_name).toBe('Test Tenant Alpha');
    expect(presentation.document_title).toBe('Test Tenant Alpha | Pet Care Portal');
    expect(presentation.portal_title).toBe('Test Tenant Alpha Portal');
    expect(presentation.client_portal_label).toBe('Test Tenant Alpha Client Portal');
    expect(presentation.staff_portal_label).toBe('Test Tenant Alpha Staff Portal');
    expect(presentation.intake_label).toBe('Request Care - Test Tenant Alpha');
    expect(presentation.team_label).toBe('Test Tenant Alpha Team');
    expect(presentation.is_default_tenant).toBe(false);
  });

  it('should update document.title dynamically and reset on null', () => {
    const alpha = deriveTenantPresentation({
      company_id: 'test_tenant_alpha',
      display_name: 'Test Tenant Alpha',
    });

    updateDocumentTitle(alpha);
    expect(document.title).toBe('Test Tenant Alpha | Pet Care Portal');

    updateDocumentTitle(null);
    expect(document.title).toBe(DEFAULT_BRANDING.document_title);
  });
});
