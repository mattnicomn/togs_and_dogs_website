# Release 4D: Quote & Payment Inline Editing — Implementation Plan

**Date:** 2026-05-13  
**Status:** Plan Only — No Implementation Yet  
**Prerequisite:** Release 4C fully accepted  
**Objective:** Make quote amount and payment status editable inline within the CareCard Pricing & Quote tab.

---

## 1. Discovery Findings

### Q1: Where are quote/pricing fields stored?

On the **PET# record** (not the REQ record):
```
PK: PET#<pet_id>
SK: CLIENT#<client_id>
```

Fields: `quote_amount`, `deposit_required`, `deposit_paid`, `payment_status`, `quote_sent_date`, `quote_accepted_date`, `quote_notes`, `internal_pricing_notes`

### Q2: Which fields exist today?

| Field | Type | Current Usage |
|-------|------|---------------|
| `quote_amount` | Decimal | Displayed in CareCard (read-only) |
| `payment_status` | String | Displayed in CareCard (read-only). Values: "Not Quoted", "Accepted", "Deposit Paid", "Paid in Full" |
| `deposit_required` | Boolean | Stored, not prominently displayed |
| `deposit_paid` | Boolean | Stored, not prominently displayed |
| `quote_sent_date` | String (ISO) | Stored, not displayed |
| `quote_accepted_date` | String (ISO) | Stored, not displayed |
| `quote_notes` | String | Stored, not displayed |
| `internal_pricing_notes` | String | Stored, not displayed. Sensitive (redacted from staff/client) |

### Q3: Which backend handler updates pricing/payment?

**`pet_handler.py`** — the `PUT /admin/pets/{petId}` endpoint. All quote/payment fields are already in the `editable_fields` list. The backend already supports editing these fields.

### Q4: Are fields restricted by backend?

**Yes, partially:**
- Staff role: `quote_amount`, `deposit_required`, `internal_pricing_notes`, `meet_and_greet_notes` are stripped from the request body before saving (sensitive_fields guard)
- Owner/admin: full access to all fields
- Client: cannot access pet update endpoint at all

### Q5: RBAC

| Role | Quote/Payment Access |
|------|---------------------|
| Owner | Full edit ✅ |
| Admin | Full edit ✅ |
| Staff | View-only (sensitive fields stripped by backend) ✅ |
| Client | No access ✅ |

**Already enforced server-side.** No additional RBAC changes needed.

### Q6: Should changes append to audit_log?

**Recommended: Yes.** Add an audit entry when quote/payment fields change. This is a frontend concern — the existing `handleUpdatePet` flow calls `updatePet()` which saves the full PET# record. We can append a note to the REQ audit_log or simply rely on the PET# `updated_at` timestamp.

For Release 4D MVP: rely on `updated_at` timestamp on PET# record. Full audit trail enhancement can be a follow-up.

### Q7: Should edits trigger notifications?

**No.** Release 4D is admin-internal. No client or staff notifications on quote/payment changes.

### Q8: Should payment status affect workflow status?

**No.** The `review_handler.py` already checks `payment_status` as a gate for APPROVED transition (if `quote_amount > 0`, payment must be "Accepted", "Deposit Paid", or "Paid in Full"). But changing payment status does NOT automatically change the request workflow status.

### Q9: Payment statuses supported?

**Current values in use** (from review_handler gate):
- "Not Quoted" (default)
- "Accepted"
- "Deposit Paid"
- "Paid in Full"

**Recommended expanded set for Release 4D:**
- Not Quoted
- Quote Sent
- Payment Pending
- Deposit Paid
- Paid in Full
- Partially Paid
- Refunded
- Waived

