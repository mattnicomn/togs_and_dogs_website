import json

class NotificationTemplates:
    """Polished, Tog and Dogs branded notification templates."""

    @staticmethod
    def get_template(event_type, context):
        """
        Returns (subject, body_text, body_html) for a given event.
        """
        # Normalize data for friendly rendering
        friendly_context = NotificationTemplates.normalize_context(context)
        
        if event_type == 'REQUEST_RECEIVED':
            return NotificationTemplates.request_received(friendly_context)
        elif event_type == 'CUSTOMER_APPROVED':
            return NotificationTemplates.customer_approved(friendly_context)
        elif event_type == 'VISIT_SCHEDULED':
            return NotificationTemplates.visit_scheduled(friendly_context)
        elif event_type == 'STAFF_ASSIGNED':
            return NotificationTemplates.staff_assigned(friendly_context)
        elif event_type == 'VISIT_CANCELLED':
            return NotificationTemplates.visit_cancelled(friendly_context)
        elif event_type == 'VISIT_TIME_CHANGED':
            return NotificationTemplates.visit_time_changed(friendly_context)
        elif event_type == 'WELCOME_INVITE_STAFF':
            return NotificationTemplates.welcome_invite_staff(friendly_context)
        elif event_type == 'WELCOME_INVITE_CLIENT':
            return NotificationTemplates.welcome_invite_client(friendly_context)
        elif event_type == 'WELCOME_INVITE':
            # Generic fallback
            return NotificationTemplates.welcome_invite_client(friendly_context)
        
        return None, None, None

    @staticmethod
    def _safe(value, default=''):
        """Returns value as a string, or default if value is None/empty."""
        if value is None:
            return default
        return str(value) if not isinstance(value, str) else value

    @staticmethod
    def normalize_context(context):
        """Safely renders friendly labels for raw data."""
        normalized = dict(context)
        safe = NotificationTemplates._safe
        
        # 1. Fallbacks for names
        normalized['client_name'] = safe(context.get('client_name'), 'Valued Client') or 'Valued Client'
        normalized['staff_name'] = safe(context.get('staff_name'), 'Team Member') or 'Team Member'
        normalized['user_name'] = safe(context.get('client_name'), '') or safe(context.get('staff_name'), '') or 'Valued Member'
        normalized['pet_names'] = safe(context.get('pet_names'), 'your pets') or 'your pets'
        
        # 2. Service type mapping (null-safe: service_type may be None even if key exists)
        service_type = context.get('service_type') or 'PET_SITTING'
        friendly_services = {
            'WALK_30MIN': '30-Minute Walk',
            'WALK_60MIN': '60-Minute Walk',
            'DROPIN_1HR': '1-Hour Drop-in',
            'DROPIN_3HR': '3-Hour Drop-in',
            'OVERNIGHT': 'Overnight Care',
            'PET_SITTING': 'Pet Sitting',
            'MEET_GREET': 'Meet & Greet'
        }
        normalized['service_label'] = friendly_services.get(service_type, service_type.replace('_', ' ').title())
        
        # 3. Date/Time normalization (if present)
        date_val = safe(context.get('start_date'), 'scheduled date') or 'scheduled date'
        time_val = context.get('start_time')
        normalized['date_label'] = f"{date_val} at {time_val}" if time_val else date_val
        
        return normalized

    @staticmethod
    def customer_approved(ctx):
        """Approval confirmation email sent to the client."""
        subject = "Your Tog & Dogs Request Has Been Approved!"
        client_name = ctx.get('client_name', 'Valued Client')
        pet_names = ctx.get('pet_names', 'your pets')
        service_label = ctx.get('service_label', 'Pet Sitting')
        date_label = ctx.get('date_label', 'your scheduled date')
        portal_url = ctx.get('portal_url', 'https://toganddogs.usmissionhero.com')

        body_text = (
            f"Hi {client_name},\n\n"
            f"Great news! Your {service_label} request for {pet_names} has been approved.\n\n"
            f"BOOKING DETAILS:\n"
            f"- Service: {service_label}\n"
            f"- Pet(s): {pet_names}\n"
            f"- Date: {date_label}\n\n"
            f"WHAT HAPPENS NEXT:\n"
            f"1. A team member will be assigned to your visit shortly.\n"
            f"2. You'll receive a confirmation once your sitter is confirmed.\n"
            f"3. You can view your booking details anytime in the client portal.\n\n"
            f"Access your portal: {portal_url}\n\n"
            f"If you have any questions or need to make changes, please reply to this email "
            f"or contact us through the portal.\n\n"
            f"Thank you for choosing Tog & Dogs!\n\n"
            f"Best,\n"
            f"The Tog & Dogs Team"
        )

        body_html = f"""
        <html>
        <body style="font-family: Arial, Helvetica, sans-serif; line-height: 1.6; color: #333; background-color: #f4f7f6; padding: 20px;">
            <div style="max-width: 600px; margin: auto; border: 1px solid #e0e0e0; background-color: #ffffff; padding: 40px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.05);">
                <div style="text-align: center; margin-bottom: 30px;">
                    <h1 style="color: #2c3e50; margin: 0; font-size: 24px; font-weight: bold;">Request Approved!</h1>
                    <div style="width: 50px; height: 4px; background: #27ae60; margin: 15px auto; border-radius: 2px;"></div>
                </div>

                <p>Hi <strong>{client_name}</strong>,</p>

                <p>Great news! Your <strong>{service_label}</strong> request for <strong>{pet_names}</strong> has been approved.</p>

                <div style="background-color: #f9fdfa; border-left: 4px solid #27ae60; padding: 20px; margin: 25px 0; border-radius: 0 8px 8px 0;">
                    <p style="margin: 0 0 12px 0; font-weight: bold; color: #2c3e50;">Booking Details</p>
                    <table style="width: 100%; border-collapse: collapse; font-size: 14px; color: #555;">
                        <tr>
                            <td style="padding: 6px 0; font-weight: bold; width: 100px;">Service:</td>
                            <td style="padding: 6px 0;">{service_label}</td>
                        </tr>
                        <tr>
                            <td style="padding: 6px 0; font-weight: bold;">Pet(s):</td>
                            <td style="padding: 6px 0;">{pet_names}</td>
                        </tr>
                        <tr>
                            <td style="padding: 6px 0; font-weight: bold;">Date:</td>
                            <td style="padding: 6px 0;">{date_label}</td>
                        </tr>
                    </table>
                </div>

                <div style="background-color: #fff9eb; border: 1px solid #ffeeba; padding: 20px; border-radius: 8px; font-size: 14px; color: #856404; margin: 25px 0;">
                    <p style="margin: 0 0 10px 0; font-weight: bold;">What happens next:</p>
                    <ol style="margin: 0; padding-left: 20px;">
                        <li style="margin-bottom: 6px;">A team member will be assigned to your visit shortly.</li>
                        <li style="margin-bottom: 6px;">You'll receive a confirmation once your sitter is confirmed.</li>
                        <li style="margin-bottom: 6px;">You can view your booking details anytime in the client portal.</li>
                    </ol>
                </div>

                <div style="text-align: center; margin: 35px 0;">
                    <a href="{portal_url}" style="background-color: #27ae60; color: #ffffff; padding: 14px 30px; text-decoration: none; border-radius: 8px; font-weight: bold; display: inline-block;">View in Portal</a>
                </div>

                <p>If you have any questions or need to make changes, simply reply to this email or reach out through the portal.</p>

                <p style="margin-top: 25px;">Thank you for choosing Tog & Dogs!</p>

                <hr style="border: 0; border-top: 1px solid #eee; margin: 30px 0;" />

                <div style="text-align: center; color: #7f8c8d; font-size: 12px;">
                    <p style="margin: 5px 0;">&copy; 2026 Tog & Dogs Pet Sitting</p>
                    <p style="margin: 5px 0;">Premium Pet Care & Management</p>
                </div>
            </div>
        </body>
        </html>
        """
        return subject, body_text, body_html

    @staticmethod
    def request_received(ctx):
        """Admin notification when a new request is submitted. Branded internal template."""
        safe = NotificationTemplates._safe
        client_name = safe(ctx.get('client_name'), 'Unknown Client') or 'Unknown Client'
        client_email = safe(ctx.get('client_email'), '')
        client_phone = safe(ctx.get('client_phone'), '')
        pet_names = safe(ctx.get('pet_names'), 'Not specified') or 'Not specified'
        service_label = safe(ctx.get('service_label'), 'Pet Sitting') or 'Pet Sitting'
        date_label = safe(ctx.get('date_label'), 'Not specified') or 'Not specified'
        request_id = safe(ctx.get('request_id'), 'N/A') or 'N/A'
        details = safe(ctx.get('details'), '')
        dashboard_url = 'https://toganddogs.usmissionhero.com'

        # Build contact line for plain text
        contact_parts = []
        if client_email:
            contact_parts.append(f"Email: {client_email}")
        if client_phone:
            contact_parts.append(f"Phone: {client_phone}")
        contact_line = " | ".join(contact_parts) if contact_parts else "No contact info available"

        subject = f"New Request: {client_name} — {service_label}"
        body_text = (
            f"NEW REQUEST RECEIVED\n"
            f"{'=' * 40}\n\n"
            f"Client: {client_name}\n"
            f"{contact_line}\n\n"
            f"REQUEST DETAILS:\n"
            f"- Service: {service_label}\n"
            f"- Pet(s): {pet_names}\n"
            f"- Requested Date: {date_label}\n"
            f"- Request ID: {request_id}\n"
        )
        if details and details != 'No details provided.':
            body_text += f"- Notes: {details}\n"
        body_text += (
            f"\nACTION REQUIRED:\n"
            f"Please review this request in the admin dashboard:\n"
            f"{dashboard_url}\n\n"
            f"— Tog & Dogs Notification System"
        )

        # Build contact HTML rows
        contact_rows = ""
        if client_email:
            contact_rows += f"""
                        <tr>
                            <td style="padding: 6px 0; font-weight: bold;">Email:</td>
                            <td style="padding: 6px 0;"><a href="mailto:{client_email}" style="color: #2980b9;">{client_email}</a></td>
                        </tr>"""
        if client_phone:
            contact_rows += f"""
                        <tr>
                            <td style="padding: 6px 0; font-weight: bold;">Phone:</td>
                            <td style="padding: 6px 0;">{client_phone}</td>
                        </tr>"""

        # Build details row
        details_section = ""
        if details and details != 'No details provided.':
            details_section = f"""
                <div style="background-color: #f8f9fa; border: 1px solid #e9ecef; padding: 15px; border-radius: 8px; margin: 20px 0; font-size: 14px; color: #555;">
                    <p style="margin: 0 0 5px 0; font-weight: bold; color: #2c3e50;">Client Notes:</p>
                    <p style="margin: 0; white-space: pre-wrap;">{details}</p>
                </div>"""

        body_html = f"""
        <html>
        <body style="font-family: Arial, Helvetica, sans-serif; line-height: 1.6; color: #333; background-color: #f4f7f6; padding: 20px;">
            <div style="max-width: 600px; margin: auto; border: 1px solid #e0e0e0; background-color: #ffffff; padding: 40px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.05);">
                <div style="text-align: center; margin-bottom: 30px;">
                    <h1 style="color: #2c3e50; margin: 0; font-size: 24px; font-weight: bold;">New Request Received</h1>
                    <div style="width: 50px; height: 4px; background: #e67e22; margin: 15px auto; border-radius: 2px;"></div>
                </div>

                <p>A new service request has been submitted and is awaiting review.</p>

                <div style="background-color: #fef9f4; border-left: 4px solid #e67e22; padding: 20px; margin: 25px 0; border-radius: 0 8px 8px 0;">
                    <p style="margin: 0 0 12px 0; font-weight: bold; color: #2c3e50;">Client Information</p>
                    <table style="width: 100%; border-collapse: collapse; font-size: 14px; color: #555;">
                        <tr>
                            <td style="padding: 6px 0; font-weight: bold; width: 120px;">Client:</td>
                            <td style="padding: 6px 0;"><strong>{client_name}</strong></td>
                        </tr>{contact_rows}
                    </table>
                </div>

                <div style="background-color: #f9fdfa; border-left: 4px solid #27ae60; padding: 20px; margin: 25px 0; border-radius: 0 8px 8px 0;">
                    <p style="margin: 0 0 12px 0; font-weight: bold; color: #2c3e50;">Request Details</p>
                    <table style="width: 100%; border-collapse: collapse; font-size: 14px; color: #555;">
                        <tr>
                            <td style="padding: 6px 0; font-weight: bold; width: 120px;">Service:</td>
                            <td style="padding: 6px 0;">{service_label}</td>
                        </tr>
                        <tr>
                            <td style="padding: 6px 0; font-weight: bold;">Pet(s):</td>
                            <td style="padding: 6px 0;">{pet_names}</td>
                        </tr>
                        <tr>
                            <td style="padding: 6px 0; font-weight: bold;">Date:</td>
                            <td style="padding: 6px 0;">{date_label}</td>
                        </tr>
                        <tr>
                            <td style="padding: 6px 0; font-weight: bold;">Request ID:</td>
                            <td style="padding: 6px 0; font-family: monospace; font-size: 12px;">{request_id}</td>
                        </tr>
                    </table>
                </div>
                {details_section}
                <div style="text-align: center; margin: 35px 0;">
                    <a href="{dashboard_url}" style="background-color: #e67e22; color: #ffffff; padding: 14px 30px; text-decoration: none; border-radius: 8px; font-weight: bold; display: inline-block;">Review in Dashboard</a>
                </div>

                <hr style="border: 0; border-top: 1px solid #eee; margin: 30px 0;" />

                <div style="text-align: center; color: #7f8c8d; font-size: 12px;">
                    <p style="margin: 5px 0;">&copy; 2026 Tog & Dogs Pet Sitting</p>
                    <p style="margin: 5px 0;">Admin Notification System</p>
                </div>
            </div>
        </body>
        </html>
        """
        return subject, body_text, body_html

    @staticmethod
    def visit_scheduled(ctx):
        """Client notification when their visit is confirmed with an assigned sitter."""
        safe = NotificationTemplates._safe
        client_name = safe(ctx.get('client_name'), 'Valued Client') or 'Valued Client'
        pet_names = safe(ctx.get('pet_names'), 'your pets') or 'your pets'
        service_label = safe(ctx.get('service_label'), 'Pet Sitting') or 'Pet Sitting'
        date_label = safe(ctx.get('date_label'), 'your scheduled date') or 'your scheduled date'
        # Use worker_name (only set when a real worker is assigned) — do NOT fall back to
        # staff_name which normalize_context defaults to 'Team Member'
        staff_name = safe(ctx.get('worker_name'), '') or ''
        if not staff_name:
            # Check if staff_name is a real value (not the 'Team Member' default)
            raw_staff = safe(ctx.get('staff_name'), '')
            if raw_staff and raw_staff != 'Team Member':
                staff_name = raw_staff
        portal_url = safe(ctx.get('portal_url'), 'https://toganddogs.usmissionhero.com')

        # Build sitter line only if we have a name
        sitter_text = f"Your sitter: {staff_name}\n" if staff_name else ""
        sitter_row = ""
        if staff_name:
            sitter_row = f"""
                        <tr>
                            <td style="padding: 6px 0; font-weight: bold;">Your Sitter:</td>
                            <td style="padding: 6px 0;">{staff_name}</td>
                        </tr>"""

        subject = f"Your {service_label} Visit Is Confirmed — Tog & Dogs"
        body_text = (
            f"Hi {client_name},\n\n"
            f"Great news! Your {service_label} visit for {pet_names} has been confirmed.\n\n"
            f"VISIT DETAILS:\n"
            f"- Service: {service_label}\n"
            f"- Pet(s): {pet_names}\n"
            f"- Date: {date_label}\n"
            f"{sitter_text}\n"
            f"WHAT TO EXPECT:\n"
            f"1. Your sitter will arrive at the scheduled time.\n"
            f"2. Visit notes will be available in your portal after the visit.\n"
            f"3. You can view or manage your booking anytime in the client portal.\n\n"
            f"Access your portal: {portal_url}\n\n"
            f"If you need to make changes or have questions, please reply to this email.\n\n"
            f"Best,\n"
            f"The Tog & Dogs Team"
        )

        body_html = f"""
        <html>
        <body style="font-family: Arial, Helvetica, sans-serif; line-height: 1.6; color: #333; background-color: #f4f7f6; padding: 20px;">
            <div style="max-width: 600px; margin: auto; border: 1px solid #e0e0e0; background-color: #ffffff; padding: 40px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.05);">
                <div style="text-align: center; margin-bottom: 30px;">
                    <h1 style="color: #2c3e50; margin: 0; font-size: 24px; font-weight: bold;">Visit Confirmed!</h1>
                    <div style="width: 50px; height: 4px; background: #2980b9; margin: 15px auto; border-radius: 2px;"></div>
                </div>

                <p>Hi <strong>{client_name}</strong>,</p>

                <p>Your <strong>{service_label}</strong> visit for <strong>{pet_names}</strong> has been confirmed and a sitter has been assigned.</p>

                <div style="background-color: #f0f7fd; border-left: 4px solid #2980b9; padding: 20px; margin: 25px 0; border-radius: 0 8px 8px 0;">
                    <p style="margin: 0 0 12px 0; font-weight: bold; color: #2c3e50;">Visit Details</p>
                    <table style="width: 100%; border-collapse: collapse; font-size: 14px; color: #555;">
                        <tr>
                            <td style="padding: 6px 0; font-weight: bold; width: 100px;">Service:</td>
                            <td style="padding: 6px 0;">{service_label}</td>
                        </tr>
                        <tr>
                            <td style="padding: 6px 0; font-weight: bold;">Pet(s):</td>
                            <td style="padding: 6px 0;">{pet_names}</td>
                        </tr>
                        <tr>
                            <td style="padding: 6px 0; font-weight: bold;">Date:</td>
                            <td style="padding: 6px 0;">{date_label}</td>
                        </tr>{sitter_row}
                    </table>
                </div>

                <div style="background-color: #fff9eb; border: 1px solid #ffeeba; padding: 20px; border-radius: 8px; font-size: 14px; color: #856404; margin: 25px 0;">
                    <p style="margin: 0 0 10px 0; font-weight: bold;">What to expect:</p>
                    <ol style="margin: 0; padding-left: 20px;">
                        <li style="margin-bottom: 6px;">Your sitter will arrive at the scheduled time.</li>
                        <li style="margin-bottom: 6px;">Visit notes will be available in your portal after the visit.</li>
                        <li style="margin-bottom: 6px;">You can view or manage your booking anytime.</li>
                    </ol>
                </div>

                <div style="text-align: center; margin: 35px 0;">
                    <a href="{portal_url}" style="background-color: #2980b9; color: #ffffff; padding: 14px 30px; text-decoration: none; border-radius: 8px; font-weight: bold; display: inline-block;">View in Portal</a>
                </div>

                <p>If you need to make changes or have questions, simply reply to this email.</p>

                <hr style="border: 0; border-top: 1px solid #eee; margin: 30px 0;" />

                <div style="text-align: center; color: #7f8c8d; font-size: 12px;">
                    <p style="margin: 5px 0;">&copy; 2026 Tog & Dogs Pet Sitting</p>
                    <p style="margin: 5px 0;">Premium Pet Care & Management</p>
                </div>
            </div>
        </body>
        </html>
        """
        return subject, body_text, body_html

    @staticmethod
    def staff_assigned(ctx):
        """Staff notification when assigned to a visit. Branded internal template."""
        safe = NotificationTemplates._safe
        staff_name = safe(ctx.get('staff_name'), '') or safe(ctx.get('worker_name'), '') or 'Team Member'
        client_name = safe(ctx.get('client_name'), 'a client') or 'a client'
        client_phone = safe(ctx.get('client_phone'), '')
        pet_names = safe(ctx.get('pet_names'), 'their pets') or 'their pets'
        service_label = safe(ctx.get('service_label'), 'Pet Sitting') or 'Pet Sitting'
        date_label = safe(ctx.get('date_label'), 'scheduled date') or 'scheduled date'
        details = safe(ctx.get('details'), '')
        portal_url = safe(ctx.get('portal_url'), 'https://toganddogs.usmissionhero.com')

        # Build client phone row
        phone_row = ""
        phone_text = ""
        if client_phone:
            phone_row = f"""
                        <tr>
                            <td style="padding: 6px 0; font-weight: bold;">Client Phone:</td>
                            <td style="padding: 6px 0;">{client_phone}</td>
                        </tr>"""
            phone_text = f"- Client Phone: {client_phone}\n"

        # Build details section
        details_section = ""
        details_text = ""
        if details and details != 'No details provided.':
            details_section = f"""
                <div style="background-color: #f8f9fa; border: 1px solid #e9ecef; padding: 15px; border-radius: 8px; margin: 20px 0; font-size: 14px; color: #555;">
                    <p style="margin: 0 0 5px 0; font-weight: bold; color: #2c3e50;">Care Notes:</p>
                    <p style="margin: 0; white-space: pre-wrap;">{details}</p>
                </div>"""
            details_text = f"- Care Notes: {details}\n"

        subject = f"New Assignment: {service_label} — {client_name}"
        body_text = (
            f"Hi {staff_name},\n\n"
            f"You've been assigned a new visit.\n\n"
            f"ASSIGNMENT DETAILS:\n"
            f"- Client: {client_name}\n"
            f"{phone_text}"
            f"- Pet(s): {pet_names}\n"
            f"- Service: {service_label}\n"
            f"- Date: {date_label}\n"
            f"{details_text}\n"
            f"Please check the staff portal for full care instructions and client details.\n\n"
            f"Access your portal: {portal_url}\n\n"
            f"If you have questions or need to discuss this assignment, please reply to this email.\n\n"
            f"Best,\n"
            f"The Tog & Dogs Management Team"
        )

        body_html = f"""
        <html>
        <body style="font-family: Arial, Helvetica, sans-serif; line-height: 1.6; color: #333; background-color: #f4f7f6; padding: 20px;">
            <div style="max-width: 600px; margin: auto; border: 1px solid #e0e0e0; background-color: #ffffff; padding: 40px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.05);">
                <div style="text-align: center; margin-bottom: 30px;">
                    <h1 style="color: #2c3e50; margin: 0; font-size: 24px; font-weight: bold;">New Assignment</h1>
                    <div style="width: 50px; height: 4px; background: #8e44ad; margin: 15px auto; border-radius: 2px;"></div>
                </div>

                <p>Hi <strong>{staff_name}</strong>,</p>

                <p>You've been assigned a new <strong>{service_label}</strong> visit. Here are the details:</p>

                <div style="background-color: #f8f4fb; border-left: 4px solid #8e44ad; padding: 20px; margin: 25px 0; border-radius: 0 8px 8px 0;">
                    <p style="margin: 0 0 12px 0; font-weight: bold; color: #2c3e50;">Assignment Details</p>
                    <table style="width: 100%; border-collapse: collapse; font-size: 14px; color: #555;">
                        <tr>
                            <td style="padding: 6px 0; font-weight: bold; width: 120px;">Client:</td>
                            <td style="padding: 6px 0;"><strong>{client_name}</strong></td>
                        </tr>{phone_row}
                        <tr>
                            <td style="padding: 6px 0; font-weight: bold;">Pet(s):</td>
                            <td style="padding: 6px 0;">{pet_names}</td>
                        </tr>
                        <tr>
                            <td style="padding: 6px 0; font-weight: bold;">Service:</td>
                            <td style="padding: 6px 0;">{service_label}</td>
                        </tr>
                        <tr>
                            <td style="padding: 6px 0; font-weight: bold;">Date:</td>
                            <td style="padding: 6px 0;">{date_label}</td>
                        </tr>
                    </table>
                </div>
                {details_section}
                <div style="text-align: center; margin: 35px 0;">
                    <a href="{portal_url}" style="background-color: #8e44ad; color: #ffffff; padding: 14px 30px; text-decoration: none; border-radius: 8px; font-weight: bold; display: inline-block;">View in Staff Portal</a>
                </div>

                <p>Please review the full care instructions and client details in the portal before your visit.</p>

                <hr style="border: 0; border-top: 1px solid #eee; margin: 30px 0;" />

                <div style="text-align: center; color: #7f8c8d; font-size: 12px;">
                    <p style="margin: 5px 0;">&copy; 2026 Tog & Dogs Pet Sitting</p>
                    <p style="margin: 5px 0;">Staff Management System</p>
                </div>
            </div>
        </body>
        </html>
        """
        return subject, body_text, body_html

    @staticmethod
    def visit_cancelled(ctx):
        """Cancellation notification. Stub — minimal template."""
        client_name = ctx.get('client_name', 'Valued Client')
        pet_names = ctx.get('pet_names', 'your pets')
        service_label = ctx.get('service_label', 'Pet Sitting')
        date_label = ctx.get('date_label', 'scheduled date')

        subject = f"Visit Cancelled — {service_label} for {pet_names}"
        body_text = (
            f"Hi {client_name},\n\n"
            f"Your {service_label} visit for {pet_names} on {date_label} has been cancelled.\n\n"
            f"If you have questions, please reply to this email.\n\nBest,\nThe Tog & Dogs Team"
        )
        body_html = f"""
        <html><body style="font-family: Arial, sans-serif; padding: 20px;">
        <h2>Visit Cancelled</h2>
        <p>Hi <strong>{client_name}</strong>,</p>
        <p>Your <strong>{service_label}</strong> visit for <strong>{pet_names}</strong> on {date_label} has been cancelled.</p>
        <p>If you have questions, please reply to this email.</p>
        <p>Best,<br/>The Tog & Dogs Team</p>
        </body></html>
        """
        return subject, body_text, body_html

    @staticmethod
    def visit_time_changed(ctx):
        """Time change notification. Stub — minimal template."""
        client_name = ctx.get('client_name', 'Valued Client')
        pet_names = ctx.get('pet_names', 'your pets')
        service_label = ctx.get('service_label', 'Pet Sitting')
        date_label = ctx.get('date_label', 'updated date')

        subject = f"Visit Time Updated — {service_label} for {pet_names}"
        body_text = (
            f"Hi {client_name},\n\n"
            f"The time for your {service_label} visit for {pet_names} has been updated.\n"
            f"New date/time: {date_label}\n\n"
            f"If you have questions, please reply to this email.\n\nBest,\nThe Tog & Dogs Team"
        )
        body_html = f"""
        <html><body style="font-family: Arial, sans-serif; padding: 20px;">
        <h2>Visit Time Updated</h2>
        <p>Hi <strong>{client_name}</strong>,</p>
        <p>The time for your <strong>{service_label}</strong> visit for <strong>{pet_names}</strong> has been updated.</p>
        <p><strong>New date/time:</strong> {date_label}</p>
        <p>If you have questions, please reply to this email.</p>
        <p>Best,<br/>The Tog & Dogs Team</p>
        </body></html>
        """
        return subject, body_text, body_html

    @staticmethod
    def welcome_invite_staff(ctx):
        subject = "You're invited to the Tog & Dogs Staff Portal"
        portal_url = ctx.get('portal_url', 'https://toganddogs.usmissionhero.com')
        staff_name = ctx.get('staff_name', 'Team Member')
        temp_password = ctx.get('temp_password')
        
        password_section_text = f"Temporary Password: {temp_password}\n" if temp_password else "Please check your inbox for a separate email containing your temporary password."
        
        body_text = (
            f"Hi {staff_name},\n\n"
            f"Welcome to the Tog & Dogs team! We've set up your access to our Staff Portal where you can manage "
            f"your schedule, review assignments, and stay connected with the team.\n\n"
            f"Access your portal here: {portal_url}\n\n"
            f"SETUP INSTRUCTIONS:\n"
            f"1. {password_section_text}\n"
            f"2. Log in using the portal link above and your email address.\n"
            f"3. You will be prompted to set a permanent password upon your first login.\n\n"
            f"Once logged in, you can view your upcoming visits, manage client care notes, and update your availability.\n\n"
            f"If you have any questions or need assistance, please contact Ryan or reply to this email.\n\n"
            f"Best,\n"
            f"The Tog & Dogs Management Team"
        )
        
        password_html = f"""
                <div style="background-color: #fff9eb; border: 1px solid #ffeeba; padding: 20px; border-radius: 8px; font-size: 14px; color: #856404; margin: 25px 0;">
                    <p style="margin: 0 0 10px 0;"><strong>Setup Instructions:</strong></p>
                    <ul style="margin: 0; padding-left: 20px;">
                        <li><strong>Your Temporary Password:</strong> <span style="font-family: monospace; font-size: 16px; background: #eee; padding: 2px 6px; border-radius: 4px;">{temp_password}</span></li>
                        <li>Log in using your email address and the password above.</li>
                        <li>You will be prompted to set a permanent password upon your first login.</li>
                    </ul>
                </div>
        """ if temp_password else f"""
                <div style="background-color: #fff9eb; border: 1px solid #ffeeba; padding: 20px; border-radius: 8px; font-size: 14px; color: #856404; margin: 25px 0;">
                    <p style="margin: 0 0 10px 0;"><strong>Setup Instructions:</strong></p>
                    <ul style="margin: 0; padding-left: 20px;">
                        <li>Check your inbox for a separate email from Cognito (Tog & Dogs) containing your <strong>temporary password</strong>.</li>
                        <li>Log in using your email address and that temporary password.</li>
                        <li>You will be prompted to set a permanent password upon your first login.</li>
                    </ul>
                </div>
        """

        body_html = f"""
        <html>
        <body style="font-family: Arial, Helvetica, sans-serif; line-height: 1.6; color: #333; background-color: #f4f7f6; padding: 20px;">
            <div style="max-width: 600px; margin: auto; border: 1px solid #e0e0e0; background-color: #ffffff; padding: 40px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.05);">
                <div style="text-align: center; margin-bottom: 30px;">
                    <h1 style="color: #2c3e50; margin: 0; font-size: 24px; font-weight: bold;">Tog & Dogs Staff Portal</h1>
                    <div style="width: 50px; height: 4px; background: #8e44ad; margin: 15px auto; border-radius: 2px;"></div>
                </div>
                
                <p>Hi <strong>{staff_name}</strong>,</p>
                
                <p>Welcome to the team! We're excited to have you with us. Your access to the Tog & Dogs Staff Portal is now ready.</p>
                
                <div style="background-color: #f8f4fb; border-left: 4px solid #8e44ad; padding: 20px; margin: 25px 0; border-radius: 0 8px 8px 0;">
                    <p style="margin: 0; font-weight: bold; color: #2c3e50;">In the staff portal you can:</p>
                    <ul style="margin: 10px 0 0 0; padding-left: 20px; color: #555;">
                        <li>View and manage your visit assignments</li>
                        <li>Access client care instructions and pet details</li>
                        <li>Log visit notes and updates</li>
                        <li>Manage your profile and availability</li>
                    </ul>
                </div>
                
                <div style="text-align: center; margin: 35px 0;">
                    <a href="{portal_url}" style="background-color: #8e44ad; color: #ffffff; padding: 14px 30px; text-decoration: none; border-radius: 8px; font-weight: bold; display: inline-block;">Access Staff Portal</a>
                </div>
                
                {password_html}
                
                <p style="margin-top: 30px;">We look forward to working with you!</p>
                
                <hr style="border: 0; border-top: 1px solid #eee; margin: 30px 0;" />
                
                <div style="text-align: center; color: #7f8c8d; font-size: 12px;">
                    <p style="margin: 5px 0;">&copy; 2026 Tog & Dogs Pet Sitting</p>
                    <p style="margin: 5px 0;">Team Management System</p>
                </div>
            </div>
        </body>
        </html>
        """
        return subject, body_text, body_html

    @staticmethod
    def welcome_invite_client(ctx):
        subject = "Your Tog & Dogs Client Portal Account Is Ready"
        portal_url = ctx.get('portal_url', 'https://toganddogs.usmissionhero.com')
        client_name = ctx.get('client_name', 'Valued Client')
        temp_password = ctx.get('temp_password')
        
        password_section_text = f"Temporary Password: {temp_password}\n" if temp_password else "Please check your inbox for a separate email containing your temporary password."

        body_text = (
            f"Hi {client_name},\n\n"
            f"Welcome to Tog & Dogs! Your client portal account is now ready. The portal is your "
            f"one-stop shop for managing your bookings, updating pet care details, and staying connected with our team.\n\n"
            f"Access your portal here: {portal_url}\n\n"
            f"LOGIN INSTRUCTIONS:\n"
            f"1. {password_section_text}\n"
            f"2. Log in using your email address and the password provided.\n"
            f"3. You'll be prompted to set a secure permanent password during your first login.\n\n"
            f"In the portal, you can request new visits, view your schedule, and update important details about your pets' care.\n\n"
            f"If you have any questions, please reply to this email or contact us at any time.\n\n"
            f"Best,\n"
            f"The Tog & Dogs Team"
        )
        
        password_html = f"""
                <div style="background-color: #fff9eb; border: 1px solid #ffeeba; padding: 20px; border-radius: 8px; font-size: 14px; color: #856404; margin: 25px 0;">
                    <p style="margin: 0 0 10px 0;"><strong>Setup Instructions:</strong></p>
                    <ul style="margin: 0; padding-left: 20px;">
                        <li><strong>Your Temporary Password:</strong> <span style="font-family: monospace; font-size: 16px; background: #eee; padding: 2px 6px; border-radius: 4px;">{temp_password}</span></li>
                        <li>Log in using your email address and the password above.</li>
                        <li>You will be prompted to set a secure permanent password upon your first login.</li>
                    </ul>
                </div>
        """ if temp_password else f"""
                <div style="background-color: #fff9eb; border: 1px solid #ffeeba; padding: 20px; border-radius: 8px; font-size: 14px; color: #856404; margin: 25px 0;">
                    <p style="margin: 0 0 10px 0;"><strong>Setup Instructions:</strong></p>
                    <ul style="margin: 0; padding-left: 20px;">
                        <li>Check your inbox for a separate email from Cognito (Tog & Dogs) containing your <strong>temporary password</strong>.</li>
                        <li>Log in using your email address and that temporary password.</li>
                        <li>You'll be prompted to set a secure permanent password upon your first login.</li>
                    </ul>
                </div>
        """

        body_html = f"""
        <html>
        <body style="font-family: Arial, Helvetica, sans-serif; line-height: 1.6; color: #333; background-color: #f4f7f6; padding: 20px;">
            <div style="max-width: 600px; margin: auto; border: 1px solid #e0e0e0; background-color: #ffffff; padding: 40px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.05);">
                <div style="text-align: center; margin-bottom: 30px;">
                    <h1 style="color: #2c3e50; margin: 0; font-size: 24px; font-weight: bold;">Welcome to Tog & Dogs!</h1>
                    <div style="width: 50px; height: 4px; background: #27ae60; margin: 15px auto; border-radius: 2px;"></div>
                </div>
                
                <p>Hi <strong>{client_name}</strong>,</p>
                
                <p>We're thrilled to have you as part of the Tog & Dogs family! Your portal access is now ready for you to use.</p>
                
                <div style="background-color: #f9fdfa; border-left: 4px solid #27ae60; padding: 20px; margin: 25px 0; border-radius: 0 8px 8px 0;">
                    <p style="margin: 0; font-weight: bold; color: #2c3e50;">In the portal you can:</p>
                    <ul style="margin: 10px 0 0 0; padding-left: 20px; color: #555;">
                        <li>Manage your bookings and requests</li>
                        <li>Update important care details for your pets</li>
                        <li>Stay updated with the latest visit notes</li>
                        <li>Manage your profile and payment methods</li>
                    </ul>
                </div>
                
                <div style="text-align: center; margin: 35px 0;">
                    <a href="{portal_url}" style="background-color: #27ae60; color: #ffffff; padding: 14px 30px; text-decoration: none; border-radius: 8px; font-weight: bold; display: inline-block;">Access Client Portal</a>
                </div>
                
                {password_html}
                
                <p style="margin-top: 30px;">We look forward to providing premium care for your best friends!</p>
                
                <hr style="border: 0; border-top: 1px solid #eee; margin: 30px 0;" />
                
                <div style="text-align: center; color: #7f8c8d; font-size: 12px;">
                    <p style="margin: 5px 0;">&copy; 2026 Tog & Dogs Pet Sitting</p>
                    <p style="margin: 5px 0;">Premium Pet Care & Management</p>
                </div>
            </div>
        </body>
        </html>
        """
        return subject, body_text, body_html