"use client";

import React, { useEffect, useRef, useState } from "react";
import { motion, useSpring, useTransform, useInView } from "framer-motion";
import { Sparkles, ArrowLeft, ArrowRight, Star } from "lucide-react";

// --- Counter Component ---

interface CounterProps {
  value: number;
  suffix: string;
}

function Counter({ value, suffix }: CounterProps) {
  const ref = useRef<HTMLDivElement>(null);
  const isInView = useInView(ref, { once: true, margin: "-100px" });

  const spring = useSpring(0, {
    stiffness: 100,
    damping: 30,
    restDelta: 0.001,
  });

  const display = useTransform(spring, (current: number) => Math.floor(current).toString());

  useEffect(() => {
    if (isInView) {
      spring.set(value);
    }
  }, [isInView, spring, value]);

  return (
    <div ref={ref} className="flex justify-center items-baseline gap-[2px]">
      <motion.span className="text-[#042718] text-[52px] font-semibold leading-[58px] tracking-[-1.8px]">
        {display}
      </motion.span>
      <span className="text-black/40 text-[42px] font-semibold leading-[48px] tracking-[-2px]">
        {suffix}
      </span>
    </div>
  );
}

// --- MetricCard Component ---

function MetricCard({
  number,
  suffix,
  title,
  description,
  delay,
}: {
  number: number;
  suffix: string;
  title: string;
  description: string;
  delay: number;
}) {
  return (
    <motion.div
      initial={{ y: 20, opacity: 0 }}
      whileInView={{ y: 0, opacity: 1 }}
      viewport={{ once: true }}
      transition={{ duration: 0.8, delay }}
      className="flex flex-col items-start w-full sm:w-[400px]"
    >
      <div className="flex flex-col items-start w-full sm:w-[294px] p-[20px_24px] gap-2.5 rounded-[24px] bg-white/40 backdrop-blur-md border border-white/20 shadow-[0_8px_32px_rgba(4,39,24,0.06)]">
        <Counter value={number} suffix={suffix} />
        <p className="text-[#042718] text-[18px] font-medium leading-[28px]">
          {title}
        </p>
      </div>
      <p className="mt-4 text-[#042718] text-[16px] font-normal leading-[24px] tracking-[-0.3px] opacity-80 line-clamp-2 pr-[20px]">
        {description}
      </p>
    </motion.div>
  );
}

// --- Testimonial Data ---

interface Testimonial {
  id: number;
  text: string;
  name: string;
  role: string;
  avatar: string;
}

const testimonials: Testimonial[] = [
  {
    id: 1,
    text: "KOE Syndicate completely transformed our outbound strategy. We saw a 3x increase in booked meetings within the first month.",
    name: "Michael Reynolds",
    role: "VP of Sales, TechCorp",
    avatar: "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=150&h=150&fit=crop",
  },
  {
    id: 2,
    text: "The NVIDIA RAPIDS integration is mind-blowing. What used to take hours of data processing now finishes in milliseconds. Truly autonomous.",
    name: "Sarah Jenkins",
    role: "Director of Revenue Ops",
    avatar: "https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=150&h=150&fit=crop",
  },
  {
    id: 3,
    text: "Lead Finder Agent pulls better local business data than our $10k/year database subscription. The semantic scoring is spot on.",
    name: "Daniel Carter",
    role: "Head of Growth",
    avatar: "https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=150&h=150&fit=crop",
  },
  {
    id: 4,
    text: "I love the Human-in-the-Loop Ops Console. We let the agents run on autopilot, but can intervene on high-value enterprise leads instantly.",
    name: "Emily Watson",
    role: "Sales Manager",
    avatar: "https://images.unsplash.com/photo-1438761681033-6461ffad8d80?w=150&h=150&fit=crop",
  },
  {
    id: 5,
    text: "The Voice SDR sounds so natural. Prospects don't even realize they're talking to an AI until they've already agreed to a meeting.",
    name: "James Wilson",
    role: "Founder & CEO",
    avatar: "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=150&h=150&fit=crop",
  },
];

const displayTestimonials: Testimonial[] = [...testimonials, ...testimonials, ...testimonials];

