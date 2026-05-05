"use client";

import { useEffect, useState } from "react";
import { MarketEstimate } from "@/lib/types";
import styles from "./MarketSizeWidget.module.css";

interface Props {
  estimate: MarketEstimate;
}

function useCountUp(target: number, duration = 1500) {
  const [value, setValue] = useState(0);

  useEffect(() => {
    const startTime = performance.now();
    function update(now: number) {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);
      // Ease out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      setValue(Math.floor(target * eased));
      if (progress < 1) requestAnimationFrame(update);
      else setValue(target);
    }
    requestAnimationFrame(update);
  }, [target, duration]);

  return value;
}

function formatCurrency(num: number, currencyCode: string, symbol: string): string {
  const symbolMap: Record<string, string> = {
    "USD": "$",
    "INR": "₹",
    "GBP": "£",
    "EUR": "€"
  };
  const effectiveSymbol = symbol || symbolMap[currencyCode] || "$";
  
  if (currencyCode === "INR") {
    if (num >= 10_000_000) return `${effectiveSymbol}${(num / 10_000_000).toFixed(1)} Cr`;
    if (num >= 100_000) return `${effectiveSymbol}${(num / 100_000).toFixed(1)} L`;
    return `${effectiveSymbol}${num.toLocaleString("en-IN")}`;
  }
  
  if (num >= 1_000_000) return `${effectiveSymbol}${(num / 1_000_000).toFixed(1)}M`;
  if (num >= 1_000) return `${effectiveSymbol}${(num / 1_000).toFixed(0)}K`;
  return `${effectiveSymbol}${num.toFixed(0)}`;
}

export default function MarketSizeWidget({ estimate }: Props) {
  const animatedTotal = useCountUp(Math.round(estimate.total_market_revenue));
  const animatedTop10 = useCountUp(Math.round(estimate.top10_revenue));

  const format = (n: number) => formatCurrency(n, estimate.currency, estimate.currency_symbol);

  return (
    <div className={`${styles.wrapper} animate-fade-in-up`}>
      <div className={styles.header}>
        <h3 className={styles.title}>
          📊 Market Size Estimate
        </h3>
        <span className="badge badge-info">{estimate.category}</span>
      </div>

      {/* Big numbers */}
      <div className={styles.metrics}>
        <div className={styles.metric}>
          <span className={styles.metricValue}>{format(animatedTotal)}</span>
          <span className={styles.metricLabel}>Total Market / Month</span>
          <span className={styles.metricNote}>Estimated category revenue</span>
        </div>
        <div className={styles.metricDivider} />
        <div className={styles.metric}>
          <span className={styles.metricValue} style={{ color: "var(--accent-secondary)" }}>
            {format(animatedTop10)}
          </span>
          <span className={styles.metricLabel}>Top 10 Sellers / Month</span>
          <span className={styles.metricNote}>≈{Math.round(100 / estimate.scaling_factor)}% of total</span>
        </div>
      </div>

      {/* Products breakdown */}
      {estimate.products_breakdown.length > 0 && (
        <>
          <div className="divider" />
          <div className={styles.breakdown}>
            <p className={styles.breakdownTitle}>Top sellers by BSR:</p>
            <div className={styles.breakdownList}>
              {estimate.products_breakdown.slice(0, 5).map((p) => (
                <div key={p.asin} className={styles.breakdownRow}>
                  <div className={styles.breakdownLeft}>
                    <span className={styles.breakdownAsin}>{p.asin}</span>
                    <span className={styles.breakdownTitle2}>{p.title}</span>
                  </div>
                  <div className={styles.breakdownRight}>
                    <span className={styles.breakdownRevenue}>
                      {format(p.monthly_revenue)}/mo
                    </span>
                    <span className={styles.breakdownBsr}>BSR #{p.bsr?.toLocaleString()}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </>
      )}

      <p className={styles.disclaimer}>
        Estimates based on BSR-to-sales modeling. Accuracy ±30% vs. commercial tools.
      </p>
    </div>
  );
}
