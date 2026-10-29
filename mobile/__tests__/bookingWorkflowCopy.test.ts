import { approvalConfirmation, bookingPetLabel, bookingNextStep } from '../src/utils/bookingWorkflow';
describe('booking copy with legacy/missing fields', () => {
  it.each([{}, { pet_name: null }, { pet_name: 42 }, { pet_names: 'legacy string' }, { pet_names: [null, 42, ' '] }])('never invents a pet or client for malformed legacy fields: %p', request => {
    expect(bookingPetLabel(request)).toBe('this booking');
    expect(approvalConfirmation(request)).not.toMatch(/undefined|null|Buddy|Jane Smith/);
    expect(approvalConfirmation(request)).toContain('If approved');
  });
  it('uses actual multi-pet labels without changing service/window data', () => {
    const request = { pet_names: [' Test Pet ', 'Second Test Pet'], service_type: 'DROPIN_3HR', timeframe: 'AFTERNOON' };
    expect(bookingPetLabel(request)).toBe('Test Pet, Second Test Pet');
    expect(request.service_type).toBe('DROPIN_3HR');
    expect(request.timeframe).toBe('AFTERNOON');
  });
  it('keeps quote preparation and account invitation as explicit web handoffs', () => {
    expect(bookingNextStep('QUOTE_NEEDED')).toContain('web quote editor');
    expect(bookingNextStep('PROFILE_CREATED')).toContain('not proof');
  });
});