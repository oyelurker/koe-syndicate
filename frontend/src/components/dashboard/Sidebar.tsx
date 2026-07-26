"use client";

import React, { useState, useEffect } from 'react';
import { Mail, Power, Calendar, Check, AlertCircle, Home } from 'lucide-react';
import { Business } from './data';

interface SidebarProps {
  businesses: Business[];
  onTriggerLeadManager: () => void;
  onReset: () => void;
  onRunDemo: () => void;
  isDemoRunning: boolean;
}

export function Sidebar({ businesses, onTriggerLeadManager, onReset, onRunDemo, isDemoRunning }: SidebarProps) {
  const [calendarEmail, setCalendarEmail] = useState<string | null>(null);

  useEffect(() => {
    // Check if we just authenticated
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('auth') === 'success') {
      // Clear the param
      window.history.replaceState({}, document.title, window.location.pathname);
    }
    
    // Fetch auth status
    const fetchAuthStatus = async () => {
      try {
        const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
        const res = await fetch(`${backendUrl}/auth/status`, { credentials: 'include' });
        if (res.ok) {
          const data = await res.json();
          if (data.connected && data.email) {
            setCalendarEmail(data.email);
          } else {
            setCalendarEmail(null);
          }
        }
      } catch (err) {
        console.error("Could not fetch auth status", err);
      }
    };
    
    fetchAuthStatus();
  }, []);

  const handleConnectCalendar = () => {
    const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
    let extraParams = "";
    if (typeof window !== "undefined") {
      const currentUrl = new URL(window.location.href);
      const city = currentUrl.searchParams.get('city') || '';
      const niche = currentUrl.searchParams.get('niche') || '';
      if (city || niche) {
        extraParams = `?city=${encodeURIComponent(city)}&niche=${encodeURIComponent(niche)}`;
      }
    }
    window.location.href = `${backendUrl}/auth/google${extraParams}`;
  };

  const handleDisconnectCalendar = async () => {
    try {
      const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
      await fetch(`${backendUrl}/auth/disconnect`, { method: 'POST', credentials: 'include' });
      setCalendarEmail(null);
    } catch (err) {
      console.error("Failed to disconnect", err);
    }
  };

  const engagedCount = businesses.filter(b => 
    ['contacted', 'engaged', 'converting', 'meeting_scheduled'].includes(b.status)
  ).length;

  return (
    <div className="w-[280px] p-8 border-r border-gray-200 flex flex-col gap-8 bg-white h-full shadow-sm z-10 relative">
      <div className="mb-0">
        <h1 className="text-2xl font-bold font-onest tracking-tight text-[#042718]">
          KOE Syndicate
        </h1>
        <div className="font-inter text-sm text-gray-500 mt-1 font-medium">Ops Console</div>
      </div>

      <div className="bg-[#f8f9fa] border border-gray-200 p-4 rounded-xl shadow-sm">
        <div className="flex items-center gap-2 font-inter text-sm font-medium mb-3">
          <Calendar size={16} className={calendarEmail ? 'text-green-600' : 'text-amber-500'} />
          <span className="text-gray-700">Google Calendar</span>
        </div>
        
        {calendarEmail ? (
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-xs text-green-700 bg-green-50 p-2 rounded-lg border border-green-100">
              <Check size={14} />
              <span className="truncate">{calendarEmail}</span>
            </div>
            <button 
              onClick={handleDisconnectCalendar}
              className="w-full text-xs text-gray-500 hover:text-gray-800 font-inter transition-colors text-left"
            >
              Disconnect
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-xs text-amber-700 bg-amber-50 p-2 rounded-lg border border-amber-100">
              <AlertCircle size={14} className="shrink-0" />
              <span>Not connected</span>
            </div>
            <button 
              onClick={handleConnectCalendar}
              className="w-full text-xs bg-white border border-gray-300 text-gray-700 py-2 rounded-lg hover:bg-gray-50 font-inter font-medium transition-colors"
            >
              Connect Calendar →
            </button>
          </div>
        )}
      </div>

      <div className="bg-[#f8f9fa] border border-gray-200 p-6 rounded-2xl text-center shadow-sm transition-shadow hover:shadow-md">
        <div className="font-inter text-sm text-gray-500 mb-2 font-medium">Acquired Leads</div>
        <div className="text-4xl font-bold text-[#042718] font-onest">{businesses.length}</div>
      </div>
      
      <div className="bg-[#f8f9fa] border border-gray-200 p-6 rounded-2xl text-center shadow-sm transition-shadow hover:shadow-md">
        <div className="font-inter text-sm text-gray-500 mb-2 font-medium">Engaged</div>
        <div className="text-4xl font-bold text-[#042718] font-onest">{engagedCount}</div>
      </div>

      <div className="mt-auto flex flex-col gap-3">
        {isDemoRunning ? (
          <div className="flex items-center justify-center gap-2 w-full p-3 bg-amber-50 text-amber-700 font-inter font-medium text-sm rounded-xl border border-amber-100">
            <div className="w-2 h-2 rounded-full bg-amber-500 animate-pulse"></div>
            Simulation Running...
          </div>
        ) : (
          <button 
            onClick={onRunDemo}
            className="flex items-center justify-center gap-2 w-full p-3 bg-blue-50 text-blue-700 font-inter font-medium text-sm rounded-xl hover:bg-blue-100 transition-colors border border-blue-100"
            title="Start the animated demo simulation"
          >
            ▶ Start Demo Simulation
          </button>
        )}
        <button 
          onClick={onReset}
          className="flex items-center justify-center gap-2 w-full p-3 bg-white border border-gray-200 text-gray-600 font-inter font-medium text-sm rounded-xl hover:bg-gray-50 hover:text-gray-900 transition-colors"
        >
          <Power size={16} /> Reset State
        </button>
        <a 
          href="/"
          className="flex items-center justify-center gap-2 w-full p-3 bg-white border border-gray-200 text-gray-600 font-inter font-medium text-sm rounded-xl hover:bg-gray-50 hover:text-gray-900 transition-colors"
        >
          <Home size={16} /> Back to Home
        </a>
      </div>
    </div>
  );
}
