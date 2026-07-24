export type LeadStatus = 'found' | 'contacted' | 'engaged' | 'not_interested' | 'no_response' | 'converting' | 'meeting_scheduled';

export interface Business {
  id: string;
  name: string;
  city: string;
  phone: string | null;
  status: LeadStatus;
  ai_score?: number; // NVIDIA RAPIDS Predictive Conversion Score (0–100)
}

export type AgentType = 'sdr' | 'lead_finder' | 'lead_manager' | 'system';

export interface AgentUpdate {
  id: string;
  timestamp: string; // ISO format
  agent_type: AgentType;
  message: string;
}

export const MOCK_BUSINESSES: Business[] = [
  { id: 'b1', name: 'Apex Real Estate',       city: 'San Francisco', phone: '(415) 555-0198', status: 'found',            ai_score: 87.3 },
  { id: 'b2', name: 'Golden Gate Properties', city: 'San Francisco', phone: '(415) 555-0233', status: 'found',            ai_score: 81.9 },
  { id: 'b3', name: 'Bay Area Realty Co.',    city: 'San Francisco', phone: null,             status: 'found',            ai_score: 64.2 },
  { id: 'b4', name: 'Summit Group',           city: 'San Francisco', phone: '(415) 555-0771', status: 'contacted',        ai_score: 72.5 },
  { id: 'b5', name: 'Pacific Edge Commercial',city: 'San Francisco', phone: '(415) 555-0899', status: 'engaged',          ai_score: 91.0 },
  { id: 'b6', name: 'WestCoast Estates',      city: 'San Francisco', phone: '(415) 555-0455', status: 'not_interested',   ai_score: 31.4 },
  { id: 'b7', name: 'Vanguard Realty',        city: 'San Francisco', phone: '(415) 555-0912', status: 'no_response',      ai_score: 48.8 },
  { id: 'b8', name: 'Elevate Properties',     city: 'San Francisco', phone: '(415) 555-0331', status: 'converting',       ai_score: 94.6 },
  { id: 'b9', name: 'Horizon Real Estate',    city: 'San Francisco', phone: '(415) 555-0888', status: 'meeting_scheduled',ai_score: 96.2 },
];

export const MOCK_UPDATES: AgentUpdate[] = [
  { id: 'u1', timestamp: new Date(Date.now() - 1000 * 60 * 60).toISOString(), agent_type: 'system', message: 'SYSTEM INITIALIZED. OPERATION: SAN FRANCISCO' },
  { id: 'u2', timestamp: new Date(Date.now() - 1000 * 60 * 45).toISOString(), agent_type: 'lead_finder', message: 'Scraped 45 local business listings from Google Maps API.' },
  { id: 'u3', timestamp: new Date(Date.now() - 1000 * 60 * 40).toISOString(), agent_type: 'lead_finder', message: 'Filtered out 36 businesses not meeting ICP criteria. 9 added to pipeline.' },
  { id: 'u4', timestamp: new Date(Date.now() - 1000 * 60 * 30).toISOString(), agent_type: 'sdr', message: 'Initiated outbound call to Summit Group...' },
  { id: 'u5', timestamp: new Date(Date.now() - 1000 * 60 * 25).toISOString(), agent_type: 'sdr', message: 'Summit Group went to voicemail. Sent follow-up email.' },
  { id: 'u6', timestamp: new Date(Date.now() - 1000 * 60 * 15).toISOString(), agent_type: 'sdr', message: 'Pacific Edge Commercial answered. Positive intent detected. Transferring context.' },
  { id: 'u7', timestamp: new Date(Date.now() - 1000 * 60 * 5).toISOString(), agent_type: 'lead_manager', message: 'Received inbound email from Elevate Properties regarding pricing.' },
  { id: 'u8', timestamp: new Date().toISOString(), agent_type: 'lead_manager', message: 'Drafting personalized response to Elevate Properties and scheduling link sent to Horizon Real Estate.' },
];
