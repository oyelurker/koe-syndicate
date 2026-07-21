import React from 'react';
import { Phone, MapPin, ExternalLink } from 'lucide-react';
import { Business } from './data';

interface BusinessCardProps {
  business: Business;
  onInitiateOutreach?: (business: Business) => void;
}

export function BusinessCard({ business, onInitiateOutreach }: BusinessCardProps) {
  const isEngaged = ['contacted', 'engaged', 'converting', 'meeting_scheduled'].includes(business.status);

  return (
    <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-all duration-200 group flex flex-col gap-3 relative">
      <div className="flex justify-between items-start">
        <h4 className="font-onest font-semibold text-[#042718] text-lg leading-tight group-hover:text-[#063b24] transition-colors">{business.name}</h4>
        {isEngaged && (
          <span className="flex h-2.5 w-2.5 relative flex-shrink-0 mt-1.5">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-green-500"></span>
          </span>
        )}
      </div>
      
      <div className="space-y-2.5 font-inter">
        <div className="flex items-center gap-2 text-sm text-gray-600">
          <MapPin size={14} className="text-gray-400" /> 
          <span className="truncate">{business.city || 'No city found'}</span>
        </div>
        <div className="flex items-center gap-2 text-sm text-gray-600">
          <Phone size={14} className="text-gray-400" /> 
          <span>{business.phone || 'No phone found'}</span>
        </div>
      </div>

      {business.status === 'found' && onInitiateOutreach && (
        <button 
          onClick={(e) => {
            e.stopPropagation();
            onInitiateOutreach(business);
          }}
          className="mt-2 w-full py-2.5 bg-white border border-gray-200 text-[#042718] font-inter font-medium text-sm rounded-lg hover:bg-gray-50 hover:border-gray-300 transition-colors flex items-center justify-center gap-2"
        >
          Draft Outreach <ExternalLink size={14} />
        </button>
      )}

      {business.status === 'contacted' && (
        <div className="mt-2 text-xs font-medium text-blue-600 font-inter bg-blue-50 px-3 py-2 rounded-lg border border-blue-100 flex items-center justify-center">
          Email Sent - Waiting
        </div>
      )}

      {(business.status === 'engaged' || business.status === 'converting') && (
        <div className="mt-2 text-xs font-medium text-green-700 font-inter bg-green-50 px-3 py-2 rounded-lg border border-green-200 flex items-center justify-center">
          Prospect Replied
        </div>
      )}

      {business.status === 'not_interested' && (
        <div className="mt-2 text-xs font-medium text-gray-500 font-inter bg-gray-50 px-3 py-2 rounded-lg border border-gray-200 flex items-center justify-center">
          Not Interested
        </div>
      )}
      
      {business.status === 'no_response' && (
        <div className="mt-2 text-xs font-medium text-gray-500 font-inter bg-gray-50 px-3 py-2 rounded-lg border border-gray-200 flex items-center justify-center">
          No Response
        </div>
      )}

      {business.status === 'meeting_scheduled' && (
        <div className="mt-2 text-xs font-bold text-white font-inter bg-[#042718] px-3 py-2 rounded-lg flex items-center justify-center shadow-md">
          Meeting Scheduled!
        </div>
      )}
    </div>
  );
}
