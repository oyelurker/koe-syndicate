"use client";

import React from 'react';
import { Business } from './data';

interface BusinessCardProps {
  business: Business;
  onInitiateOutreach?: (business: Business) => void;
}

export function BusinessCard({ business, onInitiateOutreach }: BusinessCardProps) {
  // Determine styles based on status
  let borderColor = 'border-[#00ff88]/20';
  let hoverBorderColor = 'hover:border-[#00ff88] hover:shadow-[0_0_10px_rgba(0,255,136,0.1)]';
  let badgeColor = 'text-[#00ff88] bg-[#00ff88]/10 border-[#00ff88]';
  
  if (business.status === 'converting') {
    borderColor = 'border-[#00E5FF]';
    hoverBorderColor = 'hover:border-[#00E5FF] hover:shadow-[0_0_10px_rgba(0,229,255,0.1)]';
    badgeColor = 'text-[#00E5FF] bg-transparent border-[#00E5FF]';
  } else if (business.status === 'meeting_scheduled') {
    borderColor = 'border-[#FF00FF]';
    hoverBorderColor = 'hover:border-[#FF00FF] hover:shadow-[0_0_10px_rgba(255,0,255,0.1)]';
    badgeColor = 'text-[#FF00FF] bg-transparent border-[#FF00FF]';
  }

  return (
    <div className={`bg-black/60 border ${borderColor} p-4 rounded cursor-pointer transition-all duration-300 ${hoverBorderColor}`}>
      <h4 className="m-0 mb-2 text-white text-[0.95rem]">{business.name}</h4>
      
      {business.status === 'found' ? (
        <>
          <div className="text-[0.8rem] text-gray-400 mb-2">
            {business.city}<br />
            {business.phone || 'No Phone'}
          </div>
          <button 
            onClick={(e) => {
              e.stopPropagation();
              onInitiateOutreach?.(business);
            }}
            className="w-full mt-2 bg-transparent border border-[#00ff88] text-[#00ff88] p-2 cursor-pointer font-mono text-[0.8rem] rounded hover:bg-[#00ff88]/10 transition-colors"
          >
            INITIATE OUTREACH
          </button>
        </>
      ) : (
        <div className={`inline-block text-[0.7rem] px-2 py-0.5 border rounded-sm font-mono uppercase ${badgeColor}`}>
          {business.status.replace('_', ' ')}
        </div>
      )}
    </div>
  );
}
