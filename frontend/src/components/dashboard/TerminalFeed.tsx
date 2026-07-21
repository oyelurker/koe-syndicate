"use client";

import React, { useEffect, useRef } from 'react';
import { AgentUpdate } from './data';
import { Activity } from 'lucide-react';

interface TerminalFeedProps {
  updates: AgentUpdate[];
}

export function TerminalFeed({ updates }: TerminalFeedProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new updates
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [updates]);

  const formatDate = (isoString: string) => {
    const d = new Date(isoString);
    return `${d.toLocaleDateString()} ${d.toLocaleTimeString([], { hour12: false })}`;
  };

  return (
    <div className="flex-1 flex flex-col bg-white border border-gray-200 rounded-2xl overflow-hidden min-h-[200px] shadow-sm">
      <div className="p-4 border-b border-gray-100 bg-[#f8f9fa] flex items-center gap-2">
        <Activity size={18} className="text-[#042718]" />
        <span className="font-onest font-semibold text-[#042718] tracking-tight">Activity Log</span>
      </div>
      <div 
        ref={containerRef}
        className="flex-1 p-5 overflow-y-auto font-inter text-sm flex flex-col gap-3 custom-scrollbar"
      >
        {updates.map(update => {
          let badgeClass = 'bg-gray-100 text-gray-700 border-gray-200';
          if (update.agent_type === 'sdr') badgeClass = 'bg-purple-50 text-purple-700 border-purple-200'; 
          else if (update.agent_type === 'lead_finder') badgeClass = 'bg-blue-50 text-blue-700 border-blue-200'; 
          else if (update.agent_type === 'lead_manager') badgeClass = 'bg-orange-50 text-orange-700 border-orange-200'; 
          
          return (
            <div key={update.id} className="flex items-start gap-3 py-1">
              <span className="text-gray-400 text-xs mt-1 shrink-0 whitespace-nowrap">{formatDate(update.timestamp)}</span>
              <span className={`text-xs font-semibold px-2 py-0.5 rounded-md border ${badgeClass} shrink-0`}>
                {update.agent_type.replace('_', ' ').toUpperCase()}
              </span>
              <span className="text-gray-700 leading-snug">{update.message}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
