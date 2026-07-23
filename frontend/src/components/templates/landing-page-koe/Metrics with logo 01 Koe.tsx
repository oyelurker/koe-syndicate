"use client";

import React, { useState, useEffect } from "react";
import { motion, animate } from "framer-motion";
import { ArrowUpRight } from "lucide-react";

function Counter({ value, duration = 2, suffix = "%" }: { value: number; duration?: number; suffix?: string }) {
  const [displayValue, setDisplayValue] = useState(0);

  useEffect(() => {
    const controls = animate(0, value, {
      duration: duration,
      onUpdate: (latest: number) => setDisplayValue(Math.round(latest)),
      ease: "easeOut" as const,
    });
    return () => controls.stop();
  }, [value, duration]);

  return <span>{displayValue}{suffix}</span>;
}

interface FeatureCardProps {
  logo: React.ReactNode;
  brandName: string;
  description: string;
  percentage: number;
  statLabel: string;
  bgColor: string;
  delay?: number;
  suffix?: string;
}

function FeatureCard({
  logo,
  brandName,
  description,
  percentage,
  statLabel,
  bgColor,
  delay = 0,
  suffix = "%",
}: FeatureCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 40 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ duration: 0.8, delay, ease: [0.21, 0.47, 0.32, 0.98] as const }}
      style={{ backgroundColor: bgColor }}
      className="flex w-full lg:w-[400px] p-6 md:p-8 flex-col items-start rounded-[24px]"
    >
      <div className="flex items-center gap-[12px] mb-[20px]">
        <div
          className="h-[36px] flex items-center"
          style={{
            filter: "brightness(0) saturate(100%) invert(11%) sepia(21%) saturate(2304%) hue-rotate(111deg) brightness(91%) contrast(100%)",
          } as React.CSSProperties}
        >
          {logo}
        </div>
      </div>

      <p className="font-sans text-[16px] md:text-[18px] font-medium leading-[24px] md:leading-[28px] text-[#042718] opacity-80 min-h-0 md:min-h-[112px]">
        {description}
      </p>

      <div className="mt-12 md:mt-[80px]">
        <h2 className="font-heading text-[40px] md:text-[52px] font-semibold leading-[46px] md:leading-[58px] tracking-[-1.2px] md:tracking-[-1.8px] text-[#042718]">
          <Counter value={percentage} suffix={suffix} />
        </h2>
        <p className="mt-[12px] md:mt-[16px] font-sans text-[16px] md:text-[18px] font-normal leading-[24px] md:leading-[28px] text-[#042718] opacity-80">
          {statLabel}
        </p>
      </div>
    </motion.div>
  );
}

export default function MetricsWithLogo01Koe({ className }: { className?: string }) {
  const [isHovered, setIsHovered] = useState(false);

  return (
    <>
      <section
        className={"w-full bg-[#F6FDFF] py-20 lg:py-32 flex justify-center " + (className || "")}
      >
        <div className="w-full max-w-[1440px] px-6 lg:px-[96px]">
          <div className="w-full max-w-[1248px] mx-auto">
            {/* Header Row */}
            <div className="flex flex-col md:flex-row md:justify-between md:items-end mb-10 md:mb-[64px] gap-8">
              <motion.h1
                initial={{ opacity: 0, x: -30 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.8, ease: "easeOut" as const }}
                className="max-w-[584px] text-[36px] md:text-[52px] font-heading font-semibold leading-[42px] md:leading-[58px] tracking-[-1.2px] md:tracking-[-1.8px] text-[#042718]"
              >
                Accelerated by industry-leading <i className="text-[rgba(0,0,0,0.40)]">technologies</i>
              </motion.h1>

              <motion.button
                onMouseEnter={() => setIsHovered(true)}
                onMouseLeave={() => setIsHovered(false)}
                initial={{ opacity: 0, x: 30 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true }}
                animate={{
                  paddingLeft: isHovered ? 8 : 20,
                  paddingRight: isHovered ? 20 : 8,
                }}
                transition={{
                  duration: 0.5,
                  ease: [0.22, 1, 0.36, 1] as const,
                  opacity: { duration: 0.8 },
                  x: { duration: 0.8 },
                }}
                whileTap={{ scale: 0.98 }}
                className="flex items-center h-[56px] min-w-fit w-max bg-[#042718] rounded-full group cursor-pointer transition-colors duration-300 hover:bg-[#063b25] overflow-hidden gap-[12px]"
              >
                <motion.div
                  layout="position" 
                  style={{ order: isHovered ? 2 : 1 } as React.CSSProperties}
                  transition={{ type: "spring" as const, stiffness: 400, damping: 35 }}
                  className="font-sans text-[18px] font-medium leading-[28px] text-white whitespace-nowrap"
                >
                  View Demo
                </motion.div>
                <motion.div
                  layout="position" 
                  style={{ order: isHovered ? 1 : 2 } as React.CSSProperties}
                  transition={{ type: "spring" as const, stiffness: 400, damping: 35 }}
                  className="w-[40px] h-[40px] bg-white rounded-full flex items-center justify-center shrink-0"
                >
                  <ArrowUpRight className="w-[16px] h-[16px] text-[#042718]" />
                </motion.div>
              </motion.button>
            </div>

            {/* Cards Grid */}
            <div className="flex flex-col lg:flex-row gap-[24px]">
              <FeatureCard
                delay={0.1}
                bgColor="#D2DDEA"
                brandName="Google Cloud"
                logo={<span className="font-onest font-bold text-2xl tracking-tight text-[#042718]">Google Cloud</span>}
                description="Enterprise-grade infrastructure with BigQuery and Pub/Sub for massively scalable data ingestion and agent orchestration."
                percentage={99}
                suffix="%"
                statLabel="Uptime and reliability for mission-critical operations"
              />
              <FeatureCard
                delay={0.2}
                bgColor="#EBE3D2"
                brandName="NVIDIA RAPIDS"
                logo={<span className="font-onest font-bold text-2xl tracking-tight text-[#042718]">NVIDIA RAPIDS</span>}
                description="Zero-code GPU acceleration for lead processing, utilizing cuDF to handle millions of records in mere milliseconds."
                percentage={150}
                suffix="x"
                statLabel="Faster data processing compared to traditional CPU pandas"
              />
              <FeatureCard
                delay={0.3}
                bgColor="#D4E5CD"
                brandName="Gemini 2.0 Flash"
                logo={<span className="font-onest font-bold text-2xl tracking-tight text-[#042718]">Gemini 2.0 Flash</span>}
                description="State-of-the-art multimodal reasoning for analyzing digital footprints, qualifying leads, and generating hyper-personalized outreach."
                percentage={10}
                suffix="x"
                statLabel="More cost-effective than comparable frontier models"
              />
            </div>
          </div>
        </div>
      </section>
    </>
  );
}
