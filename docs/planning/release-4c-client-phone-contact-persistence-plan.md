# Release 4C: Client Phone / Contact Persistence — Implementation Plan

**Date:** 2026-05-13  
**Status:** Plan Only — No Implementation Yet  
**Prerequisite:** Release 4B fully accepted  
**Objective:** Add client phone support end-to-end so phone numbers submitted during intake are stored, carried into Client Management, and visible to admins.

---

## 1. Discovery Findings

### Q1: Does intake_handler.py already receive a phone field?
**No.** The intake handler does not read or store any phone field from the request body. The only phone-related data currently collected is in the `emergency_contact` object (Release 4A), which is a different concept (emergency contact phone, not client's own phone).

### Q2: What field name should be canonical?
**`client_phone`** on the REQ record (consistent with `client_name`, `client_email`).  
**`phone`** on the Client Management profile (already exists as `phone` field on COMPANY#/CLIENT# records).

### Q3: Does client_profile.py already store phone?
**Yes, but sets it to `None`.** Line 176: `'phone': None,  # Not collected on current intake form`. This is the exact line to update.

### Q4: Where should phone display?
- **Client Management profile cards** — Already displays `c.phone` with 📞 icon ✅
- **Client Management search** — Already searches `c.phone` ✅
- **CareCard** — Not currently shown. Should add to Overview or a contact section.
- **Admin Request List** — Not shown inline (too many columns). Available in export as `r.client_phone`.
- **Export** — Already references `r.client_phone || r.phone` ✅

### Q5: Should phone be copied only on creation, or also fill blank existing profiles?
**Both.** On creation: set phone. On linking to existing profile: fill if profile phone is blank.

### Q6: Should phone ever overwrite existing profile phone?
**No.** Only fill blank. Admin-entered phone takes precedence.

### Q7: Validation/formatting rules?
**MVP: free text.** No formatting enforcement. Phone formats vary internationally.

---

## 2. Changes Required

### Backend: `src/backend/handlers/intake_handler.py`

Add `client_phone` to the REQ record creation:

```python
# In the item dict, after 'client_email':
'client_phone': body.get('client_phone') or None,
```

One line addition. No validation change (phone is optional).

### Backend: `src/backend/common/client_profile.py`

**On new profile creation** (line ~176):
```python
# Change from:
'phone': None,
# To:
'phone': request_item.get('client_phone') or None,
```

**On existing profile linking** — add phone fill-if-blank logic in `_update_profile_request_metadata`:
```python
# After updating latest_request_id, also fill phone if blank:
if request_item.get('client_phone') and not existing_profile.get('phone'):
    # Fill blank phone from intake
```

This requires a small addition to the linking flow.

### Frontend: `web/src/components/IntakeForm.jsx`

Re-add the client phone field to Step 1 (was removed in 4B because backend didn't persist it):

```jsx
<div className="field" style={{ marginTop: '16px' }}>
  <label>Phone Number (Optional)</label>
  <input 
    type="tel" 
    value={formData.client_phone || ''} 
    onChange={(e) => setFormData({...formData, client_phone: e.target.value})} 
    placeholder="555-123-4567"
  />
</div>
```

### Frontend: `web/src/components/CareCard.jsx`

Add phone display in the Overview tab (client contact info):

```jsx
{(activePet._originItem?.client_phone || pet._originItem?.client_phone) && (
  <p>📞 {activePet._originItem?.client_phone || pet._originItem?.client_phone}</p>
)}
```

---

## 3. Files to Change

| File | Change | Type |
|------|--------|------|
| `src/backend/handlers/intake_handler.py` | Add `client_phone` to record creation | Backend (1 line) |
| `src/backend/common/client_profile.py` | Set phone from request on creation + fill-if-blank on link | Backend (~10 lines) |
| `web/src/components/IntakeForm.jsx` | Re-add phone field to Step 1 | Frontend |
| `web/src/components/CareCard.jsx` | Display phone in Overview | Frontend (3 lines) |

**Total:** 2 backend + 2 frontend files  
**Estimated effort:** ~15 lines backend, ~15 lines frontend  
**Risk level:** Very low

---

## 4. Data Flow

```
Client submits intake with client_phone: "555-123-4567"
  → intake_handler stores client_phone on REQ record
  → Admin approves CUSTOMER_INTAKE
  → client_profile.py auto-creates profile:
      phone = request_item.get('client_phone')  → "555-123-4567"
  → OR links to existing profile:
      if existing profile.phone is blank → fill with client_phone
      if existing profile.phone already set → do not overwrite
  → Client Management card shows 📞 555-123-4567
  → CareCard Overview shows phone
  → Client search finds by phone
```

---

## 5. Merge Rules

| Scenario | Action |
|----------|--------|
| New profile created, client_phone provided | Set `phone = client_phone` |
| New profile created, no client_phone | Set `phone = None` |
| Existing profile linked, profile phone is blank, client_phone provided | Fill `phone = client_phone` |
| Existing profile linked, profile phone already set | Do NOT overwrite |
| Existing profile linked, no client_phone on request | No change |

---

## 6. Backward Compatibility

| Scenario | Behavior |
|----------|----------|
| Old requests without `client_phone` | `client_phone` is None — no display, no error |
| Old profiles without `phone` | Already handled — shows nothing |
| New request with phone, old profile without phone | Phone filled on link |
| Export references `r.client_phone \|\| r.phone` | Already works ✅ |
| Client Management search by phone | Already works ✅ |
| Client Management card phone display | Already works ✅ |

---

## 7. Validation Plan

| # | Test | Expected |
|---|------|----------|
| 1 | Submit intake WITH phone | Request stores `client_phone` |
| 2 | Submit intake WITHOUT phone | Submission succeeds, `client_phone` is null |
| 3 | Approve new customer with phone | Profile created with phone |
| 4 | Approve new customer without phone | Profile created with phone=null |
| 5 | Link to existing profile (blank phone) | Profile phone filled |
| 6 | Link to existing profile (has phone) | Profile phone NOT overwritten |
| 7 | CareCard shows phone | Visible in Overview |
| 8 | Client Management card shows phone | Already works (📞 icon) |
| 9 | Search by phone | Already works |
| 10 | Old records without phone | Clean display, no errors |
| 11 | `npm run build` | Passes |
| 12 | `py -m py_compile` | Passes |
| 13 | `terraform plan` | Lambda code-only changes |
| 14 | No Cognito/calendar/status changes | Confirmed |

---

## 8. Risks and Rollback

### Very Low Risk

- One-line backend addition (optional field)
- Phone is already supported in Client Management (display, search, edit)
- No validation enforcement (free text)
- No workflow/lifecycle changes

### Rollback

- Remove `client_phone` from intake_handler record creation → field stops being stored
- Frontend phone field can be hidden again
- Existing records with `client_phone` are harmless
- No data cleanup needed

---

## 9. Out of Scope

| Item | Reason |
|------|--------|
| Phone formatting/validation | MVP accepts free text. International formats vary. |
| Phone as auto-link key | Only email auto-links. Phone is informational. |
| SMS notifications to client phone | Separate feature, requires consent. |
| Quote/payment editing | Separate release scope. |
| Staff assignment editing | Separate release scope. |
| Multi-pet editing | Separate release scope. |
