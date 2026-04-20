export const STAFF_MEMBERS = [
  { id: 'Ryan', label: 'Ryan' },
  { id: 'Wife', label: 'Wife (Sarah)' },
  { id: 'Nephew1', label: 'Nephew 1' },
  { id: 'Nephew2', label: 'Nephew 2' }
];

export const getStaffLabel = (id) => {
  const staff = STAFF_MEMBERS.find(s => s.id === id);
  return staff ? staff.label : id;
};
