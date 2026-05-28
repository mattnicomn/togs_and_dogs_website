import pytest
from common.notifications.templates import NotificationTemplates

def test_single_day_behavior_unchanged():
    context = {
        'start_date': '2026-05-28'
    }
    norm = NotificationTemplates.normalize_context(context)
    assert norm['is_multi_visit'] is False
    assert norm['date_heading'] == 'Date:'
    assert norm['date_text'] == 'Visit Date'
    assert norm['date_display'] == 'May 28, 2026'

def test_multi_day_selected_dates_consecutive():
    context = {
        'start_date': '2026-05-28',
        'selected_dates': ['2026-05-28T00:00:00.000Z', '2026-05-29T00:00:00.000Z', '2026-05-30T00:00:00.000Z']
    }
    norm = NotificationTemplates.normalize_context(context)
    assert norm['is_multi_visit'] is True
    assert norm['date_heading'] == 'Dates:'
    assert norm['date_text'] == 'Visit Dates'
    assert norm['date_display'] == 'May 28–May 30, 2026'

def test_multi_day_selected_dates_non_consecutive():
    context = {
        'start_date': '2026-05-28',
        'selected_dates': ['2026-05-28T00:00:00.000Z', '2026-05-30T00:00:00.000Z', '2026-06-02T00:00:00.000Z']
    }
    norm = NotificationTemplates.normalize_context(context)
    assert norm['is_multi_visit'] is True
    assert norm['date_heading'] == 'Dates:'
    assert norm['date_text'] == 'Visit Dates'
    assert norm['date_display'] == 'May 28, May 30, Jun 2, 2026'

def test_multi_day_date_range_summary():
    context = {
        'start_date': '2026-05-28',
        'end_date': '2026-05-30'
    }
    norm = NotificationTemplates.normalize_context(context)
    assert norm['is_multi_visit'] is True
    assert norm['date_heading'] == 'Dates:'
    assert norm['date_text'] == 'Visit Dates'
    assert norm['date_display'] == 'May 28–May 30, 2026'

def test_missing_partial_date_context():
    context = {}
    norm = NotificationTemplates.normalize_context(context)
    assert norm['is_multi_visit'] is False
    assert norm['date_display'] == 'scheduled date'
    assert norm['date_heading'] == 'Date:'
    
    context2 = {'start_date': 'Invalid-Date'}
    norm2 = NotificationTemplates.normalize_context(context2)
    assert norm2['date_display'] == 'Invalid-Date'

def test_customer_approved_template_injection():
    context = {
        'client_name': 'Alice',
        'start_date': '2026-05-28',
        'end_date': '2026-05-30'
    }
    subj, text, html = NotificationTemplates.get_template('CUSTOMER_APPROVED', context)
    assert 'Visit Dates: May 28–May 30, 2026' in text
    assert 'Dates:</td>' in html
    assert 'May 28–May 30, 2026' in html
