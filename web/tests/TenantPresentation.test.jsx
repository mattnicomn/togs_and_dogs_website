import { describe, it, expect, afterEach } from 'vitest';
import {
  DEFAULT_BRANDING,
  TOG_AND_DOGS_BRANDING,
  NEUTRAL_PLATFORM_PRESENTATION,
  deriveTenantPresentation,
  updateDocumentTitle,
} from '../src/utils/tenantPresentation';
import { TERMS_CONTENT } from '../src/constants/policy';

describe('TenantPresentation Unit & Integration Tests (PTM-3D & PTM-3D.1)', () => {
  const originalTitle = document.title;

  afterEach(() => {
    document.title = originalTitle;
  });

  it('should return NEUTRAL_PLATFORM_PRESENTATION when tenantInfo is null or missing company_id (PTM-3D.1)', () => {
    const neutralNull = deriveTenantPresentation(null);
    expect(neutralNull.is_neutral_platform).toBe(true);
    expect(neutralNull.display_name).toBe('USMissionHero');
    expect(neutralNull.document_title).toBe('Pet Care Operations Platform | USMissionHero');
    expect(neutralNull.team_label).toBe('Pet Care Operations Team');

    const neutralEmpty = deriveTenantPresentation({});
    expect(neutralEmpty).toEqual(NEUTRAL_PLATFORM_PRESENTATION);
  });

  it('should return explicit TOG_AND_DOGS_BRANDING for primary tenant tog_and_dogs', () => {
    const info = { company_id: 'tog_and_dogs', display_name: 'Tog and Dogs' };
    const presentation = deriveTenantPresentation(info);

    expect(presentation.company_id).toBe('tog_and_dogs');
    expect(presentation.display_name).toBe('Tog and Dogs');
    expect(presentation.document_title).toBe('Tog and Dogs | Premium Pet Care & Dog Walking');
    expect(presentation.is_default_tenant).toBe(true);
    expect(presentation.is_neutral_platform).toBe(false);
    expect(presentation).toEqual(TOG_AND_DOGS_BRANDING);
    expect(presentation).toEqual(DEFAULT_BRANDING);
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
    expect(presentation.is_neutral_platform).toBe(false);
  });

  it('should update document.title dynamically and reset to NEUTRAL_PLATFORM_PRESENTATION on null (PTM-3D.1)', () => {
    const alpha = deriveTenantPresentation({
      company_id: 'test_tenant_alpha',
      display_name: 'Test Tenant Alpha',
    });

    updateDocumentTitle(alpha);
    expect(document.title).toBe('Test Tenant Alpha | Pet Care Portal');

    // On logout / null tenant context, title resets to neutral platform title (NOT Togs & Dogs)
    updateDocumentTitle(null);
    expect(document.title).toBe(NEUTRAL_PLATFORM_PRESENTATION.document_title);

    // When explicitly in Tog & Dogs tenant context, title updates to Tog & Dogs title
    const togAndDogs = deriveTenantPresentation({ company_id: 'tog_and_dogs' });
    updateDocumentTitle(togAndDogs);
    expect(document.title).toBe(TOG_AND_DOGS_BRANDING.document_title);
  });

  it('should format export backup filename with tenant company_id prefix', () => {
    const alphaInfo = { company_id: 'test_tenant_alpha', display_name: 'Test Tenant Alpha' };
    const exportPrefix = alphaInfo?.company_id || 'TogAndDogs';
    expect(exportPrefix).toBe('test_tenant_alpha');

    const defaultPrefix = null?.company_id || 'TogAndDogs';
    expect(defaultPrefix).toBe('TogAndDogs');
  });

  it('should preserve legal platform operator identity in policy terms', () => {
    const aboutSection = TERMS_CONTENT.find(s => s.title === 'About These Terms');
    expect(aboutSection).toBeDefined();
    expect(aboutSection.body).toContain('USMissionHero / Tog and Dogs');
  });
});
