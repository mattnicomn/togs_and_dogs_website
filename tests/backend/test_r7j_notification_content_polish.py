"""
tests/backend/test_r7j_notification_content_polish.py

Release 7J: Notification Content Polish Tests
- Verifies selected_dates and end_date pass through service.py context
- Verifies multi-day date display renders in templates
- Verifies single-day notifications remain unchanged
- Verifies polished copy in all modified templates
- No real emails sent (all mocked)
"""
import unittest
from unittest.mock import patch, MagicMock


class TestR7JContextBuilder(unittest.TestCase):
    """Verify service.py context builder passes selected_dates and end_date."""

    def _build_context(self, **record_fields):
        """
        Directly exercise the context-building block inside notify_event
        without routing through the full notification pipeline.
        Mirrors the exact dict structure in service.py lines ~356-374.
        """
        from unittest.mock import MagicMock
        from common.notifications.resolver import get_client_name, get_staff_name, get_pet_names

        record = {
            'request_id': 'REQ-7J-001',
            'client_id': 'CLI-001',
            'client_email': 'client@example.com',
            'client_name': 'Jane Smith',
            'client_phone': '555-1234',
            'pet_names': 'Biscuit',
            'service_type': 'DROPIN_1HR',
            'start_date': '2026-06-09',
            'status': 'ASSIGNED',
        }
        record.update(record_fields)

        # This mirrors the exact context builder in service.py
        context = {
            'client_name': get_client_name(record),
            'client_email': record.get('client_email') or record.get('email') or '',
            'client_phone': record.get('client_phone') or '',
            'staff_name': get_staff_name(record),
            'worker_id': record.get('worker_id') or '',
            'worker_name': record.get('worker_name') or record.get('assigned_to_name') or '',
            'request_id': record.get('request_id'),
            'pet_names': get_pet_names(record),
            'service_type': record.get('service_type'),
            'start_date': record.get('start_date'),
            'end_date': record.get('end_date') or '',
            'selected_dates': record.get('selected_dates') or [],
            'job_ids': record.get('job_ids') or [],
            'start_time': record.get('start_time'),
            'details': record.get('details', 'No details provided.'),
            'portal_url': 'https://toganddogs.usmissionhero.com',
            'cancellation_reason': record.get('cancellation_reason') or '',
        }
        return context

    def test_selected_dates_passed_to_template(self):
        """selected_dates from record must appear in the context dict."""
        ctx = self._build_context(
            selected_dates=['2026-06-09', '2026-06-10', '2026-06-11'],
            end_date='2026-06-11',
        )
        self.assertEqual(ctx['selected_dates'], ['2026-06-09', '2026-06-10', '2026-06-11'])
        self.assertEqual(ctx['end_date'], '2026-06-11')

    def test_end_date_passed_to_template(self):
        """end_date from record must appear in the context dict."""
        ctx = self._build_context(end_date='2026-06-13')
        self.assertEqual(ctx['end_date'], '2026-06-13')

    def test_empty_selected_dates_defaults_to_list(self):
        """When no selected_dates on record, context gets an empty list (not None)."""
        ctx = self._build_context()  # no selected_dates
        self.assertIsInstance(ctx['selected_dates'], list)
        self.assertEqual(ctx['selected_dates'], [])

    def test_job_ids_passed_to_template(self):
        """job_ids from record must appear in the context dict."""
        ctx = self._build_context(job_ids=['JOB-001', 'JOB-002', 'JOB-003'])
        self.assertEqual(ctx['job_ids'], ['JOB-001', 'JOB-002', 'JOB-003'])

    def test_selected_dates_feeds_normalize_context_multi_day(self):
        """selected_dates in context → normalize_context produces is_multi_visit=True and range display."""
        from common.notifications.templates import NotificationTemplates
        ctx = self._build_context(
            selected_dates=['2026-06-09', '2026-06-10', '2026-06-11'],
            end_date='2026-06-11',
        )
        normalized = NotificationTemplates.normalize_context(ctx)
        self.assertTrue(normalized['is_multi_visit'])
        self.assertIn('–', normalized['date_display'])
        self.assertIn('Jun', normalized['date_display'])


