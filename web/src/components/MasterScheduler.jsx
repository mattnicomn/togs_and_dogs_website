import React, { useState } from 'react';

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
    const isActive = i.entity_type === 'JOB' || i.status === 'APPROVED' || i.status === 'CANCELLATION_REQUESTED';
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

      <style jsx>{`
        .master-scheduler { display: flex; flex-direction: column; gap: 20px; }
        .scheduler-header { display: flex; justify-content: space-between; align-items: flex-end; }
        .header-left { display: flex; flex-direction: column; gap: 12px; }
        .view-toggle { display: flex; background: var(--bg-muted); padding: 4px; border-radius: 12px; align-self: flex-start; }
        .view-toggle button { border: none; background: none; padding: 8px 16px; border-radius: 8px; font-size: 0.85rem; font-weight: 600; cursor: pointer; transition: all 0.2s; color: var(--text-main); }
        .view-toggle button.active { background: var(--bg-surface); box-shadow: 0 2px 4px rgba(0,0,0,0.1); color: var(--primary); }
        
        .filter-bar { display: flex; gap: 24px; padding: 16px 24px; background: var(--bg-surface); margin-bottom: 8px; }
        .filter-group { display: flex; flex-direction: column; gap: 4px; }
        .filter-group label { font-size: 0.75rem; font-weight: 700; color: var(--text-heading); text-transform: uppercase; opacity: 0.6; }
        .filter-group select { padding: 6px 12px; border-radius: 8px; border: 1px solid var(--border-soft); font-size: 0.9rem; background: var(--bg-muted); color: var(--text-main); }

        .legend { display: flex; gap: 16px; margin-bottom: 8px; }
        .legend-item { display: flex; align-items: center; gap: 6px; font-size: 0.8rem; font-weight: 600; }
        .dot { width: 8px; height: 8px; border-radius: 50%; }

        .scheduler-grid { display: grid; grid-template-columns: 1fr 340px; gap: 24px; align-items: start; }
        .card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        .badge-light { font-size: 0.8rem; padding: 2px 10px; background: var(--bg-warm); border-radius: 99px; font-weight: 600; }
        .badge-urgent { font-size: 0.8rem; padding: 2px 8px; background: #fee2e2; color: #991b1b; border-radius: 99px; font-weight: 700; }

        .timeline-container { display: flex; flex-direction: column; gap: 12px; }
        .scheduled-visit { 
          background: var(--bg-surface); 
          padding: 16px; 
          border-radius: var(--radius-md); 
          border-left: 6px solid; 
          border-top: 1px solid var(--border-soft);
          border-right: 1px solid var(--border-soft);
          border-bottom: 1px solid var(--border-soft);
          display: flex; 
          justify-content: space-between; 
          align-items: center; 
          cursor: pointer;
          transition: all 0.2s ease; 
          color: var(--text-main);
        }
        .scheduled-visit:hover { transform: translateX(4px); box-shadow: var(--shadow-soft); background: var(--bg-muted); }
        .scheduled-visit.urgent { background: var(--bg-surface); border-color: #fbd38d; box-shadow: inset 0 0 0 1px #fbd38d; }
        .scheduled-visit.cancelled { opacity: 0.6; filter: grayscale(0.5); border-style: dashed; }
        
        .urgent-border { border: 2px solid #ef4444 !important; }
        .urgent-text { color: #ef4444; font-weight: 700; font-size: 0.75rem; }
        .urgent-bg { background: #ef4444 !important; color: white !important; }
        .cancellation-item { border-left: 4px solid #ef4444; }
        .reason-preview { font-size: 0.7rem; color: var(--text-muted); margin: 4px 0; font-style: italic; }

        .visit-main { display: flex; flex-direction: column; gap: 2px; }
        .visit-pet { font-weight: 700; color: var(--text-heading); font-size: 1.1rem; }
        .visit-type { font-size: 0.8rem; font-weight: 600; color: var(--primary); text-transform: uppercase; }
        
        .visit-meta { text-align: right; display: flex; flex-direction: column; gap: 2px; }
        .visit-time { font-weight: 700; font-size: 0.95rem; color: var(--text-heading); }
        .visit-staff { font-size: 0.75rem; font-weight: 800; text-transform: uppercase; }
        .visit-meta span { color: var(--text-main); }

        .queue-list { display: flex; flex-direction: column; gap: 10px; }
        .queue-item { 
          padding: 12px; 
          background: var(--bg-muted);
          border-radius: 12px;
          display: flex; 
          justify-content: space-between; 
          align-items: center; 
          cursor: pointer;
          color: var(--text-main);
        }
        .queue-item:hover { background: var(--bg-surface); box-shadow: var(--shadow-soft); }
        .queue-info { display: flex; flex-direction: column; gap: 2px; font-size: 0.85rem; }
        .status-pill { font-size: 0.65rem; font-weight: 800; text-transform: uppercase; color: var(--text-muted); }
        
        @media (max-width: 1024px) { .scheduler-grid { grid-template-columns: 1fr; } }
      `}</style>
    </div>
  );
};

export default MasterScheduler;
