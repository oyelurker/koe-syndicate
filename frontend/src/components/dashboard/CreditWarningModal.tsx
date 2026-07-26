import React from 'react';
import { AlertTriangle, X, Play } from 'lucide-react';

interface CreditWarningModalProps {
  isOpen: boolean;
  onClose: () => void;
  onRunDemo: () => void;
  message: string;
  missingKeys: string[];
}

export function CreditWarningModal({ isOpen, onClose, onRunDemo, message, missingKeys }: CreditWarningModalProps) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm font-inter">
      <div className="w-[500px] bg-white rounded-2xl shadow-2xl overflow-hidden flex flex-col animate-in fade-in zoom-in duration-200">
        
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-100 bg-amber-50">
          <div className="flex items-center gap-2 text-amber-800">
            <AlertTriangle size={20} className="text-amber-500" />
            <h3 className="font-bold text-lg font-onest">Insufficient API Credits</h3>
          </div>
          <button 
            onClick={onClose}
            className="p-1.5 text-amber-600 hover:bg-amber-100 rounded-lg transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 flex flex-col gap-4">
          <p className="text-gray-600 text-sm leading-relaxed">
            The AI Agent attempted to initiate a live action (e.g., outbound call), but there was an issue with your credentials or trial quota limit.
            Live AI pipelines require an active funded account.
          </p>
          
          <div className="p-4 bg-red-50 border border-red-100 rounded-xl flex flex-col gap-2">
            <span className="text-xs font-bold text-red-800 uppercase tracking-wider">Error Details</span>
            <div className="text-sm font-medium text-red-700">
              {message}
            </div>
            {missingKeys.length > 0 && (
              <ul className="text-xs text-red-600 list-disc list-inside mt-1">
                {missingKeys.map(key => <li key={key}>{key}</li>)}
              </ul>
            )}
          </div>
          
          <p className="text-gray-600 text-sm mt-2">
            You can still experience the full platform by running the <b>Animated Demo Simulation</b>, which doesn't use any API credits!
          </p>
        </div>

        {/* Footer */}
        <div className="p-4 bg-gray-50 border-t border-gray-100 flex gap-3 justify-end">
          <button 
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-gray-600 bg-white border border-gray-200 rounded-xl hover:bg-gray-50 transition-colors"
          >
            Cancel
          </button>
          <button 
            onClick={() => {
              onClose();
              onRunDemo();
            }}
            className="flex items-center gap-2 px-6 py-2 text-sm font-bold text-white bg-amber-500 rounded-xl hover:bg-amber-600 transition-colors shadow-sm"
          >
            <Play size={16} className="fill-white" />
            Run in Demo Mode
          </button>
        </div>

      </div>
    </div>
  );
}
