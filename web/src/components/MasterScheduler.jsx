import React, { useState, useEffect } from 'react';
import { getKnownServiceTypeLabel } from '../utils/serviceLabels.js';
import '../Admin.css';

const MasterScheduler = ({ items, onAssign, onReview, onSelectPet, staffList = [] }) => {
  const [viewMode, setViewMode] = useState('DAY'); // DAY or WEEK
  const [isMobile, setIsMobile] = useState(window.innerWidth <= 480);

  useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth <= 480);
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);
  const [filters, setFilters] = useState({
    staff: 'ALL',
    status: 'ALL',
    service: 'ALL'
  });

  const staffPalette = {};
  if (staffList && staffList.length > 0) {
    staffList.forEach(s => {
      const color = s.assignment_color || `var(--staff-${(s.display_name || 'unknown').toLowerCase()})`;
      if (s.email) staffPalette[s.email] = color;
      if (s.display_name) staffPalette[s.display_name] = color;
    });
  } else {
    staffPalette['Ryan'] = 'var(--staff-ryan)';
    staffPalette['Wife'] = 'var(--staff-wife)';
    staffPalette['Nephew1'] = 'var(--staff-nephew1)';
    staffPalette['Nephew2'] = 'var(--staff-nephew2)';
  }
  staffPalette['Unassigned'] = 'var(--staff-unassigned)';


  const getWorkerColor = (workerId) => {
    return staffPalette[workerId] || staffPalette['Unassigned'];
  };

  // Helper to get start of week (Sunday)
  const getStartOfWeek = (date) => {
    const d = new Date(date);
    const day = d.getDay();
    const diff = d.getDate() - day;
    return new Date(d.setDate(diff)).toISOString().split('T')[0];
  };

  // Use local date for "today" to match user expectations in their timezone
  const today = new Date().toLocaleDateString('sv-SE'); // Swedish locale returns YYYY-MM-DD
  const startOfWeek = getStartOfWeek(new Date());

  // Advanced Filtering Logic
  const filteredJobs = items.filter(i => {
    const status = (i.status || "").toUpperCase();
    const terminalStatuses = ['ARCHIVED', 'DELETED', 'COMPLETED', 'CANCELLED', 'DECLINED'];
    
    // Quick Filters
    const staffMatch = filters.staff === 'ALL' || 
      (filters.staff === '__HAS_PREFERENCE__' ? !!i.preferred_sitter : i.worker_id === filters.staff);
    const statusMatch = filters.status === 'ALL' 
      ? !terminalStatuses.includes(status) // Exclude terminal from 'ALL Active'
      : status === filters.status;         // Exact match for specific status selection
    const serviceMatch = filters.service === 'ALL' || i.service_type === filters.service;
    
    // Search Filter
    const searchTerm = (filters.search || "").toLowerCase();
    const searchMatch = !searchTerm || 
                        (i.pet_name || "").toLowerCase().includes(searchTerm) || 
                        (i.client_name || "").toLowerCase().includes(searchTerm);

    if (!statusMatch || !staffMatch || !serviceMatch || !searchMatch) return false;
    
    // Date Filtering (Day/Week View)
    const visitDate = i.start_date;
    if (!visitDate) return false;

    let dateMatch = true;
    if (viewMode === 'DAY') {
      dateMatch = visitDate === today;
    } else if (viewMode === 'WEEK') {
      const visitStartOfWeek = getStartOfWeek(visitDate);
      dateMatch = visitStartOfWeek === startOfWeek;
    }

    return dateMatch;
  });

  // Sort filtered jobs chronologically (nearest upcoming first) for mobile view
  const sortedJobs = [...filteredJobs].sort((a, b) => {
    const dateA = a.start_date || '';
    const dateB = b.start_date || '';
    if (dateA !== dateB) return dateA.localeCompare(dateB);
    const timeA = a.start_time || a.window_start || '';
    const timeB = b.start_time || b.window_start || '';
    return timeA.localeCompare(timeB);
  });

  // Helper to resolve staff display name
  const resolveStaffName = (workerId) => {
    if (!workerId) return 'Unassigned';
    const resolved = staffList.find(s => (s.email || s.display_name) === workerId);
    return resolved ? resolved.display_name : workerId;
  };

  // Helper to format visit time for mobile display
  const formatVisitTime = (job) => {
    if (job.start_time) return job.start_time;
    if (job.window_start) return job.window_start;
    if (job.window_type) return job.window_type;
    return '';
  };

  const pendingIntake = items.filter(i => ['PENDING_REVIEW', 'MEET_GREET_REQUIRED', 'PROFILE_CREATED', 'READY_FOR_APPROVAL'].includes(i.status));
  const pendingChanges = items.filter(i => i.status === 'CANCELLATION_REQUESTED');

  return (
    <div className="master-scheduler">
      <div className="scheduler-header">
        <div className="header-left">
          <h2>Master Scheduler</h2>
          <div className="view-toggle">
            <button className={viewMode === 'DAY' ? 'active' : ''} onClick={() => setViewMode('DAY')}>Day View</button>
            <button className={viewMode === 'WEEK' ? 'active' : ''} onClick={() => setViewMode('WEEK')}>Week View</button>
          </div>
        </div>
      </div>

      <div className="filter-bar card">
        <div className="filter-group search">
          <label>Search</label>
          <input 
            type="text" 
            placeholder="Customer or pet..."
            value={filters.search || ''} 
            onChange={(e) => setFilters({...filters, search: e.target.value})}
            className="search-input"
          />
        </div>
        <div className="filter-group">
          <label>Staff</label>
          <select value={filters.staff} onChange={(e) => setFilters({...filters, staff: e.target.value})}>
            <option value="ALL">All Staff</option>
            {staffList.map(s => (
              <option key={s.email || s.display_name} value={s.email || s.display_name}>
                {s.display_name}
              </option>
            ))}
            <option value="">Unassigned</option>
            {/* Release 2: Filter by preferred sitter preference */}
            <option value="__HAS_PREFERENCE__">Has Sitter Preference</option>
          </select>
        </div>
        <div className="filter-group">
          <label>Status</label>
          <select value={filters.status} onChange={(e) => setFilters({...filters, status: e.target.value})}>
            <option value="ALL">All Active</option>
            <option value="ASSIGNED">Scheduled</option>
            <option value="IN_PROGRESS">In Progress</option>
            <option value="COMPLETED">Completed</option>
            <option value="CANCELLED">Canceled</option>
            <option value="RESCHEDULED">Rescheduled</option>
          </select>
        </div>
        <div className="filter-group">
          <label>Service</label>
          <select value={filters.service} onChange={(e) => setFilters({...filters, service: e.target.value})}>
            <option value="ALL">All Services</option>
            <option value="WALK_30MIN">30m Walk</option>
            <option value="DROPIN_1HR">1hr Drop-in</option>
            <option value="DROPIN_3HR">3hr Drop-in</option>
            <option value="OVERNIGHT">Overnight</option>
          </select>
        </div>
        <div className="filter-actions">
          <button 
            className="btn-micro" 
            onClick={() => setFilters({ staff: 'ALL', status: 'ALL', service: 'ALL', search: '' })}
          >
            Clear Filters
          </button>
        </div>
      </div>

      <div className="scheduler-grid">
        {isMobile ? (
          /* Mobile: vertically scrollable list */
          <div className="scheduler-mobile-list">
            <div className="scheduler-mobile-list-header">
              <h3>{viewMode === 'DAY' ? "Today's" : "This Week's"} Visits</h3>
              <span className="badge-light">{sortedJobs.length}</span>
            </div>
            {sortedJobs.length === 0 ? (
              <p className="scheduler-mobile-empty">No visits scheduled for the selected {viewMode === 'DAY' ? 'day' : 'week'}.</p>
            ) : (
              <div className="scheduler-mobile-visits">
                {sortedJobs.map(job => (
                  <div
                    key={job.PK}
                    className={`scheduler-mobile-visit-card ${!job.worker_id ? 'urgent' : ''}`}
                    style={{ borderLeftColor: getWorkerColor(job.worker_id) }}
                    onClick={() => onSelectPet(job)}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') onSelectPet(job); }}
                  >
                    <div className="scheduler-mobile-visit-date">{job.start_date}</div>
                    <div className="scheduler-mobile-visit-time">{formatVisitTime(job)}</div>
                    <div className="scheduler-mobile-visit-client">{job.client_name || 'Unknown Client'}</div>
                    <div className="scheduler-mobile-visit-pet">{job.pet_name || ''}</div>
                    <div className="scheduler-mobile-visit-staff" style={{ color: getWorkerColor(job.worker_id) }}>
                      {!job.worker_id ? '⚠️ Unassigned' : resolveStaffName(job.worker_id)}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        ) : (
          /* Desktop: timeline view */
          <div className="timeline-view card">
            <div className="card-header">
              <h3>{viewMode} Dispatcher Timeline</h3>
              <span className="badge-light">{filteredJobs.length} Visits</span>
            </div>
            <div className="timeline-container">
              {filteredJobs.length === 0 ? (
                <p className="empty-state">No matching visits found.</p>
              ) : (
                filteredJobs.map(job => (
                  <div 
                    key={job.PK} 
                    className={`scheduled-visit ${!job.worker_id ? 'urgent' : ''}`} 
                    style={{ borderLeftColor: getWorkerColor(job.worker_id) }}
                    onClick={() => onSelectPet(job)}
                    title="Click to view Care Card"
                  >
                    <div className="visit-main">
                      <span className="visit-pet">{job.pet_name || job.client_name}</span>
                      <span className="visit-type">
                        {job.window_type
                          ? job.window_type
                          : getKnownServiceTypeLabel(job.service_type) ?? job.service_type}
                      </span>
                    </div>
                    <div className="visit-meta">
                      <span className="visit-time">{job.start_date}</span>
                      <span className="visit-staff" style={{ color: getWorkerColor(job.worker_id) }}>
                        {(() => {
                          if (!job.worker_id) return '⚠️ UNASSIGNED';
                          const resolved = staffList.find(s => (s.email || s.display_name) === job.worker_id);
                          return `Assigned to ${resolved ? resolved.display_name : job.worker_id}`;
                        })()}
                      </span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        )}

        <div className="sidebar-queue">
          {pendingChanges.length > 0 && (
            <div className="queue-card card urgent-border">
              <div className="card-header">
                <h3 className="urgent-text">Change Requests</h3>
                <span className="badge-urgent">{pendingChanges.length}</span>
              </div>
              <div className="queue-list">
                {pendingChanges.map(req => (
                  <div key={req.PK} className="queue-item cancellation-item" onClick={() => onSelectPet(req)}>
                    <div className="queue-info">
                      <strong>{req.client_name} - {req.pet_name}</strong>
                      <span className="urgent-text">CANCELLATION REQUESTED</span>
                      <p className="reason-preview">"{req.cancellation_reason?.substring(0, 40)}..."</p>
                    </div>
                    <button onClick={(e) => { e.stopPropagation(); onReview(req); }} className="btn-small urgent-bg">Review</button>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="queue-card card">
            <div className="card-header">
              <h3>Intake Queue</h3>
              {pendingIntake.length > 0 && <span className="badge-light">{pendingIntake.length}</span>}
            </div>
            <div className="queue-list">
              {pendingIntake.map(req => (
                <div key={req.PK} className="queue-item" onClick={() => onSelectPet(req)}>
                  <div className="queue-info">
                    <strong>{req.client_name}</strong>
                    <span>{getKnownServiceTypeLabel(req.service_type) ?? req.service_type}</span>
                    <span className={`status-pill ${req.status}`}>{req.status.replace(/_/g, ' ')}</span>
                  </div>
                  <button onClick={(e) => { e.stopPropagation(); onReview(req); }} className="btn-small">Process</button>
                </div>
              ))}
              {pendingIntake.length === 0 && <p className="empty-state">Queue is empty</p>}
            </div>
          </div>
        </div>
      </div>

    </div>
  );
};

export default MasterScheduler;
