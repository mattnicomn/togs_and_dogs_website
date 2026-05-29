import React, { useState } from 'react';

const DatePickerGrid = ({ selectedDates = [], onDateToggle, maxSelections = 14, minDate }) => {
  const [displayMonth, setDisplayMonth] = useState(() => {
    const now = new Date();
    return { year: now.getFullYear(), month: now.getMonth() };
  });

  const { year, month } = displayMonth;
  const firstDay = new Date(year, month, 1);
  const lastDay = new Date(year, month + 1, 0);
  
  // 0 = Sunday, 1 = Monday, ... 6 = Saturday
  // Convert to Mon=0, Tue=1, ... Sun=6 for rendering
  let startDayOfWeek = firstDay.getDay() - 1;
  if (startDayOfWeek < 0) startDayOfWeek = 6;
  
  const totalDays = lastDay.getDate();
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const minDateObj = minDate ? new Date(minDate + 'T00:00:00') : today;

  const handlePrevMonth = (e) => {
    e.preventDefault();
    setDisplayMonth(prev => {
      if (prev.month === 0) return { year: prev.year - 1, month: 11 };
      return { year: prev.year, month: prev.month - 1 };
    });
  };

  const handleNextMonth = (e) => {
    e.preventDefault();
    setDisplayMonth(prev => {
      if (prev.month === 11) return { year: prev.year + 1, month: 0 };
      return { year: prev.year, month: prev.month + 1 };
    });
  };

  const getMonthName = (m) => {
    const names = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
    return names[m];
  };

  const renderCells = () => {
    const cells = [];
    // Padding for first row
    for (let i = 0; i < startDayOfWeek; i++) {
      cells.push(<div key={`empty-${i}`} className="date-picker-cell empty"></div>);
    }

    const maxReached = selectedDates.length >= maxSelections;

    for (let day = 1; day <= totalDays; day++) {
      const currentDate = new Date(year, month, day);
      currentDate.setHours(0, 0, 0, 0);
      
      const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
      const isSelected = selectedDates.includes(dateStr);
      const isPast = currentDate < minDateObj;
      const isToday = currentDate.getTime() === today.getTime();
      
      let className = "date-picker-cell";
      if (isSelected) className += " selected";
      else if (isPast) className += " disabled";
      else if (maxReached) className += " max-reached";
      
      if (isToday) className += " today";

      const handleClick = () => {
        if (isPast) return;
        if (!isSelected && maxReached) return;
        if (onDateToggle) onDateToggle(dateStr);
      };

      cells.push(
        <div 
          key={dateStr} 
          className={className} 
          onClick={handleClick}
          title={isPast ? "Past dates cannot be selected" : (!isSelected && maxReached ? "Maximum dates selected" : undefined)}
        >
          {day}
        </div>
      );
    }
    return cells;
  };

  return (
    <div className="date-picker-grid-container">
      <div className="date-picker-header">
        <button onClick={handlePrevMonth} className="btn-month-nav prev" aria-label="Previous Month">&lt;</button>
        <span className="date-picker-month-title">{getMonthName(month)} {year}</span>
        <button onClick={handleNextMonth} className="btn-month-nav next" aria-label="Next Month">&gt;</button>
      </div>
      
      <div className="date-picker-grid">
        <div className="date-picker-day-label">Mo</div>
        <div className="date-picker-day-label">Tu</div>
        <div className="date-picker-day-label">We</div>
        <div className="date-picker-day-label">Th</div>
        <div className="date-picker-day-label">Fr</div>
        <div className="date-picker-day-label">Sa</div>
        <div className="date-picker-day-label">Su</div>
        {renderCells()}
      </div>
    </div>
  );
};

export default DatePickerGrid;
