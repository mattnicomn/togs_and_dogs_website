# Release 4B: CareCard Multi-Pet Display & Admin Usability — Implementation Plan

**Date:** 2026-05-13  
**Status:** Plan Only — No Implementation Yet  
**Prerequisite:** Release 4A fully accepted  
**Objective:** Display structured multi-pet data in the CareCard and improve admin usability without changing the underlying data model.

---

## 1. Current-State Findings

### How CareCard Gets Pet Data

```javascript
// In AdminDashboard.jsx → handleSelectPet():
if (item.pet_id) {
  const petData = await getPet(item.pet_id, item.client_id);
  setSelectedPet({ ...petData, _originItem: item });
} else {
  // Basic preview from REQ fields only
  setSelectedPet({ name: item.client_name, ... , _originItem: item });
}
```

**Key findings:**
1. CareCard receives a SINGLE PET# record merged with the REQ record (`_originItem`)
2. It uses `item.pet_id` (singular) — does NOT check `item.pet_ids` (array from Release 4A)
3. The `getPet(petId, clientId)` API fetches one PET# record by ID
4. If no `pet_id` exists, CareCard shows a basic preview from REQ fields

### What CareCard Currently Displays

| Tab | Data Source | Fields |
|-----|-------------|--------|
| Overview | PET# record | name, breed, age, photo_url, care_instructions, status |
| Visit Details | REQ record (`_originItem`) | service_type, visit_window(s), preferred_time |
| Pet Care | PET# record | behavior, care_instructions |
| Vet & Emergency | PET# record `health` map | vet_name, vet_phone, emergency_name, emergency_phone, logistics |
| Meet & Greet / Quote | PET# record | meet_and_greet_completed, quote_amount, payment_status |
| Scheduling / Staff | REQ record (`_originItem`) | scheduled_date/time, worker_name, preferred_sitter |
| Admin Notes / History | PET# + REQ | admin_notes, audit_log |

### Gap: Multi-Pet Not Supported

- `handleSelectPet` only loads `pet_id` (first pet)
- No awareness of `pet_ids` array
- No pet selector/tabs
- New Release 4A fields (`species`, `feeding_notes`, `medication_notes`, `behavior_notes`, `vet_notes`, `emergency_notes`) are stored but not displayed

---

## 2. Discovery Answers

### Q1: Where does CareCard get pet data from?
From `getPet(pet_id, client_id)` API call → returns one PET# record from DynamoDB.

### Q2: Does CareCard receive PET# records directly, or only request fields?
Both. It fetches the PET# record and merges it with `_originItem` (the REQ record). The merged object is passed as the `pet` prop.

### Q3: Does the admin API need to hydrate request records with linked PET# records?
Not currently. The frontend fetches PET# records on-demand when CareCard opens. For multi-pet, we need to either:
- Fetch all PET# records when CareCard opens (multiple API calls), OR
- Add a batch endpoint that returns all pets for a client

**Recommendation:** Fetch individually from `pet_ids` array. The list is small (1-5 pets typically).

