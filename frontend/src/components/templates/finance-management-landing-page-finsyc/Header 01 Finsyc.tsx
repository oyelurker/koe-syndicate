"use client";

import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ArrowUpRight, Sparkles, Menu, X, Search } from "lucide-react";
import { useRouter } from "next/navigation";

export default function FinsycOriginalHeader({ className }: { className?: string }) {
  const router = useRouter();
  const [city, setCity] = useState("");
  const [niche, setNiche] = useState("");
  const [isNavHovered, setIsNavHovered] = useState(false);
  const [isCTAHovered, setIsCTAHovered] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [isMounted, setIsMounted] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setIsMounted(true), 0);
    return () => clearTimeout(timer);
  }, []);

  useEffect(() => {
    if (isMobileMenuOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "unset";
    }
    return () => {
      document.body.style.overflow = "unset";
    };
  }, [isMobileMenuOpen]);

  const navItems = ["Agents", "Ops Console", "Tech Stack", "Documentation"];

  return (
    <>
      <link rel="preconnect" href="https://fonts.googleapis.com" />
      <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
      <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Onest:wght@400;500;600;700&family=Playfair+Display:ital,wght@1,600&display=swap" rel="stylesheet" crossOrigin="anonymous" />

      <motion.section
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 1, ease: "easeOut" as const }}
        className={"relative w-full overflow-hidden min-h-[800px] lg:min-h-[900px] " + (className || "")}
      >
        {/* Background Video */}
        <div className="absolute inset-0 z-0">
          {isMounted && (
            <video
              autoPlay
              loop
              muted
              playsInline
              className="w-full h-full object-cover"
            >
              <source
                src="https://cdn.jiro.build/Amox/All%20Images/P01-Header-01-BG.mp4"
                type="video/mp4"
              />
            </video>
          )}
        </div>

        <div className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-6 lg:pt-8 pb-12">
          {/* Navigation */}
          <motion.nav
            initial={{ y: -20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ delay: 0.2, duration: 0.6, ease: "easeOut" as const }}
            className="flex items-center justify-between"
          >
            <a href="/" className="flex items-center gap-2 hover:opacity-80 transition-opacity">
              <span className="font-onest font-bold text-2xl text-[#042718] tracking-tight">KOE Syndicate</span>
            </a>

            {/* Desktop Menu */}
            <ul className="hidden lg:flex items-center gap-8">
              {navItems.map((item: string) => (
                <li key={item}>
                  <a
                    href="#"
                    className={
                      "font-inter text-base leading-6 tracking-[-0.3px] text-[#042718] transition-all " +
                      (item === "Home"
                        ? "font-bold opacity-100"
                        : "font-normal opacity-80 hover:opacity-100 hover:font-bold")
                    }
                  >
                    {item}
                  </a>
                </li>
              ))}
            </ul>

            <div className="flex items-center gap-4">
              <motion.button
                onMouseEnter={() => setIsNavHovered(true)}
                onMouseLeave={() => setIsNavHovered(false)}
                layout
                className={
                  "hidden sm:flex items-center gap-3 py-1.5 rounded-full bg-white/10 backdrop-blur-sm border border-white/40 group cursor-pointer relative h-11 transition-all duration-300 " +
                  (isNavHovered ? "flex-row-reverse pl-1.5 pr-[18px]" : "flex-row pl-[18px] pr-1.5")
                }
              >
                <motion.span
                  layout
                  className="font-inter text-base font-medium leading-6 tracking-[-0.3px] text-[#042718]"
                >
                  View Demo
                </motion.span>

                <motion.div
                  layout
                  className="w-8 h-8 rounded-full bg-white flex items-center justify-center relative overflow-hidden shrink-0"
                >
                  <motion.div
                    animate={{
                      x: isNavHovered ? [-20, 0] : 0,
                      opacity: isNavHovered ? [0, 1] : 1
                    }}
                    transition={{ duration: 0.3, delay: isNavHovered ? 0.1 : 0 }}
                  >
                    <ArrowUpRight className="w-3 h-3 text-[#042718]" />
                  </motion.div>
                </motion.div>
              </motion.button>

              {/* Mobile Menu Toggle */}
              <button
                onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
                className="lg:hidden p-2 text-[#042718] bg-white/20 backdrop-blur-md rounded-full"
              >
                {isMobileMenuOpen ? <X size={24} /> : <Menu size={24} />}
              </button>
            </div>
          </motion.nav>

          {/* Mobile Navigation Drawer */}
          <AnimatePresence>
            {isMobileMenuOpen && (
              <motion.div
                key="mobile-menu"
                initial={{ x: "100%" }}
                animate={{ x: 0 }}
                exit={{ x: "100%" }}
                transition={{ type: "spring" as const, damping: 25, stiffness: 200 }}
                className="fixed inset-0 z-[100] lg:hidden bg-white px-6 py-8 flex flex-col gap-8"
              >
                <div className="flex items-center justify-between">
                  <span className="font-onest font-bold text-2xl text-[#042718] tracking-tight">KOE Syndicate</span>
                  <button
                    onClick={() => setIsMobileMenuOpen(false)}
                    className="p-2 text-[#042718] bg-[#042718]/5 rounded-full"
                  >
                    <X size={24} />
                  </button>
                </div>

                <ul className="flex flex-col gap-6">
                  {navItems.map((item: string, idx: number) => (
                    <motion.li
                      key={item}
                      initial={{ opacity: 0, x: 20 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: 0.1 * idx, ease: "easeOut" as const }}
                    >
                      <a
                        href="#"
                        onClick={() => setIsMobileMenuOpen(false)}
                        className="font-inter text-2xl font-semibold text-[#042718]"
                      >
                        {item}
                      </a>
                    </motion.li>
                  ))}
                </ul>

                <div className="mt-auto">
                  <button className="w-full py-4 rounded-full bg-[#042718] text-white font-inter font-medium text-lg">
                    View Demo
                  </button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Hero Content */}
          <div className="flex flex-col items-center mt-12 lg:mt-[80px]">
            {/* Rating Box */}
            <motion.div
              initial={{ y: 20, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              transition={{ delay: 0.4, duration: 0.8, ease: "easeOut" as const }}
              className="flex flex-row items-center gap-1.5 sm:gap-2 px-3 sm:px-[14px] py-1.5 rounded-full bg-white/10 backdrop-blur-sm border border-white/40 mb-6 whitespace-nowrap"
            >
              <div className="flex items-center gap-1 shrink-0">
                <Sparkles className="w-3.5 h-3.5 sm:w-4 sm:h-4 fill-[#042718] text-[#042718]" />
                <span className="font-inter text-sm sm:text-base lg:text-[18px] font-medium leading-[28px] text-[#042718]">
                  Hackathon Ready
                </span>
              </div>
              <span className="font-inter text-sm sm:text-base lg:text-[18px] font-normal leading-[28px] text-[#000000] opacity-60 shrink-0">
                Powered by Gemini 2.0 Flash
              </span>
            </motion.div>

            {/* Heading */}
            <motion.h1
              initial={{ y: 30, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              transition={{ delay: 0.6, duration: 0.8, ease: "easeOut" as const }}
              className="max-w-[750px] w-full text-center font-onest text-[40px] sm:text-[50px] lg:text-[66px] font-semibold leading-tight lg:leading-[72px] tracking-tight lg:tracking-[-3px] text-[#042718]"
            >
              Control Your B2B Pipeline with{" "}
              <span className="font-playfair italic font-semibold text-[#000000] opacity-50 tracking-normal lg:tracking-[-3.566px]">
                AI-Powered
              </span>{" "}
              Agents
            </motion.h1>

            {/* Subheading */}
            <motion.p
              initial={{ y: 20, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              transition={{ delay: 0.8, duration: 0.8, ease: "easeOut" as const }}
              className="max-w-[630px] w-full text-center mt-5 font-inter text-lg lg:text-[20px] font-normal leading-relaxed lg:leading-[30px] tracking-[-0.4px] text-[#042718]"
            >
              Automatically extract leads, qualify prospects, and execute voice and email outreach without lifting a finger.
            </motion.p>

            {/* CTA Form */}
            <motion.form
              onSubmit={(e) => {
                e.preventDefault();
                if (city && niche) {
                  router.push(`/dashboard?city=${encodeURIComponent(city)}&niche=${encodeURIComponent(niche)}`);
                }
              }}
              initial={{ y: 20, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              transition={{ delay: 1, duration: 0.8, ease: "easeOut" as const }}
              className="flex flex-col sm:flex-row items-center gap-3 mt-8 lg:mt-12 bg-white/20 p-2 rounded-2xl sm:rounded-full backdrop-blur-md border border-white/40 shadow-xl w-full max-w-2xl"
            >
              <input 
                type="text" 
                placeholder="Target City (e.g., Bengaluru)" 
                value={city}
                onChange={(e) => setCity(e.target.value)}
                required
                className="w-full sm:flex-1 h-12 px-5 rounded-xl sm:rounded-full bg-white text-[#042718] font-inter placeholder:text-gray-400 outline-none focus:ring-2 focus:ring-[#042718]/20"
              />
              <input 
                type="text" 
                placeholder="Target Niche (e.g., Fintech)" 
                value={niche}
                onChange={(e) => setNiche(e.target.value)}
                required
                className="w-full sm:flex-1 h-12 px-5 rounded-xl sm:rounded-full bg-white text-[#042718] font-inter placeholder:text-gray-400 outline-none focus:ring-2 focus:ring-[#042718]/20"
              />
              <button
                type="submit"
                onMouseEnter={() => setIsCTAHovered(true)}
                onMouseLeave={() => setIsCTAHovered(false)}
                className="w-full sm:w-auto flex items-center justify-center gap-2 h-12 px-6 rounded-xl sm:rounded-full bg-[#042718] text-white font-inter font-medium hover:bg-[#063b24] transition-colors"
              >
                <span>Run Discovery Scan</span>
                <Search className="w-4 h-4" />
              </button>
            </motion.form>

            {/* Presets */}
            <motion.div
              initial={{ y: 20, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              transition={{ delay: 1.1, duration: 0.8, ease: "easeOut" as const }}
              className="flex flex-wrap items-center justify-center gap-2 mt-4"
            >
              <span className="font-inter text-sm text-[#042718] opacity-70 mr-2">Try:</span>
              {[
                { c: "Bengaluru", n: "IT Services" },
                { c: "Mumbai", n: "Real Estate" },
                { c: "Singapore", n: "SaaS" },
                { c: "Dubai", n: "Hospitality" }
              ].map((preset, idx) => (
                <button
                  key={idx}
                  onClick={() => {
                    setCity(preset.c);
                    setNiche(preset.n);
                  }}
                  className="px-3 py-1.5 rounded-full bg-white/40 hover:bg-white/60 border border-white/40 text-[#042718] font-inter text-sm transition-colors"
                >
                  {preset.c} &bull; {preset.n}
                </button>
              ))}
            </motion.div>

            {/* Bottom Branding Section */}
            <motion.div
              initial={{ y: 40, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              transition={{ delay: 1.2, duration: 1, ease: "easeOut" as const }}
              className="mt-20 lg:mt-[220px] flex flex-col items-center gap-10 w-full"
            >
              <div className="px-[16px] py-1.5 rounded-full bg-white/5 backdrop-blur-sm border border-white/20">
                <p className="font-inter text-sm lg:text-base font-medium leading-6 tracking-[-0.3px] text-white text-center">
                  Collaborating with leading fintech innovators worldwide
                </p>
              </div>

              <div className="w-full mt-4 overflow-hidden" style={{ maskImage: "linear-gradient(to right, transparent, black 20%, black 80%, transparent)" } as React.CSSProperties}>
                <motion.div
                  animate={{ x: ["0%", "-50%"] }}
                  transition={{
                    duration: 25,
                    ease: "linear" as const,
                    repeat: Infinity as number
                  }}
                  className="flex items-center gap-12 sm:gap-16 lg:gap-24 w-fit"
                >
                  {[...Array(2)].map((_: unknown, i: number) => (
                    <React.Fragment key={i}>
                      <img src="https://cdn.jiro.build/Amox/All%20SVG/Horizon.svg" alt="Horizon" className="h-6 sm:h-7 lg:h-9 w-auto hover:opacity-80 transition-opacity" />
                      <img src="https://cdn.jiro.build/Amox/All%20SVG/Naxus.svg" alt="Naxus" className="h-6 sm:h-7 lg:h-9 w-auto hover:opacity-80 transition-opacity" />
                      <img src="https://cdn.jiro.build/Amox/All%20SVG/Lumassa.svg" alt="Lumassa" className="h-6 sm:h-7 lg:h-9 w-auto hover:opacity-80 transition-opacity" />
                      <img src="https://cdn.jiro.build/Amox/All%20SVG/Cyborg.svg" alt="Cyborg" className="h-6 sm:h-7 lg:h-9 w-auto hover:opacity-80 transition-opacity" />
                      <img src="https://cdn.jiro.build/Amox/All%20SVG/Catalyst.svg" alt="Catalyst" className="h-6 sm:h-7 lg:h-9 w-auto hover:opacity-80 transition-opacity" />
                    </React.Fragment>
                  ))}
                </motion.div>
              </div>
            </motion.div>
          </div>
        </div>
      </motion.section>
    </>
  );
}
