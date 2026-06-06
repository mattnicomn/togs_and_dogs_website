import { useState, useEffect, useCallback } from 'react';
import { getStaff } from '../api/client';
import { Staff } from '../types';
import { useAuth } from '../auth/useAuth';

export const useStaff = (skip = false) => {
  const { logout } = useAuth();
  const [staff, setStaff] = useState<Staff[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchStaff = useCallback(async () => {
    if (skip) return;
    setIsLoading(true);
    setError(null);
    try {
      const response = await getStaff();
      // Backend returns either array directly or { staff: [] }
      const list: Staff[] = Array.isArray(response) ? response : response.staff || [];
      
      // Filter to active, assignable staff only
      const filtered = list.filter(
        (s) => s.is_active !== false && s.is_assignable !== false
      );
      
      setStaff(filtered);
    } catch (e: any) {
      console.warn('Failed to retrieve staff list', e);
      const msg = e.message || '';
      if (msg.includes('session expired') || msg.toLowerCase().includes('expired') || msg.toLowerCase().includes('unauthorized')) {
        setError('Your session expired. Please sign in again.');
        await logout();
      } else {
        setError(msg || 'Failed to retrieve staff list. Please retry.');
      }
    } finally {
      setIsLoading(false);
    }
  }, [skip, logout]);

  useEffect(() => {
    fetchStaff();
  }, [fetchStaff]);

  return {
    staff,
    isLoading,
    error,
    refresh: fetchStaff,
  };
};