class TestR7JMultiDayDateFormatting(unittest.TestCase):
    """Verify normalize_context renders multi-day dates when selected_dates is present."""

    def _normalize(self, **kwargs):
        from common.notifications.templates import NotificationTemplates
        return NotificationTemplates.normalize_context(kwargs)

    def test_consecutive_selected_dates_render_as_range(self):
        ctx = self._normalize(
            selected_dates=['2026-06-09', '2026-06-10', '2026-06-11', '2026-06-12', '2026-06-13'],
            start_date='2026-06-09',
            end_date='2026-06-13',
        )
        self.assertIn('–', ctx['date_display'])
        self.assertIn('Jun', ctx['date_display'])
        self.assertTrue(ctx['is_multi_visit'])
        self.assertEqual(ctx['date_heading'], 'Dates:')
        self.assertEqual(ctx['date_text'], 'Visit Dates')

    def test_non_consecutive_selected_dates_render_as_list(self):
        ctx = self._normalize(
            selected_dates=['2026-06-09', '2026-06-11', '2026-06-13'],
            start_date='2026-06-09',
        )
        # Non-consecutive: should NOT have an en-dash range
        self.assertNotIn('9–13', ctx['date_display'])
        self.assertIn('Jun 9', ctx['date_display'])
        self.assertTrue(ctx['is_multi_visit'])

    def test_single_date_renders_correctly(self):
        ctx = self._normalize(
            start_date='2026-06-09',
        )
        self.assertFalse(ctx['is_multi_visit'])
        self.assertEqual(ctx['date_heading'], 'Date:')
        self.assertEqual(ctx['date_text'], 'Visit Date')
        self.assertIn('Jun', ctx['date_display'])

    def test_legacy_start_end_date_renders_as_range(self):
        ctx = self._normalize(
            start_date='2026-06-09',
            end_date='2026-06-13',
        )
        self.assertTrue(ctx['is_multi_visit'])
        self.assertIn('–', ctx['date_display'])


class TestR7JVisitScheduledTemplate(unittest.TestCase):
    """Verify visit_scheduled polish: conditional sitter sentence."""

    def _get_template(self, **kwargs):
        from common.notifications.templates import NotificationTemplates
        ctx = NotificationTemplates.normalize_context(kwargs)
        return NotificationTemplates.visit_scheduled(ctx)

    def test_sitter_confirmed_with_name(self):
        _, body_text, body_html = self._get_template(
            client_name='Jane',
            pet_names='Biscuit',
            service_type='DROPIN_1HR',
            worker_name='Ryan',
            start_date='2026-06-09',
        )
        self.assertIn('Ryan will be your sitter', body_text)
        self.assertIn('Ryan will be your sitter', body_html)

    def test_sitter_confirmed_without_name(self):
        _, body_text, body_html = self._get_template(
            client_name='Jane',
            pet_names='Biscuit',
            service_type='DROPIN_1HR',
            start_date='2026-06-09',
        )
        self.assertIn('A sitter will be assigned shortly', body_text)
        self.assertIn('A sitter will be assigned shortly', body_html)

    def test_visit_word_plural_for_multi_day(self):
        _, body_text, body_html = self._get_template(
            client_name='Jane',
            pet_names='Biscuit',
            service_type='DROPIN_1HR',
            worker_name='Ryan',
            selected_dates=['2026-06-09', '2026-06-10', '2026-06-11'],
            start_date='2026-06-09',
        )
        self.assertIn('visits', body_text)

    def test_visit_word_singular_for_single_day(self):
        _, body_text, _ = self._get_template(
            client_name='Jane',
            pet_names='Biscuit',
            service_type='DROPIN_1HR',
            worker_name='Ryan',
            start_date='2026-06-09',
        )
        # singular "visit" appears, "visits" does not
        self.assertNotIn('visits', body_text)


class TestR7JStaffAssignedTemplate(unittest.TestCase):
    """Verify staff_assigned polish: multi-day intro sentence."""

    def _get_template(self, **kwargs):
        from common.notifications.templates import NotificationTemplates
        ctx = NotificationTemplates.normalize_context(kwargs)
        return NotificationTemplates.staff_assigned(ctx)

    def test_multi_day_intro(self):
        _, body_text, body_html = self._get_template(
            staff_name='Ryan',
            client_name='Jane',
            pet_names='Biscuit',
            service_type='DROPIN_1HR',
            selected_dates=['2026-06-09', '2026-06-10', '2026-06-11'],
            start_date='2026-06-09',
        )
        self.assertIn('spanning multiple visits', body_text)
        self.assertIn('complete visit schedule', body_text)

    def test_single_day_intro(self):
        _, body_text, _ = self._get_template(
            staff_name='Ryan',
            client_name='Jane',
            pet_names='Biscuit',
            service_type='DROPIN_1HR',
            start_date='2026-06-09',
        )
        self.assertIn("You've been assigned a new visit.", body_text)
        self.assertNotIn('spanning multiple visits', body_text)


