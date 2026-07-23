"use client";

import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import type { Variants } from "framer-motion";
import {
  Sparkles,
  ArrowUpRight,
  Check,
  Database,
  Search,
  LineChart,
  Cpu,
  type LucideIcon
} from "lucide-react";
import { cn } from "@/lib/utils";

interface ProcessStep {
  id: number;
  label: string;
  icon: LucideIcon;
  heading: string;
  subheading: string;
  list: string[];
  imgSrc: string;
}

const steps: ProcessStep[] = [
  {
    id: 1,
    label: "Ingest Data",
    icon: Database,
    heading: "Ingest Local Business Data",
    subheading: "Pull unstructured, hyper-targeted local business data directly from Google Maps and serper APIs.",
    list: [
      "Target specific business categories",
      "Extract rich metadata and contact info",
      "Real-time Google Maps integration"
    ],
    imgSrc: "https://cdn.jiro.build/Amox/All%20Images/P01-Process-img-01.png"
  },
  {
    id: 2,
    label: "Analyze Footprint",
    icon: Search,
    heading: "LLM-Powered Analysis",
    subheading: "Gemini 2.0 Flash analyzes the digital footprint of each lead, scoring them based on relevance and buying intent.",
    list: [
      "Deep semantic search on company sites",
      "Automated lead qualification and scoring",
      "Identify pain points automatically"
    ],
    imgSrc: "https://cdn.jiro.build/Amox/All%20Images/P01-Process-img-01.png"
  },
  {
    id: 3,
    label: "Visualize & Decide",
    icon: LineChart,
    heading: "Live Ops Console",
    subheading: "Push all insights to a real-time terminal-inspired dashboard where human operators can monitor and intervene.",
    list: [
      "WebSocket-powered live telemetry",
      "Human-in-the-loop oversight",
      "Approve or reject leads in one click"
    ],
    imgSrc: "https://cdn.jiro.build/Amox/All%20Images/P01-Process-img-01.png"
  },
  {
    id: 4,
    label: "Automate Outreach",
    icon: Cpu,
    heading: "Autonomous Execution",
    subheading: "Trigger specialized AI voice agents and email campaigns to engage qualified prospects completely autonomously.",
    list: [
      "Conversational calls via ElevenLabs",
      "Context-aware email drafting",
      "Automatic calendar booking"
    ],
    imgSrc: "https://cdn.jiro.build/Amox/All%20Images/P01-Process-img-01.png"
  }
];

