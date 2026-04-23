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

  // Advanced Filtering Logic
  const filteredJobs = items.filter(i => {
    const isActive = i.entity_type === 'JOB' || i.status === 'APPROVED' || i.status === 'CANCELLATION_REQUESTED' || i.status === 'JOB_CREATED' || i.status === 'ASSIGNED';
    if (!isActive) return false;
    
    const staffMatch = filters.staff === 'ALL' || i.worker_id === filters.staff;
    const statusMatch = filters.status === 'ALL' || i.status === filters.status;
    const serviceMatch = filters.service === 'ALL' || i.service_type === filters.service;
    
    return staffMatch && statusMatch && serviceMatch;
  });

  const pendingIntake = items.filter(i => i.status === 'PENDING_REVIEW' || i.status === 'MEET_GREET_REQUIRED');
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
        <div className="legend">
          {Object.entries(staffPalette).map(([name, color]) => (
            <div key={name} className="legend-item">
              <span className="dot" style={{ backgroundColor: color }}></span>
              {name}
            </div>
          ))}
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
            <option value="APPROVED">Approved</option>
            <option value="CANCELLATION_REQUESTED">Cancel Requested</option>
            <option value="ASSIGNED">Assigned</option>
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