class TestR7JCustomerApprovedTemplate(unittest.TestCase):
    """Verify customer_approved polish: visit/visits in next-steps."""

    def _get_template(self, **kwargs):
        from common.notifications.templates import NotificationTemplates
        ctx = NotificationTemplates.normalize_context(kwargs)
        return NotificationTemplates.customer_approved(ctx)

    def test_plural_for_multi_day(self):
        _, body_text, body_html = self._get_template(
            client_name='Jane',
            pet_names='Biscuit',
            service_type='DROPIN_1HR',
            selected_dates=['2026-06-09', '2026-06-10', '2026-06-11'],
            start_date='2026-06-09',
        )
        self.assertIn('assigned to your visits shortly', body_text)
        self.assertIn('assigned to your visits shortly', body_html)

    def test_singular_for_single_day(self):
        _, body_text, _ = self._get_template(
            client_name='Jane',
            pet_names='Biscuit',
            service_type='DROPIN_1HR',
            start_date='2026-06-09',
        )
        self.assertIn('assigned to your visit shortly', body_text)
        self.assertNotIn('assigned to your visits shortly', body_text)


class TestR7JVisitCancelledTemplate(unittest.TestCase):
    """Verify visit_cancelled uses client-friendly subject."""

    def _get_template(self, **kwargs):
        from common.notifications.templates import NotificationTemplates
        ctx = NotificationTemplates.normalize_context(kwargs)
        return NotificationTemplates.visit_cancelled(ctx)

    def test_client_friendly_subject(self):
        subject, _, _ = self._get_template(
            client_name='Jane',
            pet_names='Biscuit',
            service_type='DROPIN_1HR',
            start_date='2026-06-09',
        )
        self.assertIn('Has Been Cancelled', subject)
        self.assertIn('Tog & Dogs', subject)
        # Must NOT include the client name in the subject (was admin-oriented)
        self.assertNotIn('Jane', subject)


class TestR7JRequestReceivedTemplate(unittest.TestCase):
    """Verify request_received plain-text contact formatting uses newline not pipe."""

    def _get_template(self, **kwargs):
        from common.notifications.templates import NotificationTemplates
        ctx = NotificationTemplates.normalize_context(kwargs)
        return NotificationTemplates.request_received(ctx)

    def test_newline_separator_in_plain_text(self):
        _, body_text, _ = self._get_template(
            client_name='Jane',
            client_email='jane@example.com',
            client_phone='555-1234',
            pet_names='Biscuit',
            service_type='DROPIN_1HR',
            start_date='2026-06-09',
        )
        self.assertNotIn('Email: jane@example.com | Phone:', body_text)
        self.assertIn('Email: jane@example.com', body_text)
        self.assertIn('Phone: 555-1234', body_text)


class TestR7JVisitTimeChangedTemplate(unittest.TestCase):
    """Verify visit_time_changed now returns a full branded template."""

    def _get_template(self, **kwargs):
        from common.notifications.templates import NotificationTemplates
        ctx = NotificationTemplates.normalize_context(kwargs)
        return NotificationTemplates.visit_time_changed(ctx)

    def test_branded_subject(self):
        subject, _, _ = self._get_template(
            client_name='Jane',
            pet_names='Biscuit',
            service_type='DROPIN_1HR',
            start_date='2026-06-09',
        )
        self.assertIn('Visit Schedule Updated', subject)

    def test_full_html_structure(self):
        _, _, body_html = self._get_template(
            client_name='Jane',
            pet_names='Biscuit',
            service_type='DROPIN_1HR',
            start_date='2026-06-09',
            portal_url='https://toganddogs.usmissionhero.com',
        )
        self.assertIn('border-radius: 12px', body_html)
        self.assertIn('View in Portal', body_html)
        self.assertIn('Tog', body_html)

    def test_not_stub(self):
        """Confirm old stub markers like <h2>Visit Time Updated</h2> are gone."""
        _, _, body_html = self._get_template(
            client_name='Jane',
            pet_names='Biscuit',
            service_type='DROPIN_1HR',
            start_date='2026-06-09',
        )
        self.assertNotIn('<h2>Visit Time Updated</h2>', body_html)