// --- Main Component ---

export default function MetricAndTestimonials({ className }: { className?: string }) {
  const metrics = [
    {
      number: 150,
      suffix: "x",
      title: "Faster Data Processing",
      description: "NVIDIA RAPIDS cuDF accelerates lead ingestion and scoring pipelines compared to standard tools.",
    },
    {
      number: 24,
      suffix: "/7",
      title: "Autonomous Uptime",
      description: "Agents execute calls, emails, and follow-ups around the clock without supervision.",
    },
    {
      number: 100,
      suffix: "%",
      title: "Human-in-the-Loop Control",
      description: "Live WebSocket telemetry allows operators to monitor, approve, or reject any action.",
    },
  ];

  const [currentIndex, setCurrentIndex] = useState(testimonials.length);
  const [isAutoPlaying, setIsAutoPlaying] = useState(true);
  const [isTransitioning, setIsTransitioning] = useState(true);
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);
  const [isMounted, setIsMounted] = useState(false);
  const [carouselWidth, setCarouselWidth] = useState(0);
  const carouselTrackRef = useRef<HTMLDivElement>(null);
  const [cardWidth, setCardWidth] = useState(660);
  const gap = 24;

  const resetTimeout = () => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
  };

  useEffect(() => {
    const timer = setTimeout(() => {
      setIsMounted(true);
    }, 0);
    return () => clearTimeout(timer);
  }, []);

  useEffect(() => {
    if (!carouselTrackRef.current) return;
    const observer = new ResizeObserver((entries: ResizeObserverEntry[]) => {
      if (entries[0]) {
        setCarouselWidth(entries[0].contentRect.width);
      }
    });
    observer.observe(carouselTrackRef.current);
    return () => observer.disconnect();
  }, [isMounted]);

  useEffect(() => {
    if (isAutoPlaying && isMounted) {
      resetTimeout();
      timeoutRef.current = setTimeout(() => {
        setIsTransitioning(true);
        setCurrentIndex((prevIndex) => prevIndex + 1);
      }, 5000);
    }
    return () => resetTimeout();
  }, [currentIndex, isAutoPlaying, isMounted]);

  useEffect(() => {
    if (currentIndex >= testimonials.length * 2) {
      const timer = setTimeout(() => {
        setIsTransitioning(false);
        setCurrentIndex(currentIndex % testimonials.length + testimonials.length);
      }, 500);
      return () => clearTimeout(timer);
    }
    if (currentIndex < testimonials.length) {
      const timer = setTimeout(() => {
        setIsTransitioning(false);
        setCurrentIndex(currentIndex + testimonials.length);
      }, 500);
      return () => clearTimeout(timer);
    }
  }, [currentIndex]);

  useEffect(() => {
    const handleResizeWidth = () => {
      const width = window.innerWidth;
      if (width < 640) {
        setCardWidth(width - 48);
      } else if (width < 1024) {
        setCardWidth(500);
      } else {
        setCardWidth(660);
      }
    };
    handleResizeWidth();
    window.addEventListener("resize", handleResizeWidth);
    return () => window.removeEventListener("resize", handleResizeWidth);
  }, []);

  const handleNext = () => {
    setIsAutoPlaying(false);
    setIsTransitioning(true);
    setCurrentIndex((prev) => prev + 1);
  };

  const handlePrev = () => {
    setIsAutoPlaying(false);
    setIsTransitioning(true);
    setCurrentIndex((prev) => prev - 1);
  };

  return (
    <>
      <link rel="preconnect" href="https://fonts.googleapis.com" />
      <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
      <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet" crossOrigin="anonymous" />

      <div className={"flex flex-col w-full " + (className || "")}>
        {/* Metrics Section */}
        <section className="w-full bg-[#F6FDFF] py-16 lg:pt-32 lg:pb-16 overflow-hidden flex justify-center">
          <div className="w-full max-w-[1248px] px-6 lg:px-0 flex flex-col items-center">
            <motion.div
              initial={{ y: 10, opacity: 0 }}
              whileInView={{ y: 0, opacity: 1 }}
              viewport={{ once: true }}
              className="flex items-center gap-2 px-4 py-1.5 rounded-full bg-[#E5F2ED] border border-[#042718]/[0.08]"
            >
              <Sparkles size={14} strokeWidth={3} className="text-[#15803D]" />
              <span className="text-sm font-medium text-[#15803D]">Key Metrics</span>
            </motion.div>

            <motion.h2
              initial="hidden"
              whileInView="visible"
              viewport={{ once: true, margin: "-100px" }}
              variants={{
                hidden: { opacity: 1 },
                visible: {
                  transition: {
                    staggerChildren: 0.015,
                  },
                },
              }}
              className="mt-6 sm:mt-8 w-full max-w-[970px] text-center text-[30px] sm:text-[36px] lg:text-[42px] font-semibold leading-[1.2] sm:leading-[44px] lg:leading-[48px] tracking-[-1.5px] sm:tracking-[-2px]"
            >
              {"Scaling your B2B pipeline, scoring leads efficiently, and making autonomous decisions. Let's conquer your market together."
                .split("")
                .map((char: string, index: number) => (
                  <motion.span
                    key={index}
                    variants={{
                      hidden: { color: "#E4E4E4" },
                      visible: {
                        color: "#042718",
                        transition: { duration: 0.5, ease: "easeOut" as const },
                      },
                    }}
                  >
                    {char}
                  </motion.span>
                ))}
            </motion.h2>

            <div className="mt-12 sm:mt-16 lg:mt-20 flex flex-col sm:flex-row flex-wrap justify-center lg:justify-start items-center sm:items-start gap-10 sm:gap-x-6 lg:gap-[24px] w-full">
              {metrics.map((metric, index: number) => (
                <MetricCard
                  key={index}
                  number={metric.number}
                  suffix={metric.suffix}
                  title={metric.title}
                  description={metric.description}
                  delay={0.2 + index * 0.1}
                />
              ))}
            </div>
          </div>
        </section>

        {/* Testimonial Section */}
        <section className="w-full bg-[#F6FDFF] py-16 lg:pt-16 lg:pb-32 overflow-hidden flex justify-center">
          <div className="w-full max-w-[1440px] flex flex-col items-center overflow-hidden">

            <div className="w-full max-w-[1248px] px-6 lg:px-0 flex flex-col items-center text-center mt-0 mb-16">
              <div className="inline-flex items-center gap-2 px-3 py-0.5 rounded-full bg-[#138E5F]/[0.05] border border-[#138E5F]/10 mb-4">
                <Star className="w-3.5 h-3.5 text-[#138E5F] fill-[#138E5F]" />
                <span className="text-[14px] font-medium text-[#138E5F] tracking-tight">Testimonials</span>
              </div>

              <h2 className="text-[#042718] text-[28px] sm:text-[36px] md:text-[52px] font-semibold leading-tight tracking-tight max-w-[690px] mb-4 lg:mb-6">
                Trusted by teams <i className="text-[rgba(0,0,0,0.40)]">who demand</i> autonomous outreach
              </h2>

              <p className="text-[#042718] opacity-80 text-[16px] md:text-[18px] leading-[24px] md:leading-[28px] max-w-[576px]">
                See how sales leaders are simplifying agent management, scaling pipeline, and making smarter economic decisions with KOE Syndicate.
              </p>
            </div>

            <div ref={carouselTrackRef} className="relative w-full overflow-visible">
              <div className="relative flex justify-start items-center overflow-visible min-h-[400px] md:min-h-[500px]">
                <motion.div
                  className="flex gap-6 items-center flex-nowrap"
                  animate={{
                    x: (carouselWidth / 2) - (cardWidth / 2) - (currentIndex * (cardWidth + gap)),
                  }}
                  transition={isTransitioning ? { type: "spring" as const, stiffness: 300, damping: 30 } : { duration: 0 }}
                >
                  {displayTestimonials.map((item: Testimonial, idx: number) => {
                    const isActive = idx === currentIndex;
                    return (
                      <div
                        key={item.id + "-" + idx}
                        className={
                          "relative flex flex-col items-center shrink-0 rounded-[24px] md:rounded-[30px] transition-all duration-500 overflow-hidden " +
                          "p-[32px] md:p-[48px_48px_40px_48px] " +
                          (isActive
                            ? "border border-[rgba(255,255,255,0.1)] shadow-[0_20px_50px_rgba(4,39,24,0.1)]"
                            : "border border-[rgba(4,39,24,0.08)] bg-[rgba(255,255,255,0.20)]")
                        }
                        style={{ width: cardWidth + "px" }}
                      >
                        {isActive && isMounted && (
                          <div className="absolute inset-0 z-0">
                            <video
                              autoPlay
                              loop
                              muted
                              playsInline
                              className="w-full h-full object-cover"
                            >
                              <source src="https://cdn.jiro.build/Amox/All%20Images/P01-Header-01-BG.mp4" type="video/mp4" />
                            </video>
                            <div className="absolute inset-0 bg-black/20" />
                          </div>
                        )}

                        {isActive && (
                          <div className="absolute bottom-0 left-0 right-0 h-[140px] bg-white/[0.05] backdrop-blur-md z-[5] pointer-events-none [mask-image:linear-gradient(to_top,black_40%,transparent)]" />
                        )}

                        <div className="relative z-10 flex flex-col items-center w-full h-full justify-center">
                          <div className="flex items-center justify-center min-h-[90px] md:min-h-[102px] mb-[48px]">
                            <p
                              className={
                                "font-medium text-center transition-colors duration-500 " +
                                (isActive ? "text-white " : "text-[#042718] ") +
                                (isActive
                                  ? "text-[20px] md:text-[26px] leading-[28px] md:leading-[34px] line-clamp-4"
                                  : "text-[18px] md:text-[22px] leading-[24px] md:leading-[30px] line-clamp-3")
                              }
                            >
                              {"\u201c" + item.text + "\u201d"}
                            </p>
                          </div>

                          <div className="flex flex-col items-center">
                            <div className="w-[48px] h-[48px] rounded-full overflow-hidden mb-[12px] border-2 border-white/20">
                              <img src={item.avatar} alt={item.name} className="w-full h-full object-cover" referrerPolicy="no-referrer" />
                            </div>

                            <p
                              className={
                                "font-medium text-[16px] md:text-[18px] leading-[28px] text-center mb-[4px] transition-colors duration-500 " +
                                (isActive ? "text-white" : "text-[#042718]")
                              }
                            >
                              {item.name}
                            </p>

                            <p
                              className={
                                "text-[12px] md:text-[14px] leading-[20px] text-center transition-colors duration-500 " +
                                (isActive ? "text-white/80" : "text-[#042718] opacity-80")
                              }
                            >
                              {item.role}
                            </p>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </motion.div>
              </div>

              <div className="absolute inset-y-0 left-0 w-[100px] md:w-[180px] z-20 pointer-events-none bg-gradient-to-r from-[#F6FDFF] via-[#F6FDFF]/70 to-transparent" />
              <div className="absolute inset-y-0 right-0 w-[100px] md:w-[180px] z-20 pointer-events-none bg-gradient-to-l from-[#F6FDFF] via-[#F6FDFF]/70 to-transparent" />
            </div>

            <div className="w-full max-w-[1248px] flex items-center justify-center gap-3 mt-12">
              <button
                onClick={() => handlePrev()}
                className="w-[48px] h-[48px] md:w-[60px] md:h-[60px] rounded-full border transition-all duration-300 flex items-center justify-center cursor-pointer border-[rgba(4,39,24,0.08)] bg-white/5 hover:bg-white/20"
              >
                <ArrowLeft className="w-5 h-5 md:w-6 md:h-6 text-[#042718]" />
              </button>
              <button
                onClick={() => handleNext()}
                className="w-[48px] h-[48px] md:w-[60px] md:h-[60px] rounded-full transition-all duration-300 flex items-center justify-center cursor-pointer bg-[#042718] hover:bg-[#042718]/90 shadow-lg"
              >
                <ArrowRight className="w-5 h-5 md:w-6 md:h-6 text-white" />
              </button>
            </div>
          </div>
        </section>
      </div>
    </>
  );
}