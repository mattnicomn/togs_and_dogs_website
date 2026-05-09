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
    def normalize_context(context):
        """Safely renders friendly labels for raw data."""
        normalized = dict(context)
        
        # 1. Fallbacks for names
        normalized['client_name'] = context.get('client_name') or 'Valued Client'
        normalized['staff_name'] = context.get('staff_name') or 'Team Member'
        normalized['user_name'] = context.get('client_name') or context.get('staff_name') or 'Valued Member'
        normalized['pet_names'] = context.get('pet_names') or 'your pets'
        
        # 2. Service type mapping
        service_type = context.get('service_type', 'PET_SITTING')
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
        date_val = context.get('start_date', 'scheduled date')
        time_val = context.get('start_time')
        normalized['date_label'] = f"{date_val} at {time_val}" if time_val else date_val
        
        return normalized

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