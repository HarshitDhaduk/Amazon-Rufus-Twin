"use client";

import { ReportCard as ReportCardType } from "@/lib/types";
import styles from "./ReportCard.module.css";

interface Props {
  report: ReportCardType;
}

function scoreColor(score: number): string {
  if (score >= 70) return "var(--accent-emerald)";
  if (score >= 40) return "var(--accent-amber)";
  return "var(--accent-rose)";
}

function scoreBadgeClass(score: number): string {
  if (score >= 70) return "badge badge-success";
  if (score >= 40) return "badge badge-warning";
  return "badge badge-danger";
}

function ScoreRing({ score, size = 120 }: { score: number; size?: number }) {
  const radius = (size - 12) / 2;
  const circumference = 2 * Math.PI * radius;
  const progress = (score / 100) * circumference;
  const color = scoreColor(score);

  return (
    <div className="score-ring" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        {/* Background track */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="rgba(255,255,255,0.06)"
          strokeWidth={6}
        />
        {/* Progress arc */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={6}
          strokeDasharray={`${progress} ${circumference}`}
          strokeLinecap="round"
          style={{ transition: "stroke-dasharray 1s cubic-bezier(0.4, 0, 0.2, 1)" }}
        />
      </svg>
      <div className="score-ring-value">
        <span className="score-num" style={{ color }}>
          {Math.round(score)}
        </span>
        <span className="score-label">/ 100</span>
      </div>
    </div>
  );
}

function SubScore({
  label,
  score,
  notes,
}: {
  label: string;
  score: number;
  notes: string;
}) {
  return (
    <div className={styles.subScore}>
      <div className={styles.subScoreHeader}>
        <span className={styles.subScoreLabel}>{label}</span>
        <span className={scoreBadgeClass(score)}>{Math.round(score)}</span>
      </div>
      <div className={styles.progressBar}>
        <div
          className={styles.progressFill}
          style={{
            width: `${score}%`,
            background: scoreColor(score),
          }}
        />
      </div>
      <p className={styles.subScoreNotes}>{notes}</p>
    </div>
  );
}

export default function ReportCard({ report }: Props) {
  return (
    <div className={`${styles.wrapper} animate-scale-in`}>
      {/* Header */}
      <div className={styles.header}>
        <div>
          <h3 className={styles.title}>AEO Report Card</h3>
          <p className={styles.asin}>ASIN: {report.target_asin}</p>
        </div>
        <ScoreRing score={report.overall_aeo_score} size={110} />
      </div>

      <div className="divider" />

      {/* Sub-scores */}
      <div className={styles.scores}>
        <SubScore
          label="Contextual Completeness"
          score={report.contextual_completeness.score}
          notes={report.contextual_completeness.notes}
        />
        <SubScore
          label="Review Sentiment Alignment"
          score={report.sentiment_alignment.score}
          notes={report.sentiment_alignment.notes}
        />
      </div>

      <div className="divider" />

      {/* Competitive Gap */}
      <div className={styles.section}>
        <h4 className={styles.sectionTitle}>
          <span className={styles.sectionIcon}>⚡</span>
          Competitive Gap Analysis
        </h4>
        {report.competitive_gap.missing_attributes.length > 0 && (
          <div className={styles.missingAttrs}>
            <p className={styles.missingLabel}>Missing from your listing:</p>
            <div className={styles.tagList}>
              {report.competitive_gap.missing_attributes.map((attr, i) => (
                <span key={i} className={`badge badge-danger ${styles.attrTag}`}>
                  {attr}
                </span>
              ))}
            </div>
          </div>
        )}
        {report.competitive_gap.competitor_advantage && (
          <p className={styles.competitorNote}>
            {report.competitive_gap.competitor_advantage}
          </p>
        )}
      </div>

      <div className="divider" />

      {/* Recommended Actions */}
      <div className={styles.section}>
        <h4 className={styles.sectionTitle}>
          <span className={styles.sectionIcon}>🎯</span>
          Recommended Actions
        </h4>
        <ol className={styles.actionList}>
          {report.recommended_actions.map((action, i) => (
            <li key={i} className={styles.actionItem}>
              <span className={styles.actionNum}>{i + 1}</span>
              <span>{action}</span>
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}
