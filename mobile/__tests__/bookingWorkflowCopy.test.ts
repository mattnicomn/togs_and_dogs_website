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
    expect(bookingNextStep('QUOTE_NEEDED')).toContain('Quote section on this screen');
    expect(bookingNextStep('QUOTE_NEEDED')).not.toMatch(/web quote editor|cannot edit or send/i);
    expect(bookingNextStep('PROFILE_CREATED')).toContain('not proof');
  });
  it('gives cancellation-specific next-step copy for CANCELLATION_REQUESTED', () => {
    const copy = bookingNextStep('CANCELLATION_REQUESTED');
    expect(copy).toContain('asked to cancel');
    expect(copy).toContain('Cancellation requested section');
    expect(copy).toContain('Approve Cancellation');
    expect(copy).toContain('Deny Cancellation');
    expect(copy).toContain('prior status');
    expect(copy).toContain('nothing is retried automatically');
    // Must not fall back to the ordinary booking-review guidance.
    expect(copy).not.toMatch(/approving or declining|Meet & Greet|Choose a staff member|Submit approval/i);
  });
  it('leaves every other status copy unchanged', () => {
    const expected: Record<string, string | null> = {
      QUOTE_SENT: 'Quote sent: check the latest client response in web quote details. This booking status alone does not prove acceptance. Do not approve or assign until the applicable confirmation requirements are satisfied.',
      QUOTED: 'Quote sent: check the latest client response in web quote details. This booking status alone does not prove acceptance. Do not approve or assign until the applicable confirmation requirements are satisfied.',
      PENDING_REVIEW: 'Review the booking before approving or declining. Meet & Greet and quote prerequisites still apply.',
      MEET_GREET_REQUIRED: 'After the Meet & Greet has actually taken place, verify it here. Approval is a separate step.',
      MG_SCHEDULED: 'After the Meet & Greet has actually taken place, verify it here. Approval is a separate step.',
      MG_COMPLETED: 'Submit approval separately when the booking is ready. Meet & Greet and quote requirements are still checked.',
      READY_FOR_APPROVAL: 'Submit approval separately when the booking is ready. Meet & Greet and quote requirements are still checked.',
      APPROVED: 'Choose a staff member after visit setup finishes. Refresh if the visits are still initializing.',
      ASSIGNED: 'Load the visits below and select the exact visit. Changing staff does not start or complete a visit.',
      COMPLETED: 'Review the booking history. No approval or visit execution is offered for this booking state.',
      CANCELLED: 'Review the booking history. No approval or visit execution is offered for this booking state.',
      ARCHIVED: 'Review the booking history. No approval or visit execution is offered for this booking state.',
      DECLINED: 'Review the booking history. No approval or visit execution is offered for this booking state.',
      CANCELLATION_DENIED: null,
      UNKNOWN_STATUS: null,
    };
    for (const [status, copy] of Object.entries(expected)) expect(bookingNextStep(status)).toBe(copy);
  });
});