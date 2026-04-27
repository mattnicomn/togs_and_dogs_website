import React, { useState } from 'react';
import '../Admin.css';

const MasterScheduler = ({ items, onAssign, onReview, onSelectPet }) => {
  const [viewMode, setViewMode] = useState('DAY'); // DAY or WEEK
  const [filters, setFilters] = useState({
    staff: 'ALL',
    status: 'ALL',
    service: 'ALL'
  });

  const staffPalette = {
    'Ryan': 'var(--staff-ryan)',
    'Wife': 'var(--staff-wife)',
    'Nephew1': 'var(--staff-nephew1)',
    'Nephew2': 'var(--staff-nephew2)',
    'Unassigned': 'var(--staff-unassigned)'
  };

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
    
    // Determine if it's an "active" visit that should be on the scheduler
    // Must be a JOB or an active workflow status, AND must NOT be a terminal lifecycle status
    const isWorkflowActive = i.entity_type === 'JOB' || 
                     ['APPROVED', 'QUOTED', 'ASSIGNED', 'SCHEDULED', 'JOB_CREATED', 'CANCELLATION_REQUESTED', 'IN_PROGRESS'].includes(status);
    
    const isLifecycleActive = !terminalStatuses.includes(status);
    
    if (!isWorkflowActive || !isLifecycleActive) return false;
    
    // Quick Filters
    const staffMatch = filters.staff === 'ALL' || i.worker_id === filters.staff;
    const statusMatch = filters.status === 'ALL' || i.status === filters.status;
    const serviceMatch = filters.service === 'ALL' || i.service_type === filters.service;
    
    // Date Filtering (Day/Week View)
    const visitDate = i.start_date; // Assuming start_date is the scheduled date
    if (!visitDate) return false;

    let dateMatch = true;
    if (viewMode === 'DAY') {
      dateMatch = visitDate === today;
    } else if (viewMode === 'WEEK') {
      const visitStartOfWeek = getStartOfWeek(visitDate);
      dateMatch = visitStartOfWeek === startOfWeek;
    }

    return staffMatch && statusMatch && serviceMatch && dateMatch;
  });

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
        <div className="filter-group">
          <label>Staff</label>
          <select value={filters.staff} onChange={(e) => setFilters({...filters, staff: e.target.value})}>
            <option value="ALL">All Staff</option>
            {Object.keys(staffPalette).filter(k=>k!=='Unassigned').map(name => (
              <option key={name} value={name}>{name}</option>
            ))}
            <option value="">Unassigned</option>
          </select>
        </div>
        <div className="filter-group">
          <label>Status</label>
          <select value={filters.status} onChange={(e) => setFilters({...filters, status: e.target.value})}>
            <option value="ALL">All Statuses</option>
            <option value="QUOTED">Quoted</option>
            <option value="APPROVED">Approved</option>
            <option value="ASSIGNED">Scheduled</option>
            <option value="IN_PROGRESS">In Progress</option>
            <option value="CANCELLATION_REQUESTED">Cancel Requested</option>
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
      </div>

      <div className="scheduler-grid">
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
                    <span className="visit-type">{job.window_type || job.service_type}</span>
                  </div>
                  <div className="visit-meta">
                    <span className="visit-time">{job.start_date}</span>
                    <span className="visit-staff" style={{ color: getWorkerColor(job.worker_id) }}>
                      {job.worker_id ? `Assigned to ${job.worker_id}` : '⚠️ UNASSIGNED'}
                    </span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

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
                    <span>{req.service_type}</span>
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
