"use client";

import { PersonaContext } from "@/lib/types";
import styles from "./PersonaBadge.module.css";

interface Props {
  persona: PersonaContext;
}

const BUDGET_LABEL: Record<string, string> = {
  budget: "💸 Budget",
  mid: "⚖️ Mid-Range",
  premium: "💎 Premium",
};

const CONCERN_LABEL: Record<string, string> = {
  price: "💰 Price",
  quality: "⭐ Quality",
  speed: "⚡ Speed",
  eco: "🌿 Eco",
};

const DEAL_LABEL: Record<string, string> = {
  "deal-seeker": "🏷️ Deal-Seeker",
  convenience: "🛒 Convenience",
};

const LOYALTY_LABEL: Record<string, string> = {
  loyal: "🔁 Brand Loyal",
  exploratory: "🔍 Exploratory",
};

const QUALITY_LABEL: Record<string, string> = {
  low: "Low",
  medium: "Medium",
  high: "High",
};

export default function PersonaBadge({ persona }: Props) {
  if (persona.is_fallback) {
    return (
      <div className={`${styles.wrapper} ${styles.guestMode} animate-fade-in-up`}>
        <div className={styles.header}>
          <span className={styles.icon}>👤</span>
          <div>
            <p className={styles.title}>Guest Mode</p>
            <p className={styles.subtitle}>No Amazon profile — using neutral analysis</p>
          </div>
          <span className={styles.guestBadge}>No Profile</span>
        </div>
        <p className={styles.guestHint}>
          Add your Amazon profile URL in the form to get a personalized analysis tailored to your shopping habits.
        </p>
      </div>
    );
  }

  const confidencePct = Math.round(persona.confidence_score * 100);

  return (
    <div className={`${styles.wrapper} animate-fade-in-up`}>
      <div className={styles.header}>
        <span className={styles.icon}>👤</span>
        <div>
          <p className={styles.title}>Shopper Profile Detected</p>
          <p className={styles.subtitle}>{persona.region} · {persona.currency} · {confidencePct}% confidence</p>
        </div>
        <span className={styles.liveBadge}>Personalized</span>
      </div>

      <div className={styles.grid}>
        <div className={styles.pill}>
          <span className={styles.pillLabel}>Budget</span>
          <span className={styles.pillValue}>{BUDGET_LABEL[persona.budget_tier] ?? persona.budget_tier}</span>
        </div>
        <div className={styles.pill}>
          <span className={styles.pillLabel}>Priority</span>
          <span className={styles.pillValue}>{CONCERN_LABEL[persona.primary_concern] ?? persona.primary_concern}</span>
        </div>
        <div className={styles.pill}>
          <span className={styles.pillLabel}>Shopping Style</span>
          <span className={styles.pillValue}>{DEAL_LABEL[persona.deal_sensitivity] ?? persona.deal_sensitivity}</span>
        </div>
        <div className={styles.pill}>
          <span className={styles.pillLabel}>Brand Attitude</span>
          <span className={styles.pillValue}>{LOYALTY_LABEL[persona.brand_loyalty] ?? persona.brand_loyalty}</span>
        </div>
        <div className={styles.pill}>
          <span className={styles.pillLabel}>Quality Bar</span>
          <span className={styles.pillValue}>📊 {QUALITY_LABEL[persona.quality_sensitivity] ?? persona.quality_sensitivity}</span>
        </div>
        {persona.category_affinity.length > 0 && (
          <div className={`${styles.pill} ${styles.pillWide}`}>
            <span className={styles.pillLabel}>Category Affinity</span>
            <span className={styles.pillValue}>{persona.category_affinity.slice(0, 3).join(" · ")}</span>
          </div>
        )}
      </div>

      <div className={styles.confidence}>
        <span className={styles.confidenceLabel}>Signal confidence</span>
        <div className={styles.confidenceBar}>
          <div className={styles.confidenceFill} style={{ width: `${confidencePct}%` }} />
        </div>
        <span className={styles.confidencePct}>{confidencePct}%</span>
      </div>
    </div>
  );
}
