"use client";

import React, { useState, useEffect, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import { Sidebar } from '@/components/dashboard/Sidebar';
import { Pipeline } from '@/components/dashboard/Pipeline';
import { TerminalFeed } from '@/components/dashboard/TerminalFeed';
import { SdrModal } from '@/components/dashboard/Modals';
import { MOCK_BUSINESSES, MOCK_UPDATES, Business, AgentUpdate } from '@/components/dashboard/data';

function DashboardContent() {
  const searchParams = useSearchParams();
  const cityParam = searchParams.get('city') || "SAN FRANCISCO";
  const nicheParam = searchParams.get('niche') || "";

  const [businesses, setBusinesses] = useState<Business[]>(MOCK_BUSINESSES);
  const [updates, setUpdates] = useState<AgentUpdate[]>(MOCK_UPDATES);
  const [activeOperation, setActiveOperation] = useState(`${cityParam} ${nicheParam ? `- ${nicheParam}` : ''}`.toUpperCase());

  // Modal State
  const [isSdrModalOpen, setIsSdrModalOpen] = useState(false);
  const [selectedBusiness, setSelectedBusiness] = useState<Business | null>(null);

  // WebSocket Connection
  useEffect(() => {
    const wsUrl = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000/ws';
    const ws = new WebSocket(wsUrl);

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        console.log("WebSocket event:", data);
        
        if (data.type === 'initial_state') {
          if (data.businesses && data.businesses.length > 0) {
            setBusinesses(data.businesses);
          }
        } else if (data.type === 'business_updated') {
          setBusinesses(prev => {
            const exists = prev.find(b => b.id === data.business.id);
            if (exists) {
              return prev.map(b => b.id === data.business.id ? data.business : b);
            } else {
              return [...prev, data.business];
            }
          });
          
          if (data.update) {
            const newUpdate: AgentUpdate = {
              id: `u${Date.now()}_${Math.random()}`,
              timestamp: new Date().toISOString(),
              agent_type: data.agent || 'system',
              message: data.update.message || `Status updated to ${data.update.status}`
            };
            setUpdates(prev => [...prev, newUpdate]);
          }
        } else if (data.type === 'agent_status') {
           const newUpdate: AgentUpdate = {
              id: `u${Date.now()}_${Math.random()}`,
              timestamp: new Date().toISOString(),
              agent_type: data.agent || 'system',
              message: data.message
           };
           setUpdates(prev => [...prev, newUpdate]);
        }
      } catch (err) {
        console.error("Failed to parse websocket message", err);
      }
    };

    return () => {
      ws.close();
    };
  }, []);

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
    <div className="flex h-screen bg-[#f8f9fa] text-[#042718] overflow-hidden font-inter">
      <Sidebar 
        businesses={businesses}
        onTriggerLeadManager={handleTriggerLeadManager}
        onReset={handleReset}
      />

      <main className="flex-1 flex flex-col p-8 overflow-hidden bg-white/50">
        <div className="mb-8 flex items-center justify-between">
          <div>
            <div className="flex items-center gap-3">
              <h2 className="font-onest text-2xl font-bold tracking-tight text-[#042718]">Active Discovery Scan</h2>
              <span className="px-2 py-0.5 rounded text-xs font-bold bg-amber-100 text-amber-800 border border-amber-300">DEMO MODE</span>
            </div>
            <div className="text-gray-500 font-medium mt-1">OPERATION: {activeOperation}</div>
          </div>
          <div className="flex items-center gap-2 px-4 py-2 bg-green-50 text-green-700 rounded-full font-medium text-sm border border-green-200">
            <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></div>
            STATUS: ACTIVE
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

export default function Dashboard() {
  return (
    <Suspense fallback={<div className="flex h-screen items-center justify-center bg-[#f8f9fa] font-onest text-xl font-bold text-[#042718]">Loading Dashboard...</div>}>
      <DashboardContent />
    </Suspense>
  );
}
