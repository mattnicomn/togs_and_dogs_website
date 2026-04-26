# Tog and Dogs | Client Operations Portal

This repository contains the frontend for the Tog and Dogs operations platform, powered by **US Mission Hero**. It serves as the primary interface for client intake, administrative scheduling, and staff coordination.

## 🌐 Domain Strategy
- **Marketing**: [toganddogs.com](https://toganddogs.com) (Ryan's public site)
- **Operations**: [toganddogs.usmissionhero.com](https://toganddogs.usmissionhero.com) (This application)

## 🚀 Key Features (Implemented)
### 1. Portal Gateway
- Branded entry point for clients and staff.
- Clear distinction between "Request Pet Care" and "Existing Client / Admin Login".
- Direct navigation back to the marketing site.

### 2. Multi-Step Intake Flow
- Guided 3-step registration process (Contact -> Schedule -> Pet Info).
- Visual progress tracking (stepper) and smooth transitions.
- Polished success screen with Reference ID and next steps.

### 3. Admin Operations Dashboard
- **At a Glance Statistics**: KPI cards for Intake, Assignment needs, and Scheduled visits.
- **Unified Request List**: High-density view for status management and inline staff assignment.
- **Enhanced Care Cards**: Detailed pet profiles with Meet & Greet verification and prominent care instructions.

## 📋 Future Backlog (Proposed)
- [ ] **Auth Enhancements**: Dedicated login and role-based entry routes (e.g., `/login/staff`, `/login/client`).
- [ ] **Advanced Reporting**: Backend `/admin/stats` endpoint for global, system-wide analytics regardless of pagination.
- [ ] **Document/Photo Center**: Support for uploading vaccination records, pet photos, and signed agreements.
- [ ] **Real-time Notifications**: Enhanced email/SMS triggers for status changes and visit completions.
- [ ] **USMH Services Page**: Dedicated "Powered by US Mission Hero" services and productization page.
- [ ] **Client Dashboard**: Logged-in view for clients to track their own requests and past visits.

---
*Created by the Google DeepMind Advanced Agentic Coding Team.*
