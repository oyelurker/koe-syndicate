"use client";

import React, { useState } from 'react';
import { Sidebar } from '@/components/dashboard/Sidebar';
import { Pipeline } from '@/components/dashboard/Pipeline';
import { TerminalFeed } from '@/components/dashboard/TerminalFeed';
import { SdrModal } from '@/components/dashboard/Modals';
import { MOCK_BUSINESSES, MOCK_UPDATES, Business, AgentUpdate } from '@/components/dashboard/data';

export default function Dashboard() {
  const [businesses, setBusinesses] = useState<Business[]>(MOCK_BUSINESSES);
  const [updates, setUpdates] = useState<AgentUpdate[]>(MOCK_UPDATES);
  const [activeOperation] = useState("SAN FRANCISCO");

  // Modal State
  const [isSdrModalOpen, setIsSdrModalOpen] = useState(false);
  const [selectedBusiness, setSelectedBusiness] = useState<Business | null>(null);

  // Handlers
  const handleInitiateOutreach = (business: Business) => {
    setSelectedBusiness(business);
    setIsSdrModalOpen(true);
  };

  const handleConfirmOutreach = (business: Business, phoneOverride: string) => {
    // Update business status
    setBusinesses(prev => prev.map(b => 
      b.id === business.id ? { ...b, status: 'contacted', phone: phoneOverride } : b
    ));

    // Add log entry
    const newUpdate: AgentUpdate = {
      id: `u${Date.now()}`,
      timestamp: new Date().toISOString(),
      agent_type: 'sdr',
      message: `Initiated outreach to ${business.name} at ${phoneOverride}. Context transferred.`
    };
    setUpdates(prev => [...prev, newUpdate]);

    setIsSdrModalOpen(false);
    setSelectedBusiness(null);
  };

  const handleTriggerLeadManager = () => {
    const newUpdate: AgentUpdate = {
      id: `u${Date.now()}`,
      timestamp: new Date().toISOString(),
      agent_type: 'lead_manager',
      message: 'SIMULATION: Received inbound query from Vanguard Realty.'
    };
    setUpdates(prev => [...prev, newUpdate]);

    // Move Vanguard Realty (b7) to engaged for the demo
    setBusinesses(prev => prev.map(b => 
      b.id === 'b7' ? { ...b, status: 'engaged' } : b
    ));
  };

  const handleReset = () => {
    setBusinesses(MOCK_BUSINESSES);
    setUpdates(MOCK_UPDATES);
  };

  return (
    <div className="flex h-screen bg-[#0F0F19] text-gray-200 overflow-hidden font-sans">
      <Sidebar 
        businesses={businesses}
        onTriggerLeadManager={handleTriggerLeadManager}
        onReset={handleReset}
      />

      <main className="flex-1 flex flex-col p-8 overflow-hidden bg-[url('/grid.svg')] bg-center bg-fixed">
        <div className="mb-6 font-mono">
          <div className="text-gray-400 text-sm mb-1">// ACTIVE OPERATION: {activeOperation}</div>
          <div className="text-sm">
            STATUS: <span className="text-[#00ff88] animate-pulse">ACTIVE</span>
          </div>
        </div>

        <Pipeline 
          businesses={businesses} 
          onInitiateOutreach={handleInitiateOutreach} 
        />
        
        <TerminalFeed updates={updates} />
      </main>

      <SdrModal 
        business={selectedBusiness}
        isOpen={isSdrModalOpen}
        onClose={() => setIsSdrModalOpen(false)}
        onConfirm={handleConfirmOutreach}
      />
    </div>
  );
}