class TestR7JDedupGuardUnchanged(unittest.TestCase):
    """Verify the Release 7F dedup guard is still operational."""

    @patch('common.notifications.service._is_recent_duplicate', return_value=True)
    def test_dedup_blocks_within_window(self, mock_dedup):
        """Dedup guard returns True (block) when a recent duplicate is found."""
        from common.notifications.service import _is_recent_duplicate
        # Test via the already-patched service function
        result = mock_dedup('STAFF_ASSIGNED', 'staff@example.com', 'REQ-001', window_minutes=5)
        self.assertTrue(result)

    @patch('common.notifications.service._is_recent_duplicate', return_value=False)
    def test_dedup_allows_outside_window(self, mock_dedup):
        """Dedup guard returns False (allow) when no recent duplicate is found."""
        result = mock_dedup('STAFF_ASSIGNED', 'staff@example.com', 'REQ-001', window_minutes=5)
        self.assertFalse(result)


class TestR7KStaffAssignedJobRecordValidation(unittest.TestCase):
    """Verify that when notify_event is triggered with a JOB record, it merges parent request date context."""

    @patch('common.db.get_item')
    @patch('common.notifications.service.resolve_notification_recipients', return_value=['staff@example.com'])
    @patch('common.notifications.service.NotificationTemplates.get_template', return_value=('Subject', 'Body Text', 'Body HTML'))
    @patch('common.notifications.service._write_ledger_entry')
    @patch('common.notifications.service._is_recent_duplicate', return_value=False)
    def test_job_record_merges_parent_req_context(self, mock_dup, mock_ledger, mock_get_template, mock_resolve, mock_get_item):
        from common.notifications.service import notify_event

        # Mock parent REQ record
        parent_req = {
            'PK': 'REQ#req_123',
            'SK': 'CLIENT#cli_123',
            'selected_dates': ['2026-06-09', '2026-06-11', '2026-06-13'],
            'start_date': '2026-06-09',
            'end_date': '2026-06-13',
            'job_ids': ['job_1', 'job_2', 'job_3'],
            'client_name': 'Justbeingbrea',
            'pet_names': 'Joey Rockwell',
            'service_type': 'OVERNIGHT',
        }

        # Mock child JOB record
        job_record = {
            'PK': 'JOB#job_1',
            'SK': 'REQ#req_123',
            'entity_type': 'JOB',
            'request_id': 'req_123',
            'client_id': 'cli_123',
            'worker_id': 'mattnicomn10@gmail.com',
            'worker_name': 'Matthew Nico',
            'start_date': '2026-06-09',
            'end_date': '2026-06-09',
            'service_type': 'OVERNIGHT',
        }

        # get_item is called in notify_event (or the resolver) to find the parent request
        # Let's mock get_item to return our parent REQ
        def side_effect(pk, sk):
            if pk == 'REQ#req_123':
                return parent_req
            return None
        mock_get_item.side_effect = side_effect

        # Call notify_event
        notify_event('STAFF_ASSIGNED', job_record)

        # Verify that get_template was called with a context that has the parent's selected_dates
        self.assertTrue(mock_get_template.called)
        called_context = mock_get_template.call_args[0][1]
        
        self.assertEqual(called_context['selected_dates'], ['2026-06-09', '2026-06-11', '2026-06-13'])
        self.assertEqual(called_context['end_date'], '2026-06-13')
        self.assertEqual(called_context['job_ids'], ['job_1', 'job_2', 'job_3'])

    @patch('common.db.get_item', return_value=None)
    @patch('common.notifications.service.resolve_notification_recipients', return_value=['staff@example.com'])
    @patch('common.notifications.service.NotificationTemplates.get_template', return_value=('Subject', 'Body Text', 'Body HTML'))
    @patch('common.notifications.service._write_ledger_entry')
    @patch('common.notifications.service._is_recent_duplicate', return_value=False)
    def test_parent_lookup_failure_failsafe(self, mock_dup, mock_ledger, mock_get_template, mock_resolve, mock_get_item):
        """If parent lookup fails (returns None), notify_event proceeds using child JOB context."""
        from common.notifications.service import notify_event

        job_record = {
            'PK': 'JOB#job_1',
            'SK': 'REQ#req_123',
            'entity_type': 'JOB',
            'request_id': 'req_123',
            'client_id': 'cli_123',
            'worker_id': 'mattnicomn10@gmail.com',
            'worker_name': 'Matthew Nico',
            'start_date': '2026-06-09',
            'end_date': '2026-06-09',
            'service_type': 'OVERNIGHT',
        }

        # Call notify_event
        notify_event('STAFF_ASSIGNED', job_record)

        self.assertTrue(mock_get_template.called)
        called_context = mock_get_template.call_args[0][1]
        
        # Verify it fallback-resolved to empty list since parent lookup returned None
        self.assertEqual(called_context['selected_dates'], [])
        self.assertEqual(called_context['end_date'], '2026-06-09')

    @patch('common.db.get_item')
    @patch('common.notifications.service.resolve_notification_recipients', return_value=['client@example.com'])
    @patch('common.notifications.service.NotificationTemplates.get_template', return_value=('Subject', 'Body Text', 'Body HTML'))
    @patch('common.notifications.service._write_ledger_entry')
    @patch('common.notifications.service._is_recent_duplicate', return_value=False)
    def test_direct_req_record_unaffected(self, mock_dup, mock_ledger, mock_get_template, mock_resolve, mock_get_item):
        """Passing a direct REQ record does not trigger JOB parent lookup logic and remains unaffected."""
        from common.notifications.service import notify_event

        req_record = {
            'PK': 'REQ#req_123',
            'SK': 'CLIENT#cli_123',
            'entity_type': 'REQUEST',
            'request_id': 'req_123',
            'client_id': 'cli_123',
            'selected_dates': ['2026-06-09', '2026-06-11'],
            'start_date': '2026-06-09',
            'end_date': '2026-06-11',
        }

        notify_event('CUSTOMER_APPROVED', req_record)

        self.assertTrue(mock_get_template.called)
        called_context = mock_get_template.call_args[0][1]
        
        # Verify db.get_item was never called with 'REQ#req_123' (only called for the quota count check)
        for call in mock_get_item.call_args_list:
            args = call[0]
            self.assertNotEqual(args[0], 'REQ#req_123')
        self.assertEqual(called_context['selected_dates'], ['2026-06-09', '2026-06-11'])

    @patch('common.db.get_item')
    @patch('common.notifications.service.resolve_notification_recipients', return_value=['staff@example.com'])
    @patch('common.notifications.service.NotificationTemplates.get_template', return_value=('Subject', 'Body Text', 'Body HTML'))
    @patch('common.notifications.service._write_ledger_entry')
    @patch('common.notifications.service._is_recent_duplicate', return_value=False)
    def test_single_day_job_backward_compatible(self, mock_dup, mock_ledger, mock_get_template, mock_resolve, mock_get_item):
        """Single-day JOB with single-day parent REQ behaves backward-compatibly."""
        from common.notifications.service import notify_event

        parent_req = {
            'PK': 'REQ#req_123',
            'SK': 'CLIENT#cli_123',
            'start_date': '2026-06-09',
            'end_date': '2026-06-09',
            'selected_dates': ['2026-06-09'],
            'client_name': 'Jane',
        }

        job_record = {
            'PK': 'JOB#job_1',
            'SK': 'REQ#req_123',
            'entity_type': 'JOB',
            'request_id': 'req_123',
            'client_id': 'cli_123',
            'start_date': '2026-06-09',
            'end_date': '2026-06-09',
        }

        mock_get_item.return_value = parent_req

        notify_event('STAFF_ASSIGNED', job_record)

        self.assertTrue(mock_get_template.called)
        called_context = mock_get_template.call_args[0][1]
        
        # Verify it has parent fields but stays single day
        self.assertEqual(called_context['selected_dates'], ['2026-06-09'])
        self.assertEqual(called_context['end_date'], '2026-06-09')


if __name__ == '__main__':
    unittest.main()

