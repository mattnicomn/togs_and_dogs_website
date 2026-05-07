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
        elif event_type == 'WELCOME_INVITE':
            return NotificationTemplates.welcome_invite(friendly_context)
        
        return None, None, None

    @staticmethod
    def normalize_context(context):
        """Safely renders friendly labels for raw data."""
        normalized = dict(context)
        
        # 1. Fallbacks for names
        normalized['client_name'] = context.get('client_name') or 'Valued Client'
        normalized['staff_name'] = context.get('staff_name') or 'Team Member'
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
        # Assuming context might have start_date, start_time
        date_val = context.get('start_date', 'scheduled date')
        time_val = context.get('start_time')
        normalized['date_label'] = f"{date_val} at {time_val}" if time_val else date_val
        
        return normalized

    @staticmethod
    def request_received(ctx):
        subject = f"New Service Request Received - {ctx['client_name']}"
        body_text = f"Hi Ryan,\n\nA new service request has been received from {ctx['client_name']} for {ctx['pet_names']}.\n\nService: {ctx['service_label']}\nDate: {ctx['date_label']}\n\nDetails: {ctx['details']}"
        body_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: auto; border: 1px solid #eee; padding: 20px; border-radius: 10px;">
                <h2 style="color: #2c3e50;">New Service Request</h2>
                <p>Hi Ryan,</p>
                <p>A new service request has been received from <strong>{ctx['client_name']}</strong> for <strong>{ctx['pet_names']}</strong>.</p>
                <div style="background: #f9f9f9; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <p style="margin: 5px 0;"><strong>Service:</strong> {ctx['service_label']}</p>
                    <p style="margin: 5px 0;"><strong>Date:</strong> {ctx['date_label']}</p>
                </div>
                <p><strong>Details:</strong><br/>{ctx['details']}</p>
                <p style="margin-top: 30px; font-size: 0.9em; color: #777;">Tog and Dogs Internal Notification</p>
            </div>
        </body>
        </html>
        """
        return subject, body_text, body_html

    @staticmethod
    def customer_approved(ctx):
        subject = "Your Tog & Dogs request was approved"
        
        # Friendly date/time or fallback
        date_time = ctx.get('date_label') or "not yet scheduled"
        
        body_text = (
            f"Hi {ctx['client_name']},\n\n"
            f"Good news — your Tog & Dogs request for {ctx['pet_names']} has been approved.\n\n"
            f"Requested date/time:\n{date_time}\n\n"
            f"Ryan will follow up if any final scheduling details are needed.\n\n"
            f"Thank you,\n"
            f"Tog & Dogs"
        )
        
        body_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: auto; border: 1px solid #eee; padding: 20px; border-radius: 10px;">
                <h2 style="color: #27ae60;">Good news, {ctx['client_name']}!</h2>
                <p>Your Tog & Dogs request for <strong>{ctx['pet_names']}</strong> has been <strong>approved</strong>.</p>
                
                <div style="background: #e8f5e9; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <p style="margin: 5px 0;"><strong>Requested date/time:</strong><br/>{date_time}</p>
                </div>
                
                <p>Ryan will follow up if any final scheduling details are needed.</p>
                
                <p style="margin-top: 30px;">Thank you,<br/>Tog & Dogs</p>
            </div>
        </body>
        </html>
        """
        return subject, body_text, body_html

    @staticmethod
    def visit_scheduled(ctx):
        subject = "Your Visit has been Scheduled"
        body_text = f"Hi {ctx['client_name']},\n\nYour upcoming visit for {ctx['pet_names']} has been scheduled with {ctx['staff_name']}.\n\nDate: {ctx['date_label']}\n\nQuestions? Reply to this email or contact Tog and Dogs directly."
        body_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: auto; border: 1px solid #eee; padding: 20px; border-radius: 10px;">
                <h2 style="color: #2980b9;">Visit Scheduled!</h2>
                <p>Hi {ctx['client_name']},</p>
                <p>Your upcoming visit for <strong>{ctx['pet_names']}</strong> has been scheduled with <strong>{ctx['staff_name']}</strong>.</p>
                <div style="background: #ebf5fb; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <p style="margin: 5px 0;"><strong>Service:</strong> {ctx['service_label']}</p>
                    <p style="margin: 5px 0;"><strong>Date:</strong> {ctx['date_label']}</p>
                </div>
                <p>Questions? Reply to this email or contact us directly.</p>
                <hr style="border: 0; border-top: 1px solid #eee; margin: 30px 0;" />
                <p style="font-size: 0.9em; color: #777;">Best,<br/>The Tog and Dogs Team</p>
            </div>
        </body>
        </html>
        """
        return subject, body_text, body_html

    @staticmethod
    def staff_assigned(ctx):
        subject = "New Assignment: Upcoming Visit"
        body_text = f"Hi {ctx['staff_name']},\n\nYou have been assigned a new visit for {ctx['client_name']}.\n\nPets: {ctx['pet_names']}\nDate: {ctx['date_label']}\n\nPlease review the details in the staff portal."
        body_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: auto; border: 1px solid #eee; padding: 20px; border-radius: 10px;">
                <h2 style="color: #8e44ad;">New Assignment</h2>
                <p>Hi {ctx['staff_name']},</p>
                <p>You have been assigned a new visit for <strong>{ctx['client_name']}</strong>.</p>
                <div style="background: #f5eef8; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <p style="margin: 5px 0;"><strong>Service:</strong> {ctx['service_label']}</p>
                    <p style="margin: 5px 0;"><strong>Pets:</strong> {ctx['pet_names']}</p>
                    <p style="margin: 5px 0;"><strong>Date:</strong> {ctx['date_label']}</p>
                </div>
                <p>Please review the details in the staff portal for any specific instructions.</p>
                <p style="margin-top: 30px; font-size: 0.9em; color: #777;">Tog and Dogs Team Management</p>
            </div>
        </body>
        </html>
        """
        return subject, body_text, body_html

    @staticmethod
    def visit_cancelled(ctx):
        subject = "Visit Cancellation Confirmation"
        body_text = f"Hi {ctx['client_name']},\n\nThis is to confirm that your visit for {ctx['pet_names']} on {ctx['date_label']} has been cancelled.\n\nQuestions? Reply to this email or contact Tog and Dogs directly."
        body_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: auto; border: 1px solid #eee; padding: 20px; border-radius: 10px;">
                <h2 style="color: #c0392b;">Visit Cancelled</h2>
                <p>Hi {ctx['client_name']},</p>
                <p>This is to confirm that your visit for <strong>{ctx['pet_names']}</strong> on <strong>{ctx['date_label']}</strong> has been <strong>Cancelled</strong>.</p>
                <div style="background: #fdf2f2; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <p style="margin: 5px 0;"><strong>Service:</strong> {ctx['service_label']}</p>
                </div>
                <p>If this was a mistake or you have questions, please reply to this email or contact us directly.</p>
                <hr style="border: 0; border-top: 1px solid #eee; margin: 30px 0;" />
                <p style="font-size: 0.9em; color: #777;">Best,<br/>The Tog and Dogs Team</p>
            </div>
        </body>
        </html>
        """
        return subject, body_text, body_html

    @staticmethod
    def visit_time_changed(ctx):
        subject = "Update: Visit Time Changed"
        body_text = f"Hi {ctx['client_name']},\n\nThere has been a change to the scheduled time for your upcoming visit.\n\nNew Time: {ctx['date_label']}\n\nQuestions? Reply to this email or contact Tog and Dogs directly."
        body_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: auto; border: 1px solid #eee; padding: 20px; border-radius: 10px;">
                <h2 style="color: #f39c12;">Time Change Notification</h2>
                <p>Hi {ctx['client_name']},</p>
                <p>There has been a change to the scheduled time for your upcoming visit for <strong>{ctx['pet_names']}</strong>.</p>
                <div style="background: #fff9eb; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <p style="margin: 5px 0;"><strong>New Time:</strong> {ctx['date_label']}</p>
                </div>
                <p>Questions? Reply to this email or contact us directly.</p>
                <hr style="border: 0; border-top: 1px solid #eee; margin: 30px 0;" />
                <p style="font-size: 0.9em; color: #777;">Best,<br/>The Tog and Dogs Team</p>
            </div>
        </body>
        </html>
        """
        return subject, body_text, body_html

    @staticmethod
    def welcome_invite(ctx):
        subject = "Welcome to Tog & Dogs!"
        portal_url = ctx.get('portal_url', 'https://toganddogs.usmissionhero.com')
        user_name = ctx.get('client_name') or ctx.get('staff_name') or 'Valued Member'
        
        body_text = (
            f"Hi {user_name},\n\n"
            f"Welcome to Tog & Dogs! We've set up your access to our portal where you can manage "
            f"your account and stay connected with our team.\n\n"
            f"Access your portal here: {portal_url}\n\n"
            f"If this is your first time logging in, please check your inbox for a separate email from "
            f"Tog & Dogs (via Cognito) containing your temporary password.\n\n"
            f"We look forward to working with you!\n\n"
            f"Best,\n"
            f"The Tog & Dogs Team"
        )
        
        body_html = f"""
        <html>
        <body style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #333; background-color: #f4f7f6; padding: 20px;">
            <div style="max-width: 600px; margin: auto; border: 1px solid #e0e0e0; background-color: #ffffff; padding: 40px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.05);">
                <div style="text-align: center; margin-bottom: 30px;">
                    <h1 style="color: #2c3e50; margin: 0; font-size: 28px;">Welcome to Tog & Dogs!</h1>
                    <div style="width: 50px; height: 4px; background: #27ae60; margin: 15px auto; border-radius: 2px;"></div>
                </div>
                
                <p>Hi <strong>{user_name}</strong>,</p>
                
                <p>We're thrilled to have you as part of the Tog & Dogs family! Your portal access is now ready for you to use.</p>
                
                <div style="background-color: #f9fdfa; border-left: 4px solid #27ae60; padding: 20px; margin: 25px 0; border-radius: 0 8px 8px 0;">
                    <p style="margin: 0; font-weight: bold; color: #2c3e50;">In the portal you can:</p>
                    <ul style="margin: 10px 0 0 0; padding-left: 20px; color: #555;">
                        <li>Manage your schedule and requests</li>
                        <li>Update important care details</li>
                        <li>Stay updated with the latest visit notes</li>
                        <li>Manage your profile and communication preferences</li>
                    </ul>
                </div>
                
                <div style="text-align: center; margin: 35px 0;">
                    <a href="{portal_url}" style="background-color: #27ae60; color: white; padding: 14px 30px; text-decoration: none; border-radius: 8px; font-weight: bold; display: inline-block; transition: background-color 0.3s;">Access the Portal</a>
                </div>
                
                <div style="background-color: #fff9eb; border: 1px solid #ffeeba; padding: 15px; border-radius: 8px; font-size: 14px; color: #856404;">
                    <p style="margin: 0;"><strong>Note for new users:</strong> Please check your inbox for a separate email containing your temporary password. You'll be prompted to set a permanent password upon your first login.</p>
                </div>
                
                <p style="margin-top: 30px;">We look forward to working with you!</p>
                
                <hr style="border: 0; border-top: 1px solid #eee; margin: 30px 0;" />
                
                <div style="text-align: center; color: #7f8c8d; font-size: 13px;">
                    <p style="margin: 5px 0;">&copy; 2026 Tog & Dogs Pet Sitting</p>
                    <p style="margin: 5px 0;">Providing premium care for your best friends.</p>
                </div>
            </div>
        </body>
        </html>
        """
        return subject, body_text, body_html