### Q4: Should CareCard show pet tabs from request.pets, pet_ids + PET# lookup, or legacy fallback?
**Recommended priority:**
1. `pet_ids` array → fetch each PET# record (authoritative, post-approval data)
2. `pet_id` singular → fetch single PET# record (legacy)
3. `_originItem.pets` array → display from request data (pre-approval, no PET# records yet)
4. `_originItem.pet_names` string → legacy display

### Q5: Lowest-risk way to display structured pet data without breaking legacy?
Use a `normalizePetsForDisplay(record)` helper that returns a consistent array regardless of source format.

### Q6: Should admin editing of PET# fields be included in Release 4B?
**No.** The existing edit flow (`handleSave` → `onUpdate` → `updatePet`) already works for the first pet. Multi-pet editing adds complexity. Release 4B is display-only for new fields. Editing the first pet continues to work as before.

### Q7: How should Vet & Emergency tab be organized?
- **Top section:** Household-level vet/emergency (from client profile or REQ `vet_info`)
- **Per-pet section:** Individual vet_notes/emergency_notes (from PET# records)
- Keep existing `health` map display as fallback for legacy records

### Q8: Should client phone field be added now?
**Yes, include in Release 4B** — it's a single `<input>` field addition to IntakeForm Step 1. Very low risk.

---

## 3. Recommended Implementation Approach

### Strategy: Display-First, Minimal Backend Changes

1. **Frontend helper:** `normalizePetsForDisplay(item)` — returns consistent pet array from any record format
2. **Multi-fetch on CareCard open:** Load all PET# records from `pet_ids` array
3. **Pet selector tabs:** Only shown when 2+ pets exist
4. **New field display:** Add species, feeding, medication, behavior, vet_notes, emergency_notes to CareCard tabs
5. **Household vet/emergency:** Display from `_originItem.vet_info` or client profile data
6. **No new backend endpoints** — use existing `getPet(petId, clientId)` for each pet
7. **No PET# mutation changes** — existing edit flow continues for first pet

### Data Flow

```
User clicks record in Request List
  → handleSelectPet(item) called
  → Check item.pet_ids (array) or item.pet_id (singular)
  → If pet_ids: fetch ALL PET# records via getPet() for each
  → If pet_id only: fetch single PET# record (current behavior)
  → If neither: show preview from REQ fields
  → Pass { pets: [...], _originItem: item } to CareCard
  → CareCard shows pet tabs if pets.length > 1
  → Each tab shows that pet's structured fields
```

---

## 4. Files Likely to Change

| File | Changes |
|------|---------|
| `web/src/components/AdminDashboard.jsx` | Update `handleSelectPet` to load multiple PET# records |
| `web/src/components/CareCard.jsx` | Pet selector tabs, new field display, household vet section |
| `web/src/components/IntakeForm.jsx` | Add client phone field to Step 1 (minor) |

**Total:** 3 frontend files  
**Backend:** No changes needed  
**Estimated effort:** ~150 lines frontend  
**Risk level:** Low (display-only, no data model changes)

---

## 5. Backward Compatibility Plan

### normalizePetsForDisplay(item) Helper

```javascript
function normalizePetsForDisplay(selectedPetData, originItem) {
  // Priority 1: Multiple fetched PET# records (Release 4B multi-fetch)
  if (selectedPetData.pets && selectedPetData.pets.length > 0) {
    return selectedPetData.pets;
  }
  
  // Priority 2: Single fetched PET# record (current behavior)
  if (selectedPetData.pet_id) {
    return [selectedPetData];  // Wrap in array for consistent interface
  }
  
  // Priority 3: Request pets array (pre-approval, no PET# records yet)
  if (originItem?.pets && originItem.pets.length > 0) {
    return originItem.pets.map(p => ({
      ...p,
      _source: 'request'  // Flag: not yet a PET# record
    }));
  }
  
  // Priority 4: Legacy pet_names string
  if (originItem?.pet_names) {
    return [{
      name: originItem.pet_names,
      care_instructions: originItem.pet_info,
      _source: 'legacy'
    }];
  }
  
  // Fallback
  return [{ name: originItem?.client_name || 'Unknown', _source: 'fallback' }];
}
```

### Display Rules

| Record Type | Pet Tabs? | Fields Shown | Edit Available? |
|-------------|-----------|--------------|-----------------|
| Multi-pet (pet_ids, 2+ PET# records) | ✅ Yes | All structured fields | First pet only (existing) |
| Single pet (pet_id, 1 PET# record) | ❌ No tabs | All structured fields | ✅ Yes (existing) |
| Pre-approval (pets array, no PET# yet) | ✅ Yes (read-only) | From request data | ❌ No |
| Legacy (pet_names string only) | ❌ No tabs | name + care_instructions | ✅ Yes (existing) |

---

## 6. CareCard Tab Enhancements

### Overview Tab (Enhanced)

```
[Pet Avatar/Initial]
Name: Joey
Species: Dog • Breed: Golden Retriever • Age: 3 years
Status: [chip]
```

### Pet Care Tab (Enhanced)

```
Feeding Notes:
  2 cups kibble morning and evening

Medication Notes:
  Heartworm pill monthly (1st of month)

Behavior Notes:
  Friendly, pulls on leash, loves other dogs

Care Instructions:
  [legacy field, shown if present]
```

### Vet & Emergency Tab (Enhanced)

```
── Household Vet ──
Clinic: Happy Paws Veterinary
Vet: Dr. Smith
Phone: 555-1234
Address: 123 Main St

── Emergency Contact ──
Name: Jane Doe
Phone: 555-5678

── Per-Pet Notes (if any) ──
Joey: Allergic to penicillin
Kyle: See specialist for hip issues
```

---

## 7. Validation Checklist

| # | Test | Expected |
|---|------|----------|
| 1 | Open CareCard for multi-pet request (2+ pets) | Pet selector tabs visible |
| 2 | Click each pet tab | Shows that pet's data |
| 3 | Species, breed, age display | Shown in overview |
| 4 | Feeding/medication/behavior notes display | Shown in Pet Care tab |
| 5 | Household vet info display | Shown in Vet & Emergency |
| 6 | Per-pet vet_notes display | Shown under household info |
| 7 | Single-pet request | No tabs, renders as before |
| 8 | Legacy record (pet_names only) | Renders as before |
| 9 | Pre-approval record (no PET# yet) | Shows request pets data (read-only) |
| 10 | Edit first pet | Existing edit flow works |
| 11 | Client phone field on intake | Visible in Step 1 |
| 12 | No console errors | Clean |
| 13 | No API errors | 200 responses |

---

## 8. Risks and Rollback

### Low Risk

1. **Multiple API calls on CareCard open** — For 2-3 pets, this is 2-3 sequential `getPet()` calls. Acceptable latency for admin use. Could add loading indicator.
2. **Pet tabs UI complexity** — Only shown when 2+ pets. Single-pet experience unchanged.
3. **Client phone field** — Single input addition. No backend validation change needed (phone is optional).

### Rollback

- Revert CareCard.jsx → single-pet display returns
- Revert AdminDashboard.jsx → single pet_id fetch returns
- No data affected (display-only changes)

---

## 9. Explicitly Out of Scope

| Item | Reason |
|------|--------|
| Multi-pet editing (edit any pet, not just first) | Adds mutation complexity. Defer to Release 5. |
| Add/remove pets from CareCard | Requires new UI patterns. Defer. |
| PET# record creation from CareCard | Already handled by approval flow. |
| Client Management redesign | Not needed. Search already works. |
| Cognito/portal changes | Not related. |
| Status/lifecycle changes | Not related. |
| Backend API changes | Not needed — existing getPet works. |
| New batch pet endpoint | Nice-to-have but not required for 1-5 pets. |
| Pet photo upload | Separate feature. |
| Quote/payment inline editing | Separate release scope. |
