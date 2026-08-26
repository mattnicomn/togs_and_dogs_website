export const TERMS_VERSION = 'v1.0';
export const PRIVACY_VERSION = 'v1.0';

export const TERMS_CONTENT = [
  {
    title: 'About These Terms',
    body: 'These Terms of Use govern your use of the pet care operations portal. By submitting a service request or using the client portal, you agree to these terms. If you do not agree, please do not submit a request or use the portal.'
  },
  {
    title: 'Services Provided',
    body: 'In-home pet care services including dog walking, drop-in visits, overnight care, and pet sitting are provided. All services are performed at the client\'s home or a designated location. Services are subject to staff availability, scheduling, and approval by management.'
  },
  {
    title: 'Booking and Scheduling',
    body: '- Service requests are submitted through the online intake form or created by staff on behalf of clients.\n- All requests are reviewed and must be approved before scheduling.\n- Approved bookings are assigned to available staff and added to the operational schedule.\n- Multi-day and selected-date bookings create individual visit records for each scheduled day.\n- Operations management reserves the right to decline, reschedule, or cancel visits due to weather, safety concerns, staffing, or other operational reasons.'
  },
  {
    title: 'Cancellations',
    body: '- Clients may request cancellation of scheduled visits by contacting staff directly or through the portal.\n- Cancellation requests are reviewed by staff and may be approved or denied based on timing and circumstances.\n- Staff may cancel visits at any time for safety or operational reasons and will make reasonable efforts to notify the client.'
  },
  {
    title: 'Client Responsibilities',
    body: '- Provide accurate and complete information about your pets, including health conditions, behavioral issues, medications, and care instructions.\n- Ensure safe and accessible entry to your home, including working locks, secure gates, and current access codes or key locations.\n- Notify staff promptly of any changes to pet health, behavior, household access, or emergency contacts.\n- Maintain current contact information so staff can reach you if needed during a visit.'
  },
  {
    title: 'Offline Client Management',
    body: '- Staff may create and manage client profiles on behalf of clients who prefer not to use the online portal.\n- These profiles are managed entirely by staff. Offline clients do not have self-service portal access unless they later choose to create an account.\n- Offline client records are subject to the same care and data handling standards as portal users.'
  },
  {
    title: 'Communication',
    body: '- Email notifications for booking confirmations, staff assignments, schedule updates, and cancellations are sent to the email address on file.\n- Clients without an email address on file will not receive automated notifications. Staff will communicate with these clients directly.\n- By providing your email address, you consent to receiving service-related communications.'
  },
  {
    title: 'Limitation of Liability',
    body: '- Reasonable care is taken in providing services but management cannot guarantee against all risks associated with pet care.\n- Management is not liable for injuries, property damage, or pet behavior that is beyond reasonable control, including undisclosed health conditions or behavioral issues.\n- Clients are responsible for disclosing known risks, aggressive behavior, escape tendencies, or medical conditions before services begin.'
  },
  {
    title: 'Changes to These Terms',
    body: '- Terms may be updated from time to time. The current version number is displayed on this page.\n- Continued use of services or the portal after changes are published constitutes acceptance of the updated terms.\n- Material changes will be communicated to active clients.'
  }
];

export const PRIVACY_CONTENT = [
  {
    title: 'Information We Collect',
    body: 'We collect information you provide when requesting services or using the portal:\n\n- Contact information: Name, email address, phone number, home address\n- Pet information: Pet names, species, breed, age, feeding instructions, medication details, behavioral notes, vet and emergency contact details\n- Booking information: Requested service dates, time preferences, service type, scheduling notes, preferred staff\n- Account information: Login credentials (managed through AWS Cognito authentication)\n\nWe also collect information created during service delivery:\n- Visit records, staff assignments, scheduling history, cancellation records\n- Communication records (notification delivery status)'
  },
  {
    title: 'How We Use Your Information',
    body: 'We use your information to:\n- Schedule and deliver pet care services\n- Assign appropriate staff to your visits\n- Send booking confirmations, schedule updates, and cancellation notices\n- Maintain care records so staff have accurate pet information during visits\n- Contact you or your emergency contact if an issue arises during a visit\n- Improve our services and operational processes'
  },
  {
    title: 'Third-Party Services',
    body: 'We use the following third-party services to operate the portal:\n\n| Service | Purpose | Data Shared |\n|---------|---------|-------------|\n| **Postmark** | Sending email notifications | Recipient email, notification content |\n| **Google Calendar** | Staff scheduling and visit coordination | Visit dates, times, client name, pet name, service type |\n| **Amazon Web Services (AWS)** | Application hosting, data storage, authentication | All portal data (encrypted at rest) |\n| **AWS Cognito** | User login and authentication | Email, login credentials |\n\nWe do not sell, rent, or share your personal information with unrelated third parties for marketing or advertising purposes.'
  },
  {
    title: 'Who Can See Your Information',
    body: '- Tog and Dogs staff assigned to your visits can see your name, contact info, pet details, care instructions, and access information needed to perform the service.\n- Tog and Dogs administrators can see all client, pet, and booking records for operational management.\n- No one else has access to your information unless required by law.'
  },
  {
    title: 'Data Storage and Security',
    body: '- Your data is stored in encrypted databases on Amazon Web Services (AWS) infrastructure.\n- Access to client data is restricted to authorized Tog and Dogs staff and administrators.\n- We use encrypted connections (HTTPS), access controls, and authentication to protect your information.\n- No system is perfectly secure. We take reasonable precautions but cannot guarantee absolute security.'
  },
  {
    title: 'Data Retention',
    body: '- Active client and pet records are retained for the duration of the service relationship.\n- Completed and cancelled booking records are retained for operational history and reference.\n- Records moved to "Trash" or "Archived" status may be permanently deleted by administrators.\n- You may request a copy of your data or request deletion by contacting us.'
  },
  {
    title: 'Your Rights',
    body: 'You have the right to:\n- Request access to the personal information we hold about you\n- Request correction of inaccurate information\n- Request deletion of your data (subject to reasonable operational recordkeeping needs)\n- Withdraw consent for email notifications by contacting us\n\nTo exercise any of these rights, contact us at support@usmissionhero.com.'
  },
  {
    title: 'Cookies and Tracking',
    body: '- This portal uses session cookies for authentication purposes only.\n- We do not use third-party analytics, advertising cookies, or tracking pixels.\n- No behavioral profiling or cross-site tracking is performed.'
  },
  {
    title: 'Changes to This Policy',
    body: '- We may update this privacy policy from time to time. The current version is displayed on this page.\n- Material changes will be communicated to active clients via email.\n- Continued use of the portal after changes are published constitutes acceptance of the updated policy.'
  }
];
