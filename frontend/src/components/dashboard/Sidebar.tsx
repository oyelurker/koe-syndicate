"use client";

import React from 'react';
import { Mail, Power } from 'lucide-react';
import { Business } from './data';

interface SidebarProps {
  businesses: Business[];
  onTriggerLeadManager: () => void;
  onReset: () => void;
}

export function Sidebar({ businesses, onTriggerLeadManager, onReset }: SidebarProps) {
  const engagedCount = businesses.filter(b => 
    ['contacted', 'engaged', 'converting', 'meeting_scheduled'].includes(b.status)
  ).length;

  return (
    <div className="w-[250px] p-6 border-r border-[#333] flex flex-col gap-8 bg-black/40 h-full">
      <div className="mb-0">
        <h1 className="text-[1.2rem] font-bold text-[#00ff88] text-shadow-[0_0_10px_rgba(0,255,136,0.5)] tracking-wider uppercase">
          Koe Syndicate
        </h1>
        <div className="font-mono text-xs text-gray-400 mt-1">Ops Console</div>
      </div>

      <div className="bg-[#00ff88]/5 border border-[#333] p-6 rounded-lg text-center">
        <div className="font-mono text-xs text-gray-400 mb-2">Acquired Leads</div>
        <div className="text-4xl font-bold text-[#00ff88]">{businesses.length}</div>
      </div>
      
      <div className="bg-[#00ff88]/5 border border-[#333] p-6 rounded-lg text-center">
        <div className="font-mono text-xs text-gray-400 mb-2">Engaged</div>
        <div className="text-4xl font-bold text-[#00ff88]">{engagedCount}</div>
      </div>

      <div className="mt-auto flex flex-col gap-2">
        <button 
          onClick={onTriggerLeadManager}
          className="flex items-center justify-center gap-2 w-full p-2 bg-[#00E5FF]/10 border border-[#00E5FF] text-[#00E5FF] font-mono text-xs rounded hover:bg-[#00E5FF]/20 transition-colors"
          title="Trigger a mock email reply from a prospect"
        >
          <Mail size={16} /> TRIGGER LEAD MANAGER
        </button>
        <button 
          onClick={onReset}
          className="flex items-center justify-center gap-2 w-full p-2 bg-transparent border border-[#00ff88] text-[#00ff88] font-mono text-xs rounded hover:bg-[#00ff88]/10 transition-colors"
        >
          <Power size={16} /> RESET
        </button>
      </div>
    </div>
  );
}
