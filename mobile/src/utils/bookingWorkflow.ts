/** Presentation only; backend validation remains authoritative. */
export const canReviewBooking = (role: string | null | undefined) => role === 'owner' || role === 'admin';
export const canOfferApproval = (status: string) => ['PENDING_REVIEW', 'MG_COMPLETED', 'READY_FOR_APPROVAL'].includes(status);
export const bookingPetLabel = (request: { pet_name?: unknown; pet_names?: unknown }) => {
  if (typeof request.pet_name === 'string' && request.pet_name.trim()) return request.pet_name.trim();
  if (Array.isArray(request.pet_names)) {
    const names = request.pet_names.filter((name): name is string => typeof name === 'string' && Boolean(name.trim())).map(name => name.trim());
    if (names.length) return names.join(', ');
  }
  return 'this booking';
};
export const approvalConfirmation = (request: { pet_name?: unknown; pet_names?: unknown }) =>
  'Submit approval for ' + bookingPetLabel(request) + '? The server will check Meet & Greet and quote requirements. If approved, job creation, calendar updates and notifications may follow. Approval does not invite a client to the portal.';
export const bookingNextStep = (status: string) => {
  if (['QUOTE_SENT', 'QUOTED'].includes(status)) return 'Quote sent: check the latest client response in web quote details. This booking status alone does not prove acceptance. Do not approve or assign until the applicable confirmation requirements are satisfied.';
  if (status === 'PENDING_REVIEW') return 'Review the booking before approving or declining. Meet & Greet and quote prerequisites still apply.';
  if (['MEET_GREET_REQUIRED', 'MG_SCHEDULED'].includes(status)) return 'After the Meet & Greet has actually taken place, verify it here. Approval is a separate step.';
  if (['MG_COMPLETED', 'READY_FOR_APPROVAL'].includes(status)) return 'Submit approval separately when the booking is ready. Meet & Greet and quote requirements are still checked.';
  if (status === 'APPROVED') return 'Choose a staff member after visit setup finishes. Refresh if the visits are still initializing.';
  if (status === 'ASSIGNED') return 'Load the visits below and select the exact visit. Changing staff does not start or complete a visit.';
  if (['COMPLETED', 'CANCELLED', 'ARCHIVED', 'DECLINED'].includes(status)) return 'Review the booking history. No approval or visit execution is offered for this booking state.';
  if (status === 'QUOTE_NEEDED') return 'Prepare and send the quote in the web quote editor. Mobile cannot edit or send owner quotes here.';
  if (status === 'PROFILE_CREATED') return 'Profile Created is a workflow status, not proof of a client account or invitation. Verify the client profile, account link and invitation in web client management.';
  return null;
};
