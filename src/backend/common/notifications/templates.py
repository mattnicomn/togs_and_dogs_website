from .config import NotificationConfig

class NotificationTemplates:
    """Templates for different notification events."""

    @staticmethod
    def get_template(event_type, context):
        """
        Returns (subject, body_text, body_html) for a given event and context.
        """
        templates = {
            'REQUEST_RECEIVED': NotificationTemplates._request_received,
            'CUSTOMER_APPROVED': NotificationTemplates._customer_approved,
            'VISIT_SCHEDULED': NotificationTemplates._visit_scheduled,
            'STAFF_ASSIGNED': NotificationTemplates._staff_assigned,
            'VISIT_CANCELLED': NotificationTemplates._visit_cancelled,
            'VISIT_TIME_CHANGED': NotificationTemplates._visit_time_changed
        }
        
        template_func = templates.get(event_type)
        if not template_func:
            return None, None, None
            
        return template_func(context)

    @staticmethod
    def _request_received(ctx):
        client_name = ctx.get('client_name', 'Valued Client')
        subject = f"New Service Request Received - {client_name}"
        text = f"Hello Ryan,\n\nA new service request has been received from {client_name}.\n\nDetails: {ctx.get('details', 'N/A')}"
        html = f"<html><body><h2>New Service Request</h2><p>A new request has been received from <strong>{client_name}</strong>.</p></body></html>"
        return subject, text, html

    @staticmethod
    def _customer_approved(ctx):
        client_name = ctx.get('client_name', 'Valued Client')
        subject = "Your Service Request has been Approved!"
        text = f"Hi {client_name},\n\nGreat news! Your service request has been approved."
        html = f"<html><body><h2>Great news, {client_name}!</h2><p>Your request has been <strong>APPROVED</strong>.</p></body></html>"
        return subject, text, html

    @staticmethod
    def _visit_scheduled(ctx):
        client_name = ctx.get('client_name', 'Valued Client')
        subject = "Your Visit has been Scheduled"
        text = f"Hi {client_name},\n\nYour visit has been successfully scheduled."
        html = f"<html><body><h2>Visit Scheduled</h2><p>Hi {client_name}, your visit is now on our schedule!</p></body></html>"
        return subject, text, html

    @staticmethod
    def _staff_assigned(ctx):
        staff_name = ctx.get('staff_name', 'Team Member')
        subject = "New Assignment: Upcoming Visit"
        text = f"Hi {staff_name},\n\nYou have been assigned a new visit."
        html = f"<html><body><h2>New Assignment</h2><p>Hi {staff_name}, you have a new assignment.</p></body></html>"
        return subject, text, html

    @staticmethod
    def _visit_cancelled(ctx):
        client_name = ctx.get('client_name', 'Valued Client')
        subject = "Visit Cancellation Confirmation"
        text = f"Hi {client_name},\n\nThis is to confirm that your visit has been cancelled."
        html = f"<html><body><h2>Visit Cancelled</h2><p>Hi {client_name}, your visit has been cancelled as requested.</p></body></html>"
        return subject, text, html

    @staticmethod
    def _visit_time_changed(ctx):
        client_name = ctx.get('client_name', 'Valued Client')
        subject = "Update: Your Visit Time has Changed"
        text = f"Hi {client_name},\n\nWe wanted to let you know that your visit time has been adjusted."
        html = f"<html><body><h2>Schedule Update</h2><p>Hi {client_name}, your visit time has been updated.</p></body></html>"
        return subject, text, html
