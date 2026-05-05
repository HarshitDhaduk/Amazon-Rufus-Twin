"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import styles from "./AsinForm.module.css";

const ASIN_REGEX = /^[A-Z0-9]{10}$/;

function validateAsin(val: string) {
  return ASIN_REGEX.test(val.trim().toUpperCase());
}

export default function AsinForm() {
  const router = useRouter();
  const [targetAsin, setTargetAsin] = useState("");
  const [competitorAsins, setCompetitorAsins] = useState<string[]>([""]);
  const [query, setQuery] = useState("");
  const [profileUrl, setProfileUrl] = useState("");
  const [includeMarket, setIncludeMarket] = useState(true);
  const [includeCompetitors, setIncludeCompetitors] = useState(true);
  const [currency, setCurrency] = useState("INR");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);

  function addCompetitor() {
    if (competitorAsins.length < 3) {
      setCompetitorAsins([...competitorAsins, ""]);
    }
  }

  function removeCompetitor(idx: number) {
    setCompetitorAsins(competitorAsins.filter((_, i) => i !== idx));
  }

  function updateCompetitor(idx: number, val: string) {
    const updated = [...competitorAsins];
    updated[idx] = val.toUpperCase().trim();
    setCompetitorAsins(updated);
  }

  function validate() {
    const newErrors: Record<string, string> = {};
    if (!validateAsin(targetAsin)) {
      newErrors.targetAsin = "Must be a valid 10-character Amazon ASIN (letters & numbers only).";
    }
    competitorAsins.forEach((asin, i) => {
      if (asin && !validateAsin(asin)) {
        newErrors[`competitor_${i}`] = "Invalid ASIN format.";
      }
    });
    if (query.trim().length < 10) {
      newErrors.query = "Query must be at least 10 characters.";
    }
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!validate()) return;

    setLoading(true);
    const params = new URLSearchParams({
      target: targetAsin.toUpperCase(),
      competitors: competitorAsins.filter(Boolean).join(","),
      query: query.trim(),
      market: String(includeMarket),
      competitors_auto: String(includeCompetitors),
      currency: currency,
    });
    if (profileUrl.trim()) params.set("profile_url", profileUrl.trim());
    router.push(`/analyze?${params.toString()}`);
  }

  return (
    <form className={styles.form} onSubmit={handleSubmit} noValidate>
      {/* Target ASIN */}
      <div className="input-group">
        <label className="input-label" htmlFor="target-asin">
          Your Product ASIN <span className={styles.required}>*</span>
        </label>
        <input
          id="target-asin"
          className={`input ${errors.targetAsin ? styles.inputError : ""}`}
          type="text"
          maxLength={10}
          placeholder="e.g. B08N5WRWNW"
          value={targetAsin}
          onChange={(e) => setTargetAsin(e.target.value.toUpperCase())}
          autoComplete="off"
          spellCheck={false}
        />
        {errors.targetAsin && <p className={styles.errorMsg}>{errors.targetAsin}</p>}
      </div>

      {/* Competitor ASINs */}
      <div className={styles.competitorSection}>
        <div className={styles.competitorHeader}>
          <span className="input-label">Competitor ASINs (optional, max 3)</span>
          {competitorAsins.length < 3 && (
            <button type="button" className={styles.addBtn} onClick={addCompetitor}>
              + Add Competitor
            </button>
          )}
        </div>
        {competitorAsins.map((asin, i) => (
          <div key={i} className={styles.competitorRow}>
            <input
              id={`competitor-${i}`}
              className={`input ${errors[`competitor_${i}`] ? styles.inputError : ""}`}
              type="text"
              maxLength={10}
              placeholder={`Competitor ${i + 1} ASIN`}
              value={asin}
              onChange={(e) => updateCompetitor(i, e.target.value)}
              spellCheck={false}
            />
            <button
              type="button"
              className={styles.removeBtn}
              onClick={() => removeCompetitor(i)}
              aria-label="Remove competitor"
            >
              ×
            </button>
            {errors[`competitor_${i}`] && (
              <p className={styles.errorMsg}>{errors[`competitor_${i}`]}</p>
            )}
          </div>
        ))}
      </div>

      {/* Shopper Query */}
      <div className="input-group">
        <label className="input-label" htmlFor="shopper-query">
          Shopper Query <span className={styles.required}>*</span>
        </label>
        <textarea
          id="shopper-query"
          className={`input ${errors.query ? styles.inputError : ""}`}
          placeholder='e.g. "What is the best magnesium supplement for seniors with sleep issues?"'
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          rows={3}
        />
        {errors.query && <p className={styles.errorMsg}>{errors.query}</p>}
        <p className={styles.hint}>
          Write it exactly as a real Amazon shopper would ask Rufus.
        </p>
      </div>

      {/* Options */}
      <label className={styles.toggle}>
        <input
          type="checkbox"
          checked={includeMarket}
          onChange={(e) => setIncludeMarket(e.target.checked)}
        />
        <span className={styles.toggleLabel}>Include market size estimate</span>
      </label>

      <label className={styles.toggle}>
        <input
          type="checkbox"
          checked={includeCompetitors}
          onChange={(e) => setIncludeCompetitors(e.target.checked)}
        />
        <span className={styles.toggleLabel}>
          Auto-discover &amp; analyze competitors
          <span className={styles.optionalTag}>recommended</span>
        </span>
      </label>

      <div className={styles.currencyGroup}>
        <label className="input-label" htmlFor="currency">
          Display Currency
        </label>
        <select
          id="currency"
          className={styles.currencySelect}
          value={currency}
          onChange={(e) => setCurrency(e.target.value)}
        >
          <option value="INR">INR (₹)</option>
          <option value="USD">USD ($)</option>
          <option value="GBP">GBP (£)</option>
          <option value="EUR">EUR (€)</option>
        </select>
      </div>

      {/* Amazon Profile URL */}
      <div className={styles.currencyGroup}>
        <label className="input-label" htmlFor="profile-url">
          Amazon Profile URL
          <span className={styles.optionalTag}>optional</span>
        </label>
        <input
          id="profile-url"
          className="input"
          type="url"
          placeholder="amazon.com/gp/profile/amzn1.account.XXX…"
          value={profileUrl}
          onChange={(e) => setProfileUrl(e.target.value)}
          spellCheck={false}
        />
        <p className={styles.hint}>
          Provide your public Amazon profile URL to get a personalized, persona-driven analysis.
          Leave blank for <strong>Guest Mode</strong> (neutral analysis).
        </p>
      </div>

      {/* Submit */}
      <button
        id="analyze-btn"
        type="submit"
        className={`btn btn-primary ${styles.submitBtn}`}
        disabled={loading}
      >
        {loading ? (
          <>
            <span className={styles.spinner} /> Launching Analysis…
          </>
        ) : (
          <>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <path d="M5 12h14M12 5l7 7-7 7" />
            </svg>
            Analyze with Rufus Twin
          </>
        )}
      </button>
    </form>
  );
}