export default function KoeOriginal4step({ className }: { className?: string }) {
  const [activeTab, setActiveTab] = useState(1);
  const [isHoveringBtn, setIsHoveringBtn] = useState(false);
  const [isMounted, setIsMounted] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setIsMounted(true), 0);
    return () => clearTimeout(timer);
  }, []);

  const activeStep = steps.find((s: ProcessStep) => s.id === activeTab) || steps[0];

  return (
    <>
      <link rel="preconnect" href="https://fonts.googleapis.com" />
      <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
      <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Onest:wght@400;500;600;700&family=Playfair+Display:ital,wght@1,600&display=swap" rel="stylesheet" crossOrigin="anonymous" />

      <section className={"w-full bg-[#F6FDFF] py-20 lg:py-32 overflow-hidden " + (className || "")}>
        <div className="w-full max-w-[1248px] mx-auto relative px-4 md:px-6">
          <div className="flex flex-col items-start gap-12 lg:gap-16">

            {/* Header Area */}
            <div className="flex flex-col items-start">
              <motion.div
                initial={{ x: -20, opacity: 0 }}
                whileInView={{ x: 0, opacity: 1 }}
                viewport={{ once: true }}
                className="flex items-center gap-2 px-4 py-1.5 rounded-full border border-[#198F38]/10 bg-[#198F38]/5 whitespace-nowrap mb-6"
              >
                <Sparkles className="w-4 h-4 text-[#198F38]" strokeWidth={2.5} />
                <span className="text-[#198F38] text-center font-inter text-base font-normal leading-6 tracking-[-0.3px]">
                  Process
                </span>
              </motion.div>

              <motion.h2
                initial={{ x: -30, opacity: 0 }}
                whileInView={{ x: 0, opacity: 1 }}
                viewport={{ once: true }}
                transition={{ delay: 0.2 }}
                className="text-[#042718] font-onest text-[32px] sm:text-[44px] lg:text-[52px] font-semibold leading-tight lg:leading-[58px] tracking-[-1.2px] lg:tracking-[-1.8px] w-full lg:max-w-[556px] text-left"
              >
                Automate your B2B sales
                <br className="block lg:hidden" />
                {" "}in{" "}
                <span className="text-black/40 font-playfair italic font-semibold">
                  4 simple
                </span>{" "}
                steps
              </motion.h2>
            </div>

            {/* Tabs and Card Container */}
            <div className="w-full flex flex-col gap-6">
              {/* Tab Selection Row */}
              <div className="w-full">
                <motion.div
                  initial={{ y: 20, opacity: 0 }}
                  whileInView={{ y: 0, opacity: 1 }}
                  viewport={{ once: true }}
                  transition={{ delay: 0.4 }}
                  className="w-full bg-white p-4 lg:px-6 lg:py-4 rounded-2xl shadow-[0_1px_20px_0_rgba(4,39,24,0.04)] flex items-center lg:justify-between gap-2 overflow-x-auto overflow-y-hidden scrollbar-hide snap-x"
                >
                  {steps.map((step: ProcessStep) => {
                    const isActive = activeTab === step.id;
                    return (
                      <button
                        key={step.id}
                        onClick={() => setActiveTab(step.id)}
                        className={cn(
                          "flex items-center gap-3 px-4 sm:px-6 py-2.5 rounded-xl transition-all duration-300 shrink-0 snap-start",
                          isActive ? "bg-white" : "hover:bg-[#F6FDFF]"
                        )}
                      >
                        <step.icon
                          className={cn("w-[22px] h-[22px]", isActive ? "text-[#198F38]" : "text-[#042718]/60")}
                          strokeWidth={2.5}
                        />
                        <span className={cn(
                          "font-inter text-base sm:text-[18px] leading-[28px] whitespace-nowrap",
                          isActive ? "text-[#198F38] font-medium" : "text-[#042718]/60 font-normal"
                        )}>
                          {step.label}
                        </span>
                      </button>
                    );
                  })}
                </motion.div>
              </div>

              {/* Main Content Card */}
              <div className="w-full">
                <div className="w-full bg-white rounded-[32px] border border-[#042718]/[0.04] shadow-[0_0_20px_0_rgba(4,39,24,0.04)] flex flex-col lg:flex-row items-center justify-between p-6 lg:pt-4 lg:pr-4 lg:pb-4 lg:pl-16 gap-12 lg:gap-0 overflow-hidden">

                  {/* Left Column: Text Info */}
                  <div className="w-full lg:w-[534px] flex flex-col items-start text-left">
                    <motion.div
                      key={"icon-" + activeTab}
                      initial={{ scale: 0.8, opacity: 0 }}
                      animate={{ scale: 1, opacity: 1 }}
                      transition={{ duration: 0.3 }}
                      className="w-16 h-16 rounded-xl border border-[#042718]/10 bg-white shadow-sm flex items-center justify-center p-4 mb-3"
                    >
                      <activeStep.icon className="w-8 h-8 text-[#198F38]" strokeWidth={2.5} />
                    </motion.div>

                    <motion.h3
                      key={"h3-" + activeTab}
                      initial={{ y: 20, opacity: 0 }}
                      animate={{ y: 0, opacity: 1 }}
                      transition={{ duration: 0.3 }}
                      className="text-[#042718] font-onest text-[28px] lg:text-[34px] font-semibold leading-tight lg:leading-[38px] tracking-[-1px] mb-4"
                    >
                      {activeStep.heading}
                    </motion.h3>

                    <motion.p
                      key={"p-" + activeTab}
                      initial={{ y: 20, opacity: 0 }}
                      animate={{ y: 0, opacity: 1 }}
                      transition={{ delay: 0.1, duration: 0.3 }}
                      className="text-[#042718] font-inter text-base lg:text-[18px] font-normal leading-relaxed lg:leading-[28px] opacity-80 mb-8"
                    >
                      {activeStep.subheading}
                    </motion.p>

                    <div className="flex flex-col gap-3 mb-12">
                      {activeStep.list.map((item: string, i: number) => (
                        <motion.div
                          key={"li-" + activeTab + "-" + i}
                          initial={{ x: -10, opacity: 0 }}
                          animate={{ x: 0, opacity: 1 }}
                          transition={{ delay: 0.2 + i * 0.1, duration: 0.3 }}
                          className="flex items-center gap-3"
                        >
                          <div className="w-5 h-5 rounded-full bg-[#198F38]/10 flex items-center justify-center shrink-0">
                            <Check className="w-3 h-3 text-[#198F38] stroke-[3px]" />
                          </div>
                          <span className="text-[#042718] font-inter text-base font-medium leading-6 tracking-[-0.3px]">
                            {item}
                          </span>
                        </motion.div>
                      ))}
                    </div>

                    {/* Action Button */}
                    <motion.button
                      onMouseEnter={() => setIsHoveringBtn(true)}
                      onMouseLeave={() => setIsHoveringBtn(false)}
                      layout
                      className={cn(
                        "flex items-center gap-3 py-2 rounded-full bg-[#042718] group cursor-pointer relative h-14 transition-all duration-300",
                        isHoveringBtn ? "flex-row-reverse pl-2 pr-5" : "flex-row pl-5 pr-2"
                      )}
                    >
                      <motion.span
                        layout
                        className="font-inter text-base lg:text-[18px] font-medium leading-[28px] text-white"
                      >
                        View Demo
                      </motion.span>

                      <motion.div
                        layout
                        className="w-10 h-10 rounded-full bg-white flex items-center justify-center relative overflow-hidden"
                      >
                        <motion.div
                          animate={{
                            x: isHoveringBtn ? [-20, 0] : 0,
                            opacity: isHoveringBtn ? [0, 1] : 1
                          }}
                          transition={{ duration: 0.3, delay: isHoveringBtn ? 0.1 : 0 }}
                        >
                          <ArrowUpRight className="w-4 h-4 text-[#042718]" />
                        </motion.div>
                      </motion.div>
                    </motion.button>
                  </div>

                  {/* Right Column: UI Card */}
                  <div className="w-full lg:w-[516px] h-[400px] sm:h-[500px] lg:h-[560px] relative rounded-[24px] overflow-hidden flex items-center justify-center">
                    {/* Video BG */}
                    <div className="absolute inset-0 z-0">
                      {isMounted && (
                        <video
                          autoPlay
                          loop
                          muted
                          playsInline
                          className="w-full h-full object-cover opacity-60"
                        >
                          <source src="https://cdn.jiro.build/Amox/All%20Images/P01-Header-01-BG.mp4" type="video/mp4" />
                        </video>
                      )}
                    </div>

                    {/* Dynamic Image */}
                    <AnimatePresence mode="wait">
                      <motion.div
                        key={"img-" + activeTab}
                        initial={{ scale: 0.9, opacity: 0, y: 30 }}
                        animate={{ scale: 1, opacity: 1, y: 0 }}
                        exit={{ scale: 1.1, opacity: 0, y: -30 }}
                        transition={{ duration: 0.5 }}
                        className="relative z-10 w-full flex items-center justify-center p-6 lg:p-0"
                      >
                        <img
                          src={activeStep.imgSrc}
                          alt={activeStep.heading}
                          className="w-full max-w-[384px] h-auto object-contain drop-shadow-2xl"
                        />
                      </motion.div>
                    </AnimatePresence>
                  </div>

                </div>
              </div>
            </div>

          </div>
        </div>
      </section>
    </>
  );
}
