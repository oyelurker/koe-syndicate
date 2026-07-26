"use client";

import React, { useState, useEffect, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import { Sidebar } from '@/components/dashboard/Sidebar';
import { Pipeline } from '@/components/dashboard/Pipeline';
import { TerminalFeed } from '@/components/dashboard/TerminalFeed';
import { SdrModal } from '@/components/dashboard/Modals';
import { CreditWarningModal } from '@/components/dashboard/CreditWarningModal';
import { getMockBusinesses, AgentUpdate, Business } from '@/components/dashboard/data';

function DashboardContent() {
  const searchParams = useSearchParams();
  const cityParam = searchParams.get('city') || "SAN FRANCISCO";
  const nicheParam = searchParams.get('niche') || "";

  // Start with empty state for simulation
  const [businesses, setBusinesses] = useState<Business[]>([]);
  const [updates, setUpdates] = useState<AgentUpdate[]>([]);
  const [activeOperation, setActiveOperation] = useState(`${cityParam} ${nicheParam ? `- ${nicheParam}` : ''}`.toUpperCase());
  const [isDemoRunning, setIsDemoRunning] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  
  // Credits Check State
  const [isCreditsModalOpen, setIsCreditsModalOpen] = useState(false);
  const [creditsError, setCreditsError] = useState("");
  const [missingKeys, setMissingKeys] = useState<string[]>([]);
  const [systemReady, setSystemReady] = useState(false);
  const [isAuthChecking, setIsAuthChecking] = useState(true);

  // Modal State
  const [isSdrModalOpen, setIsSdrModalOpen] = useState(false);
  const [selectedBusiness, setSelectedBusiness] = useState<Business | null>(null);

  // Check Auth & System Status on load
  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
        
        // Check Google Auth
        const authRes = await fetch(`${backendUrl}/auth/status`, { credentials: 'include' });
        if (authRes.ok) {
          const authData = await authRes.json();
          setIsAuthenticated(authData.connected === true);
          
          if (authData.connected === true) {
            // Trigger real lead finding if authenticated
            const formData = new URLSearchParams();
            formData.append('city', cityParam);
            
            fetch(`${backendUrl}/start_lead_finding`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
              body: formData.toString()
            })
            .then(async res => {
              const contentType = res.headers.get('content-type') || '';
              if (!res.ok || !contentType.includes('application/json')) {
                // Backend returned an error or HTML page — silently skip, not user-facing
                return null;
              }
              return res.json();
            })
            .then(data => {
              if (data && data.businesses) setBusinesses(data.businesses);
            })
            .catch(() => {}); // Startup errors are expected if backend is warming up
          }
        }
        
        // Pre-check system readiness
        const sysRes = await fetch(`${backendUrl}/api/system-status`);
        if (sysRes.ok) {
          const sysData = await sysRes.json();
          setSystemReady(sysData.ready);
          if (!sysData.ready) {
            setCreditsError(sysData.message || "Unknown error verifying credentials");
            setMissingKeys(sysData.missing || []);
          }
        }
      } catch (err) {
        // Backend may still be starting up — this is expected on cold load
        if (process.env.NODE_ENV === 'development') {
          console.debug("Backend not yet ready:", (err as Error).message);
        }
      } finally {
        setIsAuthChecking(false);
      }
    };
    fetchStatus();
  }, [cityParam]);

  // WebSocket Connection (kept for real-time mode if needed, though demo overrides)
  useEffect(() => {
    const wsUrl = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000/ws';
    const ws = new WebSocket(wsUrl);

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        // Only update from WS if we have NO local businesses yet
        // This prevents WS from wiping the demo state after it completes
        if (data.type === 'initial_state') {
          if (data.businesses && data.businesses.length > 0) {
            setBusinesses(prev => prev.length === 0 ? data.businesses : prev);
          }
        } else if (data.type === 'business_updated') {
          setBusinesses(prev => {
            const exists = prev.find(b => b.id === data.business.id);
            return exists ? prev.map(b => b.id === data.business.id ? data.business : b) : [...prev, data.business];
          });
          if (data.update) {
            setUpdates(prev => [...prev, {
              id: `u${Date.now()}_${Math.random()}`,
              timestamp: new Date().toISOString(),
              agent_type: data.agent || 'system',
              message: data.update.message || `Status updated to ${data.update.status}`
            }]);
            
            // Check if this is an API limit error that should trigger Demo Mode
            if (data.update.message && (data.update.message.includes("Demo Mode") || data.update.message.includes("exhausted"))) {
                setCreditsError(data.update.message);
                setIsCreditsModalOpen(true);
            }
          }
        }
      } catch (err) {
        console.error("Failed to parse websocket message", err);
      }
    };
    return () => ws.close();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Run only once — never reconnect on state changes

  // The actual Demo Simulation Runner
  const handleRunDemo = async () => {
    const demoBusinesses = getMockBusinesses(cityParam, nicheParam);
    const b4name = demoBusinesses[3]?.name || 'Local Business';
    const b5name = demoBusinesses[4]?.name || 'Local Agency';
    const b8name = demoBusinesses[7]?.name || 'Prime Firm';
    const b9name = demoBusinesses[8]?.name || 'Top Lead';
    const displayCity = cityParam.charAt(0).toUpperCase() + cityParam.slice(1).toLowerCase();

    setIsDemoRunning(true);
    setBusinesses([]);
    setUpdates([{ id: 'init', timestamp: new Date().toISOString(), agent_type: 'system', message: `SYSTEM INITIALIZED. OPERATION: ${cityParam.toUpperCase()} — ${nicheParam ? nicheParam.toUpperCase() : 'ALL NICHES'}` }]);

    // Phase 1: Lead Finder (0s - 3s)
    setTimeout(() => {
      setUpdates(prev => [...prev, { id: 'lf1', timestamp: new Date().toISOString(), agent_type: 'lead_finder', message: `Scraped 45 local business listings from Google Maps API in ${displayCity}.` }]);
    }, 1500);

    setTimeout(() => {
      setUpdates(prev => [...prev, { id: 'lf2', timestamp: new Date().toISOString(), agent_type: 'lead_finder', message: `Filtered out 36 businesses not meeting ICP criteria. 9 added to pipeline.` }]);
      setBusinesses(demoBusinesses.map(b => ({ ...b, status: 'found' }))); // all found
    }, 3000);

    // Phase 2: SDR Outreach (4s - 8s)
    setTimeout(() => {
      setUpdates(prev => [...prev, { id: 'sdr1', timestamp: new Date().toISOString(), agent_type: 'sdr', message: `Initiated outbound call to ${b4name}...` }]);
      setBusinesses(prev => prev.map(b => b.id === 'b4' ? { ...b, status: 'contacted' } : b));
    }, 5000);

    setTimeout(() => {
      setUpdates(prev => [...prev, { id: 'sdr2', timestamp: new Date().toISOString(), agent_type: 'sdr', message: `${b5name} answered. Positive intent detected. Transferring context.` }]);
      setBusinesses(prev => prev.map(b => b.id === 'b5' ? { ...b, status: 'engaged' } : b));
    }, 7000);

    // Phase 3: Lead Manager (9s - 12s)
    setTimeout(() => {
      setUpdates(prev => [...prev, { id: 'lm1', timestamp: new Date().toISOString(), agent_type: 'lead_manager', message: `Received inbound email from ${b8name} regarding pricing.` }]);
      setBusinesses(prev => prev.map(b => b.id === 'b8' ? { ...b, status: 'converting' } : b));
    }, 10000);

    setTimeout(async () => {
      setUpdates(prev => [...prev, { id: 'lm2', timestamp: new Date().toISOString(), agent_type: 'lead_manager', message: `Drafting personalized response to ${b8name} and scheduling link sent to ${b9name}.` }]);
      
      // Phase 4: Meeting Scheduled (13s)
      let calendarEventUrl = "";
      let calendarEventDate = "";
      
      if (isAuthenticated) {
        try {
          const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
          const res = await fetch(`${backendUrl}/auth/schedule-meeting`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ lead_name: b9name }),
            credentials: 'include'
          });
          if (res.ok) {
            const data = await res.json();
            calendarEventUrl = data.event_url;
            calendarEventDate = data.date;
            setUpdates(prev => [...prev, { id: 'lm3', timestamp: new Date().toISOString(), agent_type: 'system', message: `Successfully created Google Calendar event for ${b9name}.` }]);
          } else {
            let errorMsg = 'Failed to create calendar event (unauthorized).';
            try {
              const errData = await res.json();
              if (errData.error) errorMsg = `Calendar Error: ${errData.error}`;
            } catch (e) {}
            setUpdates(prev => [...prev, { id: 'lm3', timestamp: new Date().toISOString(), agent_type: 'system', message: errorMsg }]);
          }
        } catch (err) {
          console.error("Failed to schedule meeting", err);
        }
      } else {
        // Fallback fake date
        const d = new Date();
        d.setDate(d.getDate() + 2);
        d.setHours(10, 0, 0, 0);
        calendarEventDate = d.toLocaleString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' });
      }

      setBusinesses(prev => prev.map(b => 
        b.id === 'b9' ? { 
          ...b, 
          status: 'meeting_scheduled',
          calendar_event_url: calendarEventUrl,
          calendar_event_date: calendarEventDate
        } : b
      ));
      
      // Mark demo as done but keep all the state intact — do NOT reset businesses/updates
      setIsDemoRunning(false);
    }, 13000);
  };

  // ── Partial Demo: runs SDR → Lead Manager → Calendar on EXISTING businesses ──
  const handleRunDemoFromOutreach = async (targetBusiness: Business) => {
    setIsCreditsModalOpen(false);
    setIsDemoRunning(true);

    const b4name = businesses[3]?.name || targetBusiness.name;
    const b5name = targetBusiness.name;
    const b8name = businesses[7]?.name || businesses[1]?.name || targetBusiness.name;
    const b9name = businesses[8]?.name || businesses[0]?.name || targetBusiness.name;

    // Log: SDR attempting call
    setUpdates(prev => [...prev,
      { id: `demo_sdr1`, timestamp: new Date().toISOString(), agent_type: 'sdr', message: `Google API, ElevenLabs, and Twilio credits exhausted. Switching to Demo Mode. Simulating outbound call to ${b5name}...` }
    ]);
    setBusinesses(prev => prev.map(b => b.id === targetBusiness.id ? { ...b, status: 'contacted' } : b));

    setTimeout(() => {
      setUpdates(prev => [...prev,
        { id: 'demo_sdr2', timestamp: new Date().toISOString(), agent_type: 'sdr', message: `${b5name} answered. Positive intent detected. Transferring context.` }
      ]);
      setBusinesses(prev => prev.map(b => b.id === targetBusiness.id ? { ...b, status: 'engaged' } : b));
    }, 3000);

    setTimeout(() => {
      setUpdates(prev => [...prev,
        { id: 'demo_lm1', timestamp: new Date().toISOString(), agent_type: 'lead_manager', message: `Received inbound email from ${b8name} regarding pricing.` }
      ]);
      setBusinesses(prev => prev.map(b => b.name === b8name ? { ...b, status: 'converting' } : b));
    }, 6000);

    setTimeout(async () => {
      setUpdates(prev => [...prev,
        { id: 'demo_lm2', timestamp: new Date().toISOString(), agent_type: 'lead_manager', message: `Drafting personalized response to ${b8name} and scheduling link sent to ${b9name}.` }
      ]);

      let calendarEventUrl = "";
      let calendarEventDate = "";

      if (isAuthenticated) {
        try {
          const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
          const res = await fetch(`${backendUrl}/auth/schedule-meeting`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ lead_name: b9name }),
            credentials: 'include'
          });
          if (res.ok) {
            const data = await res.json();
            calendarEventUrl = data.event_url;
            calendarEventDate = data.date;
            setUpdates(prev => [...prev, { id: 'demo_cal', timestamp: new Date().toISOString(), agent_type: 'system', message: `Successfully created Google Calendar event for ${b9name}.` }]);
          }
        } catch (e) { console.error('Calendar booking failed', e); }
      } else {
        const d = new Date();
        d.setDate(d.getDate() + 2);
        d.setHours(10, 0, 0, 0);
        calendarEventDate = d.toLocaleString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' });
      }

      setBusinesses(prev => prev.map(b =>
        b.name === b9name ? { ...b, status: 'meeting_scheduled', calendar_event_url: calendarEventUrl, calendar_event_date: calendarEventDate } : b
      ));
      setIsDemoRunning(false);
    }, 9000);
  };

  const handleInitiateOutreach = (business: Business) => {
    setSelectedBusiness(business);
    setIsSdrModalOpen(true);
  };

  const handleConfirmOutreach = async (business: Business, phoneOverride: string) => {
    setIsSdrModalOpen(false);
    setSelectedBusiness(business); // keep reference for demo
    
    // Show a quick "Attempting outreach..." log
    setUpdates(prev => [...prev, {
      id: `u${Date.now()}`,
      timestamp: new Date().toISOString(),
      agent_type: 'sdr',
      message: `Attempting outbound call to ${business.name} at ${phoneOverride}...`
    }]);

    try {
      const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
      const formData = new URLSearchParams();
      formData.append('business_id', business.id);
      if (phoneOverride) formData.append('user_phone', phoneOverride);
      
      const res = await fetch(`${backendUrl}/send_to_sdr`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: formData.toString()
      });

      if (!res.ok) {
        // Real call failed — show credit warning with option to run demo
        setCreditsError(`Outbound call to ${phoneOverride} blocked. Google API billing account, ElevenLabs, and Twilio trial credits exhausted.`);
        setIsCreditsModalOpen(true);
        return;
      }

      // Real call succeeded
      setSelectedBusiness(null);
      setBusinesses(prev => prev.map(b => b.id === business.id ? { ...b, status: 'contacted' } : b));
      setUpdates(prev => [...prev, { id: `u${Date.now()}`, timestamp: new Date().toISOString(), agent_type: 'sdr', message: `Live call initiated to ${business.name}. Context transferred.` }]);
      
    } catch {
      setCreditsError(`Connection error while calling ${phoneOverride}. API credits may be exhausted.`);
      setIsCreditsModalOpen(true);
    }
  };

  const handleReset = () => {
    setBusinesses([]);
    setUpdates([]);
    setIsDemoRunning(false);
  };

  if (isAuthChecking) {
    return <div className="flex h-screen items-center justify-center bg-[#f8f9fa] font-onest text-xl font-bold text-[#042718]">Verifying connection...</div>;
  }

  if (!isAuthenticated && !isDemoRunning) {
    const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
    const loginUrl = `${backendUrl}/auth/google?city=${encodeURIComponent(cityParam)}&niche=${encodeURIComponent(nicheParam)}`;
    return (
      <div className="flex h-screen items-center justify-center bg-[#f8f9fa] text-[#042718] font-inter">
        <div className="bg-white p-10 rounded-2xl shadow-xl max-w-md w-full text-center border border-gray-100">
          <div className="w-16 h-16 bg-[#042718] text-[#00ff9d] rounded-2xl flex items-center justify-center mx-auto mb-6 shadow-lg">
            <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
          </div>
          <h2 className="text-2xl font-bold font-onest mb-3">Connect Your Calendar</h2>
          <p className="text-gray-500 mb-8 leading-relaxed">
            Koe Syndicate agents need access to your calendar to schedule qualified leads.
          </p>
          <a 
            href={loginUrl}
            className="block w-full bg-[#042718] text-[#00ff9d] font-bold py-4 px-6 rounded-xl hover:bg-[#063b24] hover:shadow-lg transition-all duration-300 font-onest"
          >
            Connect Google Calendar
          </a>
          
          <div className="mt-6 pt-6 border-t border-gray-100">
            <button 
              onClick={handleRunDemo}
              className="text-sm text-gray-400 hover:text-gray-600 font-medium underline"
            >
              Skip and run in Demo Mode
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-[#f8f9fa] text-[#042718] overflow-hidden font-inter">
      <Sidebar 
        businesses={businesses}
        onTriggerLeadManager={handleRunDemo}
        onReset={handleReset}
        onRunDemo={handleRunDemo}
        isDemoRunning={isDemoRunning}
      />

      <main className="flex-1 flex flex-col p-8 overflow-hidden bg-white/50 relative">
        <div className="mb-8 flex items-center justify-between">
          <div>
            <div className="flex items-center gap-3">
              <h2 className="font-onest text-2xl font-bold tracking-tight text-[#042718]">Active Discovery Scan</h2>
              {!systemReady && <span className="px-2 py-0.5 rounded text-xs font-bold bg-amber-100 text-amber-800 border border-amber-300">DEMO MODE</span>}
            </div>
            <div className="text-gray-500 font-medium mt-1">OPERATION: {activeOperation}</div>
          </div>
          <div className="flex items-center gap-2 px-4 py-2 bg-green-50 text-green-700 rounded-full font-medium text-sm border border-green-200">
            <div className={`w-2 h-2 rounded-full bg-green-500 ${isDemoRunning ? 'animate-pulse' : ''}`}></div>
            STATUS: {isDemoRunning ? 'ACTIVE' : 'IDLE'}
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
      
      <CreditWarningModal
        isOpen={isCreditsModalOpen}
        onClose={() => setIsCreditsModalOpen(false)}
        onRunDemo={() => {
          if (selectedBusiness) {
            // Outreach triggered the modal — run partial demo on existing businesses
            handleRunDemoFromOutreach(selectedBusiness);
          } else {
            // Manual trigger from sidebar — run full demo
            setIsCreditsModalOpen(false);
            handleRunDemo();
          }
        }}
        message={creditsError}
        missingKeys={missingKeys}
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
