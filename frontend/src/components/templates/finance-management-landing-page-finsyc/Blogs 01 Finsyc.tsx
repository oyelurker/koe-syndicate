"use client";

import React from "react";
import { motion } from "framer-motion";
import { Sparkles } from "lucide-react";

const getTagStyles = (tag: string): string => {
  const t = tag.toLowerCase();
  if (t === "ai") return "bg-[#E0F2FE] text-[#0369A1]";
  if (t === "innovation") return "bg-[#DCFCE7] text-[#15803D]";
  if (t === "tech") return "bg-[#FEF3C7] text-[#B45309]";
  return "bg-[#F4FAFB] text-[#042718]/60";
};

interface BlogCardProps {
  image: string;
  date: string;
  title: string;
  description: string;
  tags: string[];
  imageTop?: boolean;
  delay?: number;
}

function BlogCard({ image, date, title, description, tags, imageTop = true, delay = 0 }: BlogCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, delay }}
      viewport={{ once: true }}
      className="group cursor-pointer flex flex-col items-start bg-white hover:bg-[#F6FDFF] rounded-[24px] overflow-hidden border border-[#042718]/10 shadow-[0_4px_24px_rgba(4,39,24,0.02)] hover:shadow-[0_20px_60px_rgba(4,39,24,0.08)] transition-all duration-500 w-full lg:w-[612px]"
    >
      {imageTop && (
        <div className="w-full h-[300px] md:h-[440px] overflow-hidden">
          <motion.img
            src={image}
            alt={title}
            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-700"
          />
        </div>
      )}

      <div className="flex flex-col p-6 md:p-[40px] gap-4 w-full self-stretch lg:w-[612px]">
        <span className="text-[#042718] font-sans text-base md:text-[18px] leading-[28px] opacity-80">
          {date}
        </span>
        <h3 className="text-[#042718] font-onest text-[28px] md:text-[34px] font-semibold leading-[1.1] md:leading-[38px] tracking-[-1px]">
          {title}
        </h3>
        <p className="text-[#042718] font-sans text-base md:text-[18px] leading-[28px] opacity-80">
          {description}
        </p>
        <div className="flex flex-wrap gap-4">
          {tags.map((tag: string, i: number) => (
            <div
              key={i}
              className={"px-[10px] py-[3px] rounded-[6px] text-center font-sans text-[14px] font-medium leading-[20px] " + getTagStyles(tag)}
            >
              {tag}
            </div>
          ))}
        </div>
      </div>

      {!imageTop && (
        <div className="w-full h-[300px] md:h-[440px] overflow-hidden">
          <motion.img
            src={image}
            alt={title}
            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-700"
          />
        </div>
      )}
    </motion.div>
  );
}

export default function Blog01Finsyc({ className }: { className?: string }) {
  return (
    <>
      <link rel="preconnect" href="https://fonts.googleapis.com" />
      <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
      <link href="https://fonts.googleapis.com/css2?family=Onest:wght@400;500;600;700&display=swap" rel="stylesheet" />

      <section className={"w-full bg-[#FFFFFF] py-16 md:py-[100px] flex justify-center " + (className || "")}>
        <div className="w-full max-w-[1440px] px-6 lg:px-[96px]">
          <div className="w-full max-w-[1248px] mx-auto">
            {/* Header Content */}
            <div className="flex flex-col items-center text-center mb-12 md:mb-[80px]">
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                whileInView={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5 }}
                viewport={{ once: true }}
                className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-[#E4F3EB] border border-[#138E5F]/10 mb-6"
              >
                <Sparkles className="w-3.5 h-3.5 text-[#138E5F]" />
                <span className="text-[#138E5F] text-[13px] font-sans font-medium uppercase tracking-wider">Latest posts</span>
              </motion.div>

              <motion.h2
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, delay: 0.1 }}
                viewport={{ once: true }}
                className="text-[32px] sm:text-[40px] md:text-[52px] font-onest font-semibold text-[#042718] leading-[1.1] md:leading-[58px] tracking-tight md:tracking-[-2px] mb-6 max-w-3xl"
              >
                Insights to help you <span className="italic text-[rgba(4,39,24,0.40)]">scale</span> your outreach
              </motion.h2>

              <motion.p
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, delay: 0.2 }}
                viewport={{ once: true }}
                className="text-[15px] md:text-[18px] text-[#042718] leading-[1.6] md:leading-[28px] max-w-[612px] font-sans opacity-60"
              >
                Learn how to leverage AI agents, GPU acceleration, and Gemini 2.0 to dominate your B2B sales pipeline.
              </motion.p>
            </div>

            {/* Blog Cards Grid */}
            <div className="flex flex-col lg:flex-row gap-6 justify-center">
              <BlogCard
                image="https://cdn.jiro.build/Amox/All%20Images/blogs-img-01.jpg"
                date="19 Feb 2026"
                title="How NVIDIA RAPIDS accelerates lead ingestion by 150x"
                description="Discover how we replaced standard pandas workflows with cuDF to process millions of business records in milliseconds."
                tags={["AI", "Data", "Tech"]}
                imageTop={true}
                delay={0.3}
              />
              <BlogCard
                image="https://cdn.jiro.build/Amox/All%20Images/blogs-img-02.jpg"
                date="13 May 2026"
                title="Building a Human-in-the-Loop SDR Agent with Gemini 2.0"
                description="Explore the architecture behind our autonomous sales reps and how operators maintain complete control via WebSockets."
                tags={["AI", "Innovation", "Engineering"]}
                imageTop={false}
                delay={0.4}
              />
            </div>
          </div>
        </div>
      </section>
    </>
  );
}