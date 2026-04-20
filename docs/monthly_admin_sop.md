# MONTHLY ADMIN SOP
**US Mission Hero Operations - Togs & Dogs Project**

---

## **1. Purpose**
This Standard Operating Procedure (SOP) ensures the Togs & Dogs application remains secure, fiscally predictable, and that Ryan is invoiced accurately and on time.

---

## **2. Cadence & Schedule**
- **Date Range**: 1st – 5th of every month.
- **Account**: US Mission Hero Payer Account (**253881689673**).
- **Profile**: `website-infra-sandbox`.
- **Duration**: ~20 minutes.

---

## **3. Monthly Hygiene Checklist**

### **A. Infrastructure Cost Review (10 mins)**
1. **Verify Data (CLI)**: Run the following in your terminal to get the raw billable total:
   ```powershell
   $env:AWS_PROFILE = "website-infra-sandbox"
   aws ce get-cost-and-usage --time-period Start=2026-04-01,End=2026-05-01 --granularity MONTHLY --metrics "UnblendedCost" --filter '{\"Tags\": {\"Key\": \"Client\", \"Values\": [\"TogAndDogs\"]}}'
   ```
2. **Open AWS Cost Explorer**: Use the saved view **`Togs & Dogs Monthly Overview`** in the Payer Account (253881689673).
3. **Review Prior Month**: Ensure current project costs align with historical baselines.
4. **Budget Status**: Verify the `togs-and-dogs-prod-monthly-budget` is in "OK" status. 

### **B. Application Integrity (5 mins)**
1. **Login Check**: Log into the Admin Portal at [toganddogs.usmissionhero.com/admin](https://toganddogs.usmissionhero.com/admin).
2. **Master Scheduler**: Confirm that current intake requests and approved jobs are rendering correctly.
3. **Uptime Verification**: Check CloudFront distribution status (E35L00QPA2IRCY) via the console.

### **C. Daily/Weekly Operational Gating**
1. **Meet & Greet Verification**:
   - Locate records in **PENDING_REVIEW** or **READY_FOR_APPROVAL**.
   - After confirming Google Calendar invite completion, click **`Mark M&G Complete`** in the Admin Dashboard Actions column.
   - This unblocks the **`Approve & Job Creation`** flow.
2. **Staff Assignment**:
   - For records in **JOB_CREATED** or **APPROVED**, ensure a staff member is assigned.
   - Use the **`Assign Staff`** dropdown to select the primary worker (e.g., Ryan, Wife, Nephew).
   - Verify the worker ID appears in the **Staff** column to ensure the job is active.
3. **Pet Profile Hygiene**:
   - Periodically open **Care Cards** for active jobs.
   - Verify Vet and Emergency Contact info is populated; update as needed to ensure safety data is current.

---

## **4. Invoicing Workflow**

1. **Open Invoice Template**: Use `docs/client_invoice_template.md`.
2. **Data Entry**:
   - Transfer total spend for the *Project: TogsAndDogs* tag into the AWS section.
   - Confirm with project lead if any enhancement change requests or hourly work was approved.
3. **Finalize & File**:
   - Export invoice as PDF (`INV-YYYYMM-01.pdf`).
   - Send to Ryan via Email.
   - Archive the PDF in the US Mission Hero client folder.

---

## **5. Escalation & Issue Log Review**

- **Project Breaches**: If an AWS Budget alert hits `mbn@usmissionhero.com`, investigate the Cost Explorer for usage spikes (e.g., unexpected S3 scan or Lambda timeout).
- **Bug Reports**: Review the project `CHANGELOG.md` for any issues resolved during the month and ensure they are mentioned in the maintenance report to Ryan.

---

## **6. Emergency Contacts**
- **Primary**: Matthew Nico (@mattnicomn)
- **Technical**: US Mission Hero Platform Lead
- **Client**: Ryan (@toganddogs)
