"use client";

import React, { useEffect, useRef } from 'react';
import { AgentUpdate } from './data';

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
    <div className="flex-1 flex flex-col bg-black/40 border border-[#333] rounded-lg overflow-hidden min-h-[200px] backdrop-blur-md">
      <div className="p-3 border-b border-[#333] font-mono text-sm text-gray-400">
        <div>// LIVE_TELEMETRY</div>
      </div>
      <div 
        ref={containerRef}
        className="flex-1 p-4 overflow-y-auto font-mono text-sm flex flex-col gap-2"
      >
        {updates.map(update => {
          let agentColor = 'text-gray-400';
          if (update.agent_type === 'sdr') agentColor = 'text-[#FF00FF]'; // Magenta
          else if (update.agent_type === 'lead_finder') agentColor = 'text-[#00ff88]'; // Green
          else if (update.agent_type === 'lead_manager') agentColor = 'text-[#00E5FF]'; // Cyan
          
          return (
            <div key={update.id} className="leading-tight mb-1">
              <span className="text-[#666] mr-3">[{formatDate(update.timestamp)}]</span>
              <span className={`${agentColor} font-bold mr-3`}>[{update.agent_type.toUpperCase()}]</span>
              <span className="text-gray-300">{update.message}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
