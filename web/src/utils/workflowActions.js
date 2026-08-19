export const GUIDED_ACTION_SEMANTICS = Object.freeze({
  STATUS_TRANSITION: 'STATUS_TRANSITION',
  ASSIGNMENT_HANDOFF: 'ASSIGNMENT_HANDOFF',
  CALENDAR_NAVIGATION: 'CALENDAR_NAVIGATION'
});

const PRIMARY_ACTION_BY_STATUS = Object.freeze({
  PENDING_REVIEW: 'CREATE_PROFILE',
  NEEDS_REVIEW: 'CREATE_PROFILE',
  MEET_GREET_REQUIRED: 'VERIFY_MG',
  NEEDS_MG: 'VERIFY_MG',
  MG_SCHEDULED: 'VERIFY_MG',
  MG_COMPLETED: 'APPROVE',
  QUOTE_NEEDED: 'QUOTED',
  QUOTE_SENT: 'APPROVE',
  QUOTED: 'APPROVE',
  READY_FOR_APPROVAL: 'APPROVE',
  NEW_REQUEST: 'APPROVE',
  APPROVED: 'ASSIGN',
  BOOKED: 'ASSIGN',
  JOB_CREATED: 'ASSIGN',
  IN_PROGRESS: 'COMPLETE',
  COMPLETED: 'ARCHIVE',
  CANCELLED: 'REOPEN_PENDING',
  DECLINED: 'ARCHIVE',
  ARCHIVED: 'REOPEN_PENDING',
  DELETED: 'REOPEN_PENDING'
});

const getActionDescriptor = (actionId) => {
  if (actionId === 'ASSIGN') {
    return {
      id: actionId,
      label: 'Assign Sitter',
      semantic: GUIDED_ACTION_SEMANTICS.ASSIGNMENT_HANDOFF
    };
  }

  if (actionId === 'VIEW_CALENDAR') {
    return {
      id: actionId,
      label: 'View in Calendar',
      semantic: GUIDED_ACTION_SEMANTICS.CALENDAR_NAVIGATION,
      target: 'SCHEDULER'
    };
  }

  return {
    id: actionId,
    semantic: GUIDED_ACTION_SEMANTICS.STATUS_TRANSITION
  };
};

export const resolveGuidedWorkflowAction = (item, allowedActions = []) => {
  const status = String(item?.status || 'PENDING_REVIEW').toUpperCase();
  let actionId;

  if (status === 'PROFILE_CREATED') {
    actionId = item?.meet_and_greet_required !== false ? 'MEET_GREET' : 'APPROVE';
  } else if (status === 'ASSIGNED' && !item?.worker_id && allowedActions.includes('ASSIGN')) {
    actionId = 'ASSIGN';
  } else if (status === 'ASSIGNED' || status === 'SCHEDULED') {
    actionId = 'VIEW_CALENDAR';
  } else {
    actionId = PRIMARY_ACTION_BY_STATUS[status];
  }

  if (!actionId) return null;

  const descriptor = getActionDescriptor(actionId);
  if (
    descriptor.semantic !== GUIDED_ACTION_SEMANTICS.CALENDAR_NAVIGATION &&
    !allowedActions.includes(actionId)
  ) {
    return null;
  }

  return descriptor;
};
