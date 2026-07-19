"use client";

import React, { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { ShieldCheck, Star } from "lucide-react";

interface IntegrationItem {
  id: string;
  name: string;
  description: string;
  icon: string;
}

const leftIntegrations: IntegrationItem[] = [
  {
    id: "gcp",
    name: "Google Cloud",
    description: "Enterprise infrastructure",
    icon: "https://cdn.jiro.build/Amox/All%20Images/Plaid-icon-01.png",
  },
  {
    id: "bigquery",
    name: "BigQuery",
    description: "Data warehousing",
    icon: "https://cdn.jiro.build/Amox/All%20Images/Stripe-icon-02.png",
  },
  {
    id: "rapids",
    name: "NVIDIA RAPIDS",
    description: "GPU data processing",
    icon: "https://cdn.jiro.build/Amox/All%20Images/PayPal-icon-03.png",
  },
  {
    id: "gemini",
    name: "Gemini 2.0",
    description: "Advanced LLM reasoning",
    icon: "https://cdn.jiro.build/Amox/All%20Images/Visa-icon-04.png",
  },
];

const rightIntegrations: IntegrationItem[] = [
  {
    id: "salesforce",
    name: "Salesforce",
    description: "Sync leads & accounts",
    icon: "https://cdn.jiro.build/Amox/All%20Images/Mastercard-icon-05.png",
  },
  {
    id: "hubspot",
    name: "HubSpot",
    description: "Inbound CRM syncing",
    icon: "https://cdn.jiro.build/Amox/All%20Images/QuickBooks-icon-06.png",
  },
  {
    id: "slack",
    name: "Slack",
    description: "Real-time deal alerts",
    icon: "https://cdn.jiro.build/Amox/All%20Images/Xero-icon-07.png",
  },
  {
    id: "gmail",
    name: "Gmail / GSuite",
    description: "Automated outbound",
    icon: "https://cdn.jiro.build/Amox/All%20Images/Coinbase-icon-08.png",
  },
];

const topValues: Record<number, string> = { 0: "0px", 1: "96px", 2: "192px", 3: "288px" };

export default function Integration01Finsyc({ className }: { className?: string }) {
  const [isMounted, setIsMounted] = useState(false);
  const [windowWidth, setWindowWidth] = useState(0);

  useEffect(() => {
    const timer = setTimeout(() => {
      setIsMounted(true);
      setWindowWidth(window.innerWidth);
    }, 0);

    const handleResize = () => setWindowWidth(window.innerWidth);
    window.addEventListener("resize", handleResize);
    return () => {
      clearTimeout(timer);
      window.removeEventListener("resize", handleResize);
    };
  }, []);

  const isLargeScreen = isMounted && windowWidth >= 1024;

  return (
    <>
      <link rel="preconnect" href="https://fonts.googleapis.com" />
      <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
      <link href="https://fonts.googleapis.com/css2?family=Onest:wght@400;500;600;700&display=swap" rel="stylesheet" crossOrigin="anonymous" />

      <section className={"w-full bg-[#F4FAFB] py-16 md:py-[100px] overflow-hidden relative flex justify-center " + (className || "")}>
        <div className="w-full max-w-[1440px] px-6 lg:px-[96px]">
          <div className="w-full max-w-[1248px] mx-auto">

            {/* Header Content */}
            <div className="flex flex-col items-center text-center mb-12 md:mb-[80px]">
              {/* Tag */}
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                whileInView={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5 }}
                viewport={{ once: true }}
                className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#138E5F]/5 border border-[#138E5F]/10 mb-6"
              >
                <Star className="w-4 h-4 text-[#138E5F] fill-[#138E5F]" />
                <span className="text-[#138E5F] text-[14px] font-medium font-sans">Integrations</span>
              </motion.div>

              {/* Heading */}
              <motion.h2
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, delay: 0.1 }}
                viewport={{ once: true }}
                className="text-[32px] sm:text-[40px] md:text-[52px] font-semibold text-[#042718] leading-[1.2] md:leading-[58px] tracking-tight md:tracking-[-1.8px] mb-6 max-w-2xl text-center"
              >
                Integrate with the tools your team{" "}
                <span className="italic text-[rgba(0,0,0,0.40)]">already uses</span>
              </motion.h2>

              <motion.p
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, delay: 0.2 }}
                viewport={{ once: true }}
                className="text-[15px] md:text-[18px] text-[#042718] leading-[1.6] md:leading-[28px] max-w-[612px] font-sans font-normal opacity-80 text-center"
              >
                Connect KOE Syndicate directly to your CRM, communication tools, and data warehouse for a seamless pipeline.
              </motion.p>
            </div>

            {/* Integration Visualization */}
            <div className="relative w-full max-w-[1240px] mx-auto min-h-[400px] lg:h-[368px] flex items-center justify-center">

              {/* Desktop Only SVG Visualization */}
              <svg
                className="absolute inset-0 w-full h-full pointer-events-none hidden lg:block"
                viewBox="0 0 1240 368"
              >
                <defs>
                  <linearGradient id="line-gradient-left" x1="0%" y1="0%" x2="100%" y2="0%">
                    <stop offset="0%" stopColor="#138E5F" stopOpacity="0.02" />
                    <stop offset="100%" stopColor="#138E5F" stopOpacity="0.4" />
                  </linearGradient>
                  <linearGradient id="line-gradient-right" x1="100%" y1="0%" x2="0%" y2="0%">
                    <stop offset="0%" stopColor="#138E5F" stopOpacity="0.02" />
                    <stop offset="100%" stopColor="#138E5F" stopOpacity="0.4" />
                  </linearGradient>
                </defs>

                {/* Left Connection Paths */}
                {[225, 195, 165, 135].map((angle, i) => {
                  const rad = (angle * Math.PI) / 180;
                  const startX = 620 + 84 * Math.cos(rad);
                  const startY = 184 + 84 * Math.sin(rad);
                  const cardY = [40, 136, 232, 328][i];
                  const dPath = "M " + startX + " " + startY + " Q " + (startX - 150) + " " + startY + " 280 " + cardY;
                  return (
                    <React.Fragment key={"path-left-" + i}>
                      <path
                        d={dPath}
                        stroke="url(#line-gradient-left)"
                        fill="none"
                        strokeWidth="1.8"
                        strokeDasharray="4 4"
                        opacity="0.9"
                      />
                      <motion.circle r="3.5" fill="#138E5F">
                        <animateMotion
                          dur="3.5s"
                          repeatCount="indefinite"
                          path={dPath}
                          begin={i * 0.4 + "s"}
                        />
                      </motion.circle>
                    </React.Fragment>
                  );
                })}

                {/* Right Connection Paths */}
                {[-45, -15, 15, 45].map((angle, i) => {
                  const rad = (angle * Math.PI) / 180;
                  const startX = 620 + 84 * Math.cos(rad);
                  const startY = 184 + 84 * Math.sin(rad);
                  const cardY = [40, 136, 232, 328][i];
                  const dPath = "M " + startX + " " + startY + " Q " + (startX + 150) + " " + startY + " 960 " + cardY;
                  return (
                    <React.Fragment key={"path-right-" + i}>
                      <path
                        d={dPath}
                        stroke="url(#line-gradient-right)"
                        fill="none"
                        strokeWidth="1.8"
                        strokeDasharray="4 4"
                        opacity="0.9"
                      />
                      <motion.circle r="3.5" fill="#138E5F">
                        <animateMotion
                          dur="3.5s"
                          repeatCount="indefinite"
                          path={dPath}
                          begin={(i * 0.4 + 0.2) + "s"}
                        />
                      </motion.circle>
                    </React.Fragment>
                  );
                })}

                {/* Static Connection Dots at Seal */}
                {[225, 195, 165, 135, -45, -15, 15, 45].map((angle, i) => {
                  const rad = (angle * Math.PI) / 180;
                  return (
                    <motion.circle
                      key={"seal-dot-" + i}
                      cx={620 + 84 * Math.cos(rad)}
                      cy={184 + 84 * Math.sin(rad)}
                      r="5"
                      fill="#138E5F"
                      animate={{ scale: [1, 1.2, 1], opacity: [0.9, 1, 0.9] }}
                      transition={{ duration: 2.5, repeat: Infinity as number, delay: i * 0.2 }}
                    />
                  );
                })}
              </svg>

              {/* Visualization Container */}
              <div className="w-full flex flex-col lg:block relative z-10 lg:h-full">

                {/* Left column items */}
                <div className="flex flex-wrap lg:grid justify-center gap-4 lg:absolute lg:left-0 lg:top-0 lg:h-full lg:w-[280px] mb-8 lg:mb-0">
                  {leftIntegrations.map((item, idx) => (
                    <motion.div
                      key={item.id}
                      initial={{ opacity: 0, x: -20 }}
                      whileInView={{ opacity: 1, x: 0 }}
                      transition={{ duration: 0.6, delay: 0.1 + idx * 0.1 }}
                      viewport={{ once: true }}
                      className={"w-[240px] sm:w-[260px] lg:w-[280px] h-[72px] lg:h-[80px] bg-white rounded-[16px] lg:rounded-[20px] p-3 lg:p-[16px] flex items-center gap-3 lg:gap-4 shadow-[0_4px_20px_rgba(4,39,24,0.02)] group hover:shadow-[0_12px_40px_rgba(4,39,24,0.06)] transition-all cursor-default border border-black/[0.02] lg:absolute"}
                      style={{ top: isLargeScreen ? topValues[idx] : undefined }}
                    >
                      <div className="w-[48px] h-[48px] flex items-center justify-center shrink-0 group-hover:scale-110 transition-transform">
                        <img src={item.icon} alt={item.name} className="w-full h-full object-contain" referrerPolicy="no-referrer" />
                      </div>
                      <div className="flex flex-col">
                        <span className="text-[#042718] font-semibold text-[14px] lg:text-[16px] leading-tight">{item.name}</span>
                        <span className="text-[#042718]/40 text-[12px] lg:text-[13px] font-sans mt-0.5">{item.description}</span>
                      </div>
                    </motion.div>
                  ))}
                </div>

                {/* Center Seal */}
                <div className="flex items-center justify-center py-8 lg:py-0 lg:absolute lg:left-1/2 lg:top-1/2 lg:-translate-x-1/2 lg:-translate-y-1/2">
                  <div className="relative w-[100px] lg:w-[124px] h-[100px] lg:h-[124px] flex items-center justify-center">
                    <motion.div
                      animate={{ scale: [1, 1.05, 1], opacity: [0.3, 0.5, 0.3] }}
                      transition={{ duration: 4, repeat: Infinity as number, ease: "easeInOut" as const }}
                      className="absolute inset-0 -m-8 lg:-m-[58px] rounded-full bg-[#E4F3EB]/60 shadow-[inset_0_0_40px_rgba(19,142,95,0.03)]"
                    />
                    <div className="absolute inset-0 -m-4 lg:-m-[32px] rounded-full bg-white/40 backdrop-blur-[1px]" />

                    <motion.div
                      initial={{ scale: 0 }}
                      whileInView={{ scale: 1 }}
                      transition={{ type: "spring" as const, stiffness: 260, damping: 22 }}
                      viewport={{ once: true }}
                      className="w-full h-full rounded-full bg-white shadow-[0_12px_48px_rgba(19,142,95,0.12)] flex items-center justify-center relative z-10"
                    >
                      <div className="w-[84px] lg:w-[104px] h-[84px] lg:h-[104px] rounded-full bg-[#FAFFFD] flex items-center justify-center">
                        <img
                          src="https://cdn.jiro.build/Amox/All%20SVG/only%20loto-%20Finsyc.svg"
                          alt="Finsyc Logo"
                          className="w-[50px] lg:w-[64px] h-[50px] lg:h-[64px] object-contain opacity-95"
                          referrerPolicy="no-referrer"
                        />
                      </div>
                    </motion.div>
                  </div>
                </div>

                {/* Right column items */}
                <div className="flex flex-wrap lg:grid justify-center gap-4 lg:absolute lg:right-0 lg:top-0 lg:h-full lg:w-[280px] mt-8 lg:mt-0">
                  {rightIntegrations.map((item, idx) => (
                    <motion.div
                      key={item.id}
                      initial={{ opacity: 0, x: 20 }}
                      whileInView={{ opacity: 1, x: 0 }}
                      transition={{ duration: 0.6, delay: 0.1 + idx * 0.1 }}
                      viewport={{ once: true }}
                      className={"w-[240px] sm:w-[260px] lg:w-[280px] h-[72px] lg:h-[80px] bg-white rounded-[16px] lg:rounded-[20px] p-3 lg:p-[16px] flex items-center gap-3 lg:gap-4 shadow-[0_4px_20px_rgba(4,39,24,0.02)] group hover:shadow-[0_12px_40px_rgba(4,39,24,0.06)] transition-all cursor-default border border-black/[0.02] lg:absolute"}
                      style={{ top: isLargeScreen ? topValues[idx] : undefined }}
                    >
                      <div className="w-[48px] h-[48px] flex items-center justify-center shrink-0 group-hover:scale-110 transition-transform">
                        <img src={item.icon} alt={item.name} className="w-full h-full object-contain" referrerPolicy="no-referrer" />
                      </div>
                      <div className="flex flex-col">
                        <span className="text-[#042718] font-semibold text-[14px] lg:text-[16px] leading-tight">{item.name}</span>
                        <span className="text-[#042718]/40 text-[12px] lg:text-[13px] font-sans mt-0.5">{item.description}</span>
                      </div>
                    </motion.div>
                  ))}
                </div>
              </div>
            </div>

            {/* Footer Info */}
            <div className="flex flex-col items-center mt-12 md:mt-[80px] gap-6 md:gap-8">
              <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                whileInView={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.5, delay: 0.5 }}
                viewport={{ once: true }}
                className="inline-flex items-center gap-3 px-5 md:px-[24px] py-2 md:py-[11px] rounded-full border border-[#138E5F]/15 bg-white/50 shadow-[0_4px_24px_rgba(19,142,95,0.03)]"
              >
                <ShieldCheck className="w-5 h-5 text-[#138E5F]" />
                <p className="text-[13px] md:text-[15px] font-sans">
                  <span className="text-[#138E5F] font-semibold">Bank-level security.</span>{" "}
                  <span className="text-[#042718]/40">Your data is encrypted and never shared.</span>
                </p>
              </motion.div>

              <motion.p
                initial={{ opacity: 0 }}
                whileInView={{ opacity: 1 }}
                transition={{ duration: 0.8, delay: 0.6 }}
                viewport={{ once: true }}
                className="text-[13px] md:text-[15px] text-[#042718]/40 font-sans tracking-tight text-center px-4"
              >
                Built on {" "}
                <span className="font-semibold text-[#138E5F]">Google Cloud</span>{" "}
                infrastructure. Powered by {" "}
                <span className="font-semibold text-[#138E5F]">NVIDIA RAPIDS</span>{" "}
                and Gemini 2.0.
              </motion.p>
            </div>

          </div>
        </div>
      </section>
    </>
  );
}