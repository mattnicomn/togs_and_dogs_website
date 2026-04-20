# MONTHLY ADMIN SOP
**US Mission Hero Operations - Togs & Dogs Project**

---

## **1. Purpose**
This Standard Operating Procedure (SOP) ensures the Togs & Dogs application remains secure, fiscally predictable, and that Ryan is invoiced accurately and on time.

---

## **2. Cadence & Schedule**
- **Date Range**: 1st – 5th of every month.
- **Duration**: ~20 minutes.

---

## **3. Monthly Hygiene Checklist**

### **A. Infrastructure Cost Review (10 mins)**
1. **Open AWS Cost Explorer**: Use the saved view **`Togs & Dogs Monthly Overview`**.
2. **Review Prior Month**: Ensure current project costs align with historical baselines.
3. **Budget Status**: Verify the `togs-and-dogs-prod-monthly-budget` is in "OK" status. 

### **B. Application Integrity (5 mins)**
1. **Login Check**: Log into the Admin Portal as `admin@toganddogs.com`.
2. **Data Review**: Open the **Master Scheduler** and confirm that current intake requests and approved jobs are rendering correctly.
3. **Uptime Verification**: Check CloudFront distribution status via the console.

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
