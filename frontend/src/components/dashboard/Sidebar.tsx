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
    <div className="w-[280px] p-8 border-r border-gray-200 flex flex-col gap-8 bg-white h-full shadow-sm z-10 relative">
      <div className="mb-0">
        <h1 className="text-2xl font-bold font-onest tracking-tight text-[#042718]">
          KOE Syndicate
        </h1>
        <div className="font-inter text-sm text-gray-500 mt-1 font-medium">Ops Console</div>
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
        <button 
          onClick={onTriggerLeadManager}
          className="flex items-center justify-center gap-2 w-full p-3 bg-blue-50 text-blue-700 font-inter font-medium text-sm rounded-xl hover:bg-blue-100 transition-colors border border-blue-100"
          title="Trigger a mock email reply from a prospect"
        >
          <Mail size={16} /> Trigger Lead Manager
        </button>
        <button 
          onClick={onReset}
          className="flex items-center justify-center gap-2 w-full p-3 bg-white border border-gray-200 text-gray-600 font-inter font-medium text-sm rounded-xl hover:bg-gray-50 hover:text-gray-900 transition-colors"
        >
          <Power size={16} /> Reset State
        </button>
      </div>
    </div>
  );
}
