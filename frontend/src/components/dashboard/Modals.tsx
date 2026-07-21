"use client";

import React, { useState } from 'react';
import { X, Send } from 'lucide-react';
import { Business } from './data';

interface SdrModalProps {
  business: Business | null;
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (business: Business, phoneOverride: string) => void;
}

export function SdrModal({ business, isOpen, onClose, onConfirm }: SdrModalProps) {
  const [phoneOverride, setPhoneOverride] = useState('');

  // Update input when business changes
  React.useEffect(() => {
    if (business) {
      setPhoneOverride(business.phone || '');
    }
  }, [business]);

  if (!isOpen || !business) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex justify-center items-center z-50 backdrop-blur-sm">
      <div className="bg-white border border-gray-200 p-8 rounded-2xl w-[450px] shadow-2xl relative">
        <div className="flex justify-between items-center mb-6">
          <h3 className="m-0 text-[#042718] font-onest font-semibold text-xl tracking-tight">Draft Outreach</h3>
          <button 
            onClick={onClose}
            className="text-gray-400 hover:text-gray-700 hover:bg-gray-100 p-1 rounded-full transition-colors"
          >
            <X size={20} />
          </button>
        </div>
        
        <div className="mb-6">
          <div className="font-inter text-gray-600 mb-5 text-sm p-4 bg-gray-50 rounded-xl border border-gray-100">
            <span className="font-semibold block text-[#042718] mb-1">Target Prospect</span>
            {business.name} &bull; {business.city}
          </div>
          <div className="flex flex-col gap-2">
            <label className="font-inter text-sm font-medium text-[#042718]">Target Phone Number</label>
            <input 
              type="tel" 
              value={phoneOverride}
              onChange={(e) => setPhoneOverride(e.target.value)}
              className="w-full bg-white border border-gray-200 text-[#042718] px-4 py-3 font-inter rounded-xl focus:border-[#042718] focus:ring-1 focus:ring-[#042718] focus:outline-none transition-colors"
              required
            />
            <span className="text-xs text-gray-500 font-inter">The SDR Agent will contact this number directly.</span>
          </div>
        </div>
        
        <div className="flex gap-3 justify-end">
          <button 
            onClick={onClose}
            className="px-5 py-3 rounded-xl bg-white border border-gray-200 text-gray-700 font-inter font-medium hover:bg-gray-50 transition-colors"
          >
            Cancel
          </button>
          <button 
            onClick={() => onConfirm(business, phoneOverride)}
            className="flex items-center gap-2 px-6 py-3 bg-[#042718] text-white font-inter font-medium rounded-xl hover:bg-[#063b24] transition-colors shadow-md hover:shadow-lg"
          >
            <Send size={16} /> Deploy Agent
          </button>
        </div>
      </div>
    </div>
  );
}
