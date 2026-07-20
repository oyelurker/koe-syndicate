"use client";

import React from 'react';
import { Database, SatelliteDish, Crosshair } from 'lucide-react';
import { Business } from './data';
import { BusinessCard } from './BusinessCard';

interface PipelineProps {
  businesses: Business[];
  onInitiateOutreach: (business: Business) => void;
}

export function Pipeline({ businesses, onInitiateOutreach }: PipelineProps) {
  const foundLeads = businesses.filter(b => b.status === 'found');
  const activeLeads = businesses.filter(b => ['contacted', 'engaged', 'not_interested', 'no_response'].includes(b.status));
  const convertingLeads = businesses.filter(b => b.status === 'converting');
  const scheduledLeads = businesses.filter(b => b.status === 'meeting_scheduled');

  return (
    <div className="flex gap-6 h-[60vh] mb-8">
      {/* Stage 1: Data Mining */}
      <div className="flex-1 flex flex-col bg-[#111] border border-[#333] rounded-lg overflow-hidden">
        <div className="p-4 border-b border-[#333] bg-black/30 flex items-center justify-between font-mono text-sm">
          <span>[1] DATA_MINING</span>
          <Database size={16} className="text-[#00ff88]" />
        </div>
        <div className="flex-1 p-4 overflow-y-auto flex flex-col gap-4">
          {foundLeads.map(b => (
            <BusinessCard key={b.id} business={b} onInitiateOutreach={onInitiateOutreach} />
          ))}
        </div>
      </div>

      {/* Stage 2: Active Outreach */}
      <div className="flex-1 flex flex-col bg-[#111] border border-[#333] rounded-lg overflow-hidden">
        <div className="p-4 border-b border-[#333] bg-black/30 flex items-center justify-between font-mono text-sm">
          <span>[2] ACTIVE_OUTREACH</span>
          <SatelliteDish size={16} className="text-[#00ff88]" />
        </div>
        <div className="flex-1 p-4 overflow-y-auto flex flex-col gap-4">
          {activeLeads.map(b => (
            <BusinessCard key={b.id} business={b} />
          ))}
        </div>
      </div>

      {/* Stage 3: Conversion Ops */}
      <div className="flex-1 flex flex-col bg-[#111] border border-[#333] rounded-lg overflow-hidden">
        <div className="p-4 border-b border-[#333] bg-black/30 flex items-center justify-between font-mono text-sm">
          <span>[3] CONVERSION_OPS</span>
          <Crosshair size={16} className="text-[#00ff88]" />
        </div>
        
        {/* Converting Section */}
        <div className="p-4 overflow-y-auto flex flex-col gap-4 min-h-[50%]">
          {convertingLeads.map(b => (
            <BusinessCard key={b.id} business={b} />
          ))}
        </div>
        
        {/* Scheduled Section */}
        <div className="p-4 border-t border-[#333] overflow-y-auto flex flex-col gap-4 min-h-[30%]">
          <div className="font-mono text-[0.7rem] text-gray-400 mb-2">SECURED MEETINGS</div>
          {scheduledLeads.map(b => (
            <BusinessCard key={b.id} business={b} />
          ))}
        </div>
      </div>
    </div>
  );
}