**Important:** The review_handler approval gate checks for `['Accepted', 'Deposit Paid', 'Paid in Full']`. If we add new statuses, we must ensure the gate still works. "Payment Pending", "Partially Paid", "Refunded", "Waived" would NOT satisfy the gate — which is correct behavior (can't approve without payment confirmation).

### Q10: Can edits be saved independently from status transitions?

**Yes.** The `handleUpdatePet` → `updatePet()` flow saves PET# record fields independently. It does not trigger status transitions unless the record is in an intake state with `pet_id === 'NEW'`.

### Q11: Where should the edit UI live?

In the existing **CareCard "Meet & Greet / Quote" tab** (case `'quoting'`). The tab already displays `quote_amount` and `payment_status` as read-only. Release 4D makes them editable when `isEditing` is true.

### Q12: Validation for dollar amounts?

- `quote_amount`: numeric, >= 0, max 2 decimal places. Frontend: `<input type="number" step="0.01" min="0">`
- `payment_status`: select dropdown from allowed values
- `quote_notes`: free text, optional

### Q13: Risks with exports, archived, cancelled records?

- **Exports:** Already include quote/payment fields from PET# records. No change needed.
- **Archived/cancelled records:** CareCard can still be opened for these. Editing should be allowed (admin may need to update payment status after cancellation for refund tracking).
- **Data Issues:** Quote/payment fields don't affect Data Issues detection.

---

## 2. Recommended Release 4D Scope

### In Scope

1. Make `quote_amount` editable in CareCard (number input, when `isEditing`)
2. Make `payment_status` editable in CareCard (dropdown, when `isEditing`)
3. Add `quote_notes` display and edit (textarea, when `isEditing`)
4. Add `deposit_required` toggle (checkbox, when `isEditing`)
5. Add `deposit_paid` toggle (checkbox, when `isEditing`)
6. Use existing `handleSave` → `updatePet()` flow (already works)
7. Enforce RBAC via existing backend sensitive_fields guard (staff can't edit)
8. Show edit controls only for owner/admin role

### Out of Scope

- Notifications on payment change
- Automatic workflow status change from payment
- Invoice generation or links
- Payment processing integration
- `internal_pricing_notes` editing (already sensitive, keep admin-only via separate mechanism)
- New backend endpoints (existing `PUT /admin/pets/{petId}` already works)

---

## 3. Files to Change

| File | Change | Type |
|------|--------|------|
| `web/src/components/CareCard.jsx` | Make quote/payment fields editable in the Quoting tab | Frontend |

**That's it.** One file. The backend already supports all these fields via `updatePet()`. The save flow already exists. This is purely a frontend display change.

---

## 4. Implementation Detail

### Current CareCard Quoting Tab (read-only)

```jsx
<div className="price-display">
  <label>Quote Amount</label>
  <p className="price-large">${pet.quote_amount || '0.00'}</p>
</div>
<div className="price-display">
  <label>Payment Status</label>
  <p><strong>{pet.payment_status || 'Not Quoted'}</strong></p>
</div>
```

### Target (editable when isEditing)

```jsx
<div className="field">
  <label>Quote Amount</label>
  {isEditing ? (
    <input type="number" step="0.01" min="0" 
      value={formData.quote_amount || ''} 
      onChange={e => handleInputChange('quote_amount', parseFloat(e.target.value) || 0)} 
    />
  ) : <p className="price-large">${activePet.quote_amount || '0.00'}</p>}
</div>
<div className="field">
  <label>Payment Status</label>
  {isEditing ? (
    <select value={formData.payment_status || 'Not Quoted'} 
      onChange={e => handleInputChange('payment_status', e.target.value)}>
      <option value="Not Quoted">Not Quoted</option>
      <option value="Quote Sent">Quote Sent</option>
      <option value="Payment Pending">Payment Pending</option>
      <option value="Accepted">Accepted</option>
      <option value="Deposit Paid">Deposit Paid</option>
      <option value="Paid in Full">Paid in Full</option>
      <option value="Partially Paid">Partially Paid</option>
      <option value="Refunded">Refunded</option>
      <option value="Waived">Waived</option>
    </select>
  ) : <p><strong>{activePet.payment_status || 'Not Quoted'}</strong></p>}
</div>
<div className="field">
  <label>Quote Notes</label>
  {isEditing ? (
    <textarea rows="2" value={formData.quote_notes || ''} 
      onChange={e => handleInputChange('quote_notes', e.target.value)} 
      placeholder="Payment terms, special pricing notes..." />
  ) : <p>{activePet.quote_notes || 'No notes.'}</p>}
</div>
<div style={{ display: 'flex', gap: '20px' }}>
  <label><input type="checkbox" checked={formData.deposit_required || false} 
    disabled={!isEditing} onChange={e => handleInputChange('deposit_required', e.target.checked)} /> Deposit Required</label>
  <label><input type="checkbox" checked={formData.deposit_paid || false} 
    disabled={!isEditing} onChange={e => handleInputChange('deposit_paid', e.target.checked)} /> Deposit Paid</label>
</div>
```

---

## 5. Backward Compatibility

| Scenario | Behavior |
|----------|----------|
| Old PET# records without quote fields | Displays "Not Quoted" / "$0.00" (existing fallback) |
| Records with existing payment_status values | Dropdown shows current value |
| Staff role opens CareCard | Edit button works but backend strips sensitive fields on save |
| Approval gate | Still checks `payment_status in ['Accepted', 'Deposit Paid', 'Paid in Full']` — unchanged |

---

## 6. Validation Plan

| # | Test | Expected |
|---|------|----------|
| 1 | Open CareCard, click Edit | Quote/payment fields become editable |
| 2 | Change quote_amount to 75.00 | Saves successfully |
| 3 | Change payment_status to "Deposit Paid" | Saves successfully |
| 4 | Add quote_notes | Saves successfully |
| 5 | Toggle deposit_required | Saves successfully |
| 6 | View as staff role | Fields visible but not editable (backend strips) |
| 7 | Old record without quote fields | Shows clean defaults |
| 8 | Approval gate still works | Can't approve if quote > 0 and payment not accepted |
| 9 | No console errors | Clean |
| 10 | npm run build | Passes |

---

## 7. Risks and Rollback

### Very Low Risk

- **One frontend file changed** (CareCard.jsx)
- **No backend changes** — existing `updatePet` already supports all fields
- **No new API endpoints**
- **No workflow/status changes**
- **No notification changes**
- **Existing RBAC already enforces staff restrictions**

### Rollback

Revert CareCard.jsx → fields return to read-only display. No data affected.

---

## 8. Implementation Phases

### Phase 1 (Release 4D)
- Make quote_amount, payment_status, quote_notes, deposit_required, deposit_paid editable in CareCard
- Frontend-only change

### Phase 2 (Future)
- Add audit trail for quote/payment changes
- Add invoice link field
- Add payment date tracking
- Consider payment reminder notifications
