export type LeadStatus = 'found' | 'contacted' | 'engaged' | 'not_interested' | 'no_response' | 'converting' | 'meeting_scheduled';

export interface Business {
  id: string;
  name: string;
  city: string;
  phone: string | null;
  status: LeadStatus;
  ai_score?: number; // AI Predictive Conversion Score (0–100)
  calendar_event_url?: string;
  calendar_event_date?: string;
}

export type AgentType = 'sdr' | 'lead_finder' | 'lead_manager' | 'system';

export interface AgentUpdate {
  id: string;
  timestamp: string; // ISO format
  agent_type: AgentType;
  message: string;
}

// ─── Name banks by niche keyword ───────────────────────────────────────────────
const NAME_BANKS: Record<string, string[]> = {
  'real estate': [
    'Apex Realty', 'Crown Properties', 'Summit Estates', 'Pacific Edge Commercial',
    'Horizon Real Estate', 'Elevate Properties', 'Golden Gate Realty', 'Westland Group',
    'Vanguard Estates', 'Elite Properties'
  ],
  'it services': [
    'NexGen Solutions', 'CodeCraft Systems', 'TechAxis Consulting', 'Infosync Technologies',
    'Pinnacle IT Services', 'CloudBridge Labs', 'DataNest Systems', 'Synapse Tech',
    'BrightCore IT', 'Vertex Solutions'
  ],
  'healthcare': [
    'MedPoint Clinic', 'HealthFirst Medical', 'Vitality Care Center', 'ClearMed Associates',
    'Pinnacle Health Group', 'Apex Diagnostics', 'Summit Healthcare', 'Wellspring Clinic',
    'Horizon Medical', 'PrimeCare Associates'
  ],
  'education': [
    'Apex Learning Hub', 'BrightMind Institute', 'EduCraft Academy', 'Summit Ed Tech',
    'Horizon Coaching', 'NexStep Learning', 'TeachWell Academy', 'CoreLearn Institute',
    'EliteEd Solutions', 'Pinnacle Tutors'
  ],
  'finance': [
    'Apex Capital', 'Summit Financial', 'Horizon Wealth Advisors', 'CoreFin Group',
    'Vanguard Consulting', 'Crown Finance', 'Elevate Capital', 'NexGen Advisors',
    'Pinnacle Investments', 'Westland Finance'
  ],
};

const DEFAULT_NAMES = [
  'Apex Solutions', 'Crown Consulting', 'Summit Group', 'Pacific Edge Corp',
  'Horizon Ventures', 'Elevate Group', 'Core Systems', 'Westland Co.',
  'Vanguard Partners', 'Elite Consultants'
];

function getNamesForNiche(niche: string): string[] {
  const key = Object.keys(NAME_BANKS).find(k => niche.toLowerCase().includes(k));
  return key ? NAME_BANKS[key] : DEFAULT_NAMES;
}

// Indian-style phone prefixes per city
const CITY_PHONES: Record<string, string> = {
  'bengaluru':    '+91 80',
  'bangalore':    '+91 80',
  'mumbai':       '+91 22',
  'delhi':        '+91 11',
  'hyderabad':    '+91 40',
  'chennai':      '+91 44',
  'pune':         '+91 20',
  'kolkata':      '+91 33',
  'san francisco':'+1 415',
  'new york':     '+1 212',
  'london':       '+44 20',
};

function getPhonePrefix(city: string): string {
  const key = Object.keys(CITY_PHONES).find(k => city.toLowerCase().includes(k));
  return key ? CITY_PHONES[key] : '+91 98';
}

function fakePhone(prefix: string, seed: number): string {
  const n = (seed * 7919 + 1234) % 10000;
  return `${prefix}-${String(n).padStart(4, '0')}`;
}

// ─── Dynamic mock generator ─────────────────────────────────────────────────
export function getMockBusinesses(city: string, niche: string): Business[] {
  const names = getNamesForNiche(niche);
  const prefix = getPhonePrefix(city);
  const displayCity = city.charAt(0).toUpperCase() + city.slice(1).toLowerCase();

  const statuses: LeadStatus[] = [
    'found', 'found', 'found',
    'contacted',
    'engaged',
    'not_interested',
    'no_response',
    'converting',
    'meeting_scheduled',
  ];

  const scores = [87.3, 81.9, 64.2, 72.5, 91.0, 31.4, 48.8, 94.6, 96.2];

  return names.slice(0, 9).map((name, i) => ({
    id: `b${i + 1}`,
    name,
    city: displayCity,
    phone: i === 2 ? null : fakePhone(prefix, i * 17 + 3),
    status: statuses[i],
    ai_score: scores[i],
  }));
}

// Keep a default export for backward compat (San Francisco / Real Estate)
export const MOCK_BUSINESSES: Business[] = getMockBusinesses('San Francisco', 'real estate');

export const MOCK_UPDATES: AgentUpdate[] = [
  { id: 'u1', timestamp: new Date(Date.now() - 1000 * 60 * 60).toISOString(), agent_type: 'system', message: 'SYSTEM INITIALIZED.' },
  { id: 'u2', timestamp: new Date(Date.now() - 1000 * 60 * 45).toISOString(), agent_type: 'lead_finder', message: 'Scraped 45 local business listings from Google Maps API.' },
  { id: 'u3', timestamp: new Date(Date.now() - 1000 * 60 * 40).toISOString(), agent_type: 'lead_finder', message: 'Filtered out 36 businesses not meeting ICP criteria. 9 added to pipeline.' },
  { id: 'u4', timestamp: new Date(Date.now() - 1000 * 60 * 30).toISOString(), agent_type: 'sdr', message: 'Initiated outbound calls...' },
  { id: 'u5', timestamp: new Date(Date.now() - 1000 * 60 * 25).toISOString(), agent_type: 'sdr', message: 'Positive intent detected. Transferring context.' },
  { id: 'u6', timestamp: new Date(Date.now() - 1000 * 60 * 15).toISOString(), agent_type: 'lead_manager', message: 'Received inbound email regarding pricing.' },
  { id: 'u7', timestamp: new Date().toISOString(), agent_type: 'lead_manager', message: 'Drafting personalized response and scheduling link sent.' },
];
