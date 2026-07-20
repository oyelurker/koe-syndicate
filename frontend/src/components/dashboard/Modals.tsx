"use client";

import React, { useState } from 'react';
import { X } from 'lucide-react';
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
    <div className="fixed inset-0 bg-black/80 flex justify-center items-center z-50 backdrop-blur-sm">
      <div className="bg-[#0F0F19] border border-[#00ff88] p-8 rounded-lg w-[400px] shadow-[0_0_30px_rgba(0,255,136,0.15)] relative">
        <div className="flex justify-between items-center mb-6">
          <h3 className="m-0 text-[#00ff88] font-mono tracking-wider">AUTHORIZE OUTREACH</h3>
          <button 
            onClick={onClose}
            className="bg-transparent border-none text-white cursor-pointer hover:text-[#00ff88] transition-colors"
          >
            <X size={20} />
          </button>
        </div>
        
        <div className="mb-6">
          <div className="font-mono text-gray-400 mb-4 text-sm whitespace-pre-wrap leading-relaxed">
            TARGET: {business.name}
            <br />
            LOC: {business.city}
          </div>
          <div className="flex flex-col gap-2">
            <label className="font-mono text-sm text-gray-300">Target Ph. Number (Override)</label>
            <input 
              type="tel" 
              value={phoneOverride}
              onChange={(e) => setPhoneOverride(e.target.value)}
              className="w-full bg-[#05050A] border border-[#333] text-white p-3 font-mono rounded focus:border-[#00ff88] focus:outline-none transition-colors"
              required
            />
          </div>
        </div>
        
        <button 
          onClick={() => onConfirm(business, phoneOverride)}
          className="w-full bg-[#00ff88]/10 border border-[#00ff88] text-[#00ff88] p-3 font-mono tracking-wider rounded hover:bg-[#00ff88]/20 transition-all shadow-[0_0_10px_rgba(0,255,136,0.2)] hover:shadow-[0_0_15px_rgba(0,255,136,0.4)] cursor-pointer"
        >
          INITIATE CONTACT
        </button>
      </div>
    </div>
  );
}
