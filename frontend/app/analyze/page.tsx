"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";
import { streamAnalysis } from "@/lib/api";
import { ReportCard as ReportCardType, MarketEstimate, PersonaContext } from "@/lib/types";
import RufusSimulator from "@/components/RufusSimulator";
import ReportCard from "@/components/ReportCard";
import MarketSizeWidget from "@/components/MarketSizeWidget";
import PersonaBadge from "@/components/PersonaBadge";
import styles from "./page.module.css";

type Status = "profiling" | "extracting" | "simulating" | "done" | "error";

const STATUS_LABELS: Record<Status, string> = {
  profiling: "Analyzing your shopper persona…",
  extracting: "Extracting product data from Amazon…",
  simulating: "Running Rufus simulation…",
  done: "Analysis complete",
  error: "Analysis failed",
};

// 4-step stepper matching the architecture pipeline
const STEPS: { key: Status; label: string }[] = [
  { key: "profiling",  label: "Profile" },
  { key: "extracting", label: "Extract" },
  { key: "simulating", label: "Simulate" },
  { key: "done",       label: "Report" },
];

function ProgressStepper({ status }: { status: Status }) {
  const stepKeys = STEPS.map((s) => s.key);
  const currentIdx = status === "error"
    ? 0
    : Math.max(stepKeys.indexOf(status), 0);

  return (
    <div className={styles.stepper}>
      {STEPS.map((step, i) => (
        <div key={step.key} className={styles.stepperItem}>
          <div
            className={`${styles.stepperDot} ${
              i < currentIdx
                ? styles.stepperDone
                : i === currentIdx
                ? status === "error"
                  ? styles.stepperError
                  : styles.stepperActive
                : styles.stepperPending
            }`}
          >
            {i < currentIdx ? "✓" : i + 1}
          </div>
          <span className={styles.stepperLabel}>{step.label}</span>
          {i < STEPS.length - 1 && (
            <div className={`${styles.stepperLine} ${i < currentIdx ? styles.stepperLineDone : ""}`} />
          )}
        </div>
      ))}
    </div>
  );
}

function AnalyzePage() {
  const params = useSearchParams();
  const router = useRouter();

  const target = params.get("target") ?? "";
  const competitors = params.get("competitors")?.split(",").filter(Boolean) ?? [];
  const query = params.get("query") ?? "";
  const includeMarket = params.get("market") !== "false";
  // Default true: QP routing will force competitor discovery for comparison/planning queries
  const includeCompetitors = params.get("competitors_auto") !== "false";
  const chosenCurrency = params.get("currency") ?? "USD";
  const profileUrl = params.get("profile_url") ?? undefined;

  const [status, setStatus] = useState<Status>("profiling");
  const [persona, setPersona] = useState<PersonaContext | null>(null);
  const [recommendation, setRecommendation] = useState("");
  const [reportCard, setReportCard] = useState<ReportCardType | null>(null);
  const [marketEstimate, setMarketEstimate] = useState<MarketEstimate | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!target || !query) {
      router.push("/");
      return;
    }

    streamAnalysis(
      {
        target_asin: target,
        competitor_asins: competitors,
        query,
        include_market_size: includeMarket,
        include_competitors: includeCompetitors,
        currency: chosenCurrency,
        amazon_profile_url: profileUrl,
      },
      {
        onPersona: (p) => {
          setPersona(p);
          setStatus("extracting");
        },
        onToken: (token) => {
          setStatus("simulating");
          setRecommendation((prev) => prev + token);
        },
        onReportCard: (report) => {
          setReportCard(report);
          setStatus("done");
        },
        onMarketEstimate: (est) => {
          setMarketEstimate(est);
        },
        onError: (err) => {
          setError(err.message);
          setStatus("error");
        },
        onDone: () => {
          setStatus("done");
        },
      }
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <main className={styles.main}>
      <div className={styles.orb1} aria-hidden />
      <div className={styles.orb2} aria-hidden />

      <div className="container">
        {/* Nav */}
        <nav className={styles.nav}>
          <Link href="/" className={styles.logo}>
            <span className={styles.logoR}>R</span>
            <span>ufus Twin</span>
          </Link>
          <Link href="/" className="btn btn-ghost" style={{ fontSize: "0.875rem", padding: "0.5rem 1rem" }}>
            ← New Analysis
          </Link>
        </nav>

        {/* Header */}
        <div className={styles.pageHeader}>
          <div>
            <h1 className={styles.pageTitle}>
              Analysis: <span className="gradient-text">{target}</span>
            </h1>
            <p className={styles.pageQuery}>&ldquo;{query}&rdquo;</p>
          </div>
          <ProgressStepper status={status} />
        </div>

        {/* Status Banner */}
        {status !== "done" && !error && (
          <div className={styles.statusBanner}>
            <div className="pulse-dot" />
            <span>{STATUS_LABELS[status]}</span>
          </div>
        )}

        {error && !reportCard && (
          <div className={styles.errorBanner}>
            <span>⚠️</span>
            <span>{error}</span>
          </div>
        )}

        {error && reportCard && (
          <div className={styles.errorWarning}>
            <span>Note: Analysis finished with minor connection interruption.</span>
          </div>
        )}

        {/* Content grid */}
        <div className={styles.grid}>
          {/* Left column */}
          <div className={styles.leftCol}>
            {/* Persona Badge — appears as soon as persona arrives */}
            {persona && <PersonaBadge persona={persona} />}

            <RufusSimulator
              text={recommendation}
              isStreaming={status === "simulating"}
            />

            {marketEstimate && (
              <MarketSizeWidget estimate={marketEstimate} />
            )}
          </div>

          {/* Right column */}
          <div className={styles.rightCol}>
            {reportCard ? (
              <ReportCard report={reportCard} />
            ) : (
              <div className={styles.reportSkeleton}>
                <div className={styles.skeletonHeader}>
                  <div className="skeleton" style={{ height: "24px", width: "60%", marginBottom: "8px" }} />
                  <div className="skeleton" style={{ height: "110px", width: "110px", borderRadius: "50%" }} />
                </div>
                <div className="skeleton" style={{ height: "1px", margin: "1.5rem 0" }} />
                <div className="skeleton" style={{ height: "14px", width: "80%", marginBottom: "10px" }} />
                <div className="skeleton" style={{ height: "8px", width: "100%", marginBottom: "16px" }} />
                <div className="skeleton" style={{ height: "14px", width: "70%", marginBottom: "10px" }} />
                <div className="skeleton" style={{ height: "8px", width: "100%" }} />
              </div>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}

export default function AnalyzePageWrapper() {
  return (
    <Suspense fallback={<div style={{ color: "white", padding: "2rem" }}>Loading…</div>}>
      <AnalyzePage />
    </Suspense>
  );
}
