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
        subject = "Your Tog and Dogs Service Request: Approved!"
        body_text = f"Hi {ctx['client_name']},\n\nGreat news! Your service request for {ctx['pet_names']} has been approved.\n\nWe've added this to our master schedule and will see you soon!\n\nQuestions? Reply to this email or contact Tog and Dogs directly."
        body_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: auto; border: 1px solid #eee; padding: 20px; border-radius: 10px;">
                <h2 style="color: #27ae60;">Great news, {ctx['client_name']}!</h2>
                <p>Your service request for <strong>{ctx['pet_names']}</strong> has been <strong>Approved</strong>.</p>
                <p>We've added this to our master schedule and will see you soon!</p>
                <div style="background: #e8f5e9; padding: 15px; border-radius: 5px; margin: 20px 0;">
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
