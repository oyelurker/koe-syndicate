"use client";

import React from 'react';
import { Database, SatelliteDish, Crosshair } from 'lucide-react';
import { Business } from './data';
import { BusinessCard } from './BusinessCard';

interface PipelineProps {
  businesses: Business[];
  onInitiateOutreach: (business: Business) => void;
}

function PipelineColumn({ title, count, children }: { title: string, count: number, children: React.ReactNode }) {
  return (
    <div className="flex flex-col bg-white rounded-2xl border border-gray-200 overflow-hidden shadow-sm h-full">
      <div className="p-4 border-b border-gray-100 flex justify-between items-center bg-[#f8f9fa]">
        <h3 className="font-onest font-semibold text-[#042718] tracking-tight">{title}</h3>
        <span className="bg-white text-[#042718] font-inter text-xs px-2.5 py-1 rounded-full border border-gray-200 font-medium">
          {count}
        </span>
      </div>
      <div className="p-4 flex-1 overflow-y-auto space-y-4 custom-scrollbar">
        {children}
      </div>
    </div>
  );
}

export function Pipeline({ businesses, onInitiateOutreach }: PipelineProps) {
  const foundLeads = businesses.filter(b => b.status === 'found');
  const activeLeads = businesses.filter(b => ['contacted', 'engaged', 'not_interested', 'no_response'].includes(b.status));
  const convertingLeads = businesses.filter(b => b.status === 'converting');
  const scheduledLeads = businesses.filter(b => b.status === 'meeting_scheduled');

  return (
    <div className="flex-1 grid grid-cols-4 gap-6 mb-8 overflow-hidden h-full">
      <PipelineColumn 
        title="Discovered" 
        count={foundLeads.length}
      >
        {foundLeads.map(b => (
          <BusinessCard key={b.id} business={b} onInitiateOutreach={onInitiateOutreach} />
        ))}
      </PipelineColumn>

      <PipelineColumn 
        title="Active Outreach" 
        count={activeLeads.length}
      >
        {activeLeads.map(b => (
          <BusinessCard key={b.id} business={b} />
        ))}
      </PipelineColumn>

      <PipelineColumn 
        title="Conversion Ops" 
        count={convertingLeads.length}
      >
        {convertingLeads.map(b => (
          <BusinessCard key={b.id} business={b} />
        ))}
      </PipelineColumn>

      <PipelineColumn 
        title="Meeting Scheduled" 
        count={scheduledLeads.length}
      >
        {scheduledLeads.map(b => (
          <BusinessCard key={b.id} business={b} />
        ))}
      </PipelineColumn>
    </div>
  );
}
