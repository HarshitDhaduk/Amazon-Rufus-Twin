import AsinForm from "@/components/AsinForm";
import styles from "./page.module.css";

export default function HomePage() {
  return (
    <main className={styles.main}>
      {/* Background glow orbs */}
      <div className={styles.orb1} aria-hidden />
      <div className={styles.orb2} aria-hidden />

      <div className="container">
        {/* Nav */}
        <nav className={styles.nav}>
          <div className={styles.logo}>
            <span className={styles.logoR}>R</span>
            <span>ufus Twin</span>
          </div>
          <span className="badge badge-info">Beta</span>
        </nav>

        {/* Hero */}
        <section className={styles.hero}>
          <div className={`badge badge-info ${styles.heroBadge}`}>
            <span className="pulse-dot" />
            Powered by Claude 3.5 Sonnet
          </div>
          <h1 className={styles.heroTitle}>
            See Your Product Through{" "}
            <span className="gradient-text">Rufus&apos;s Eyes</span>
          </h1>
          <p className={styles.heroSubtitle}>
            The Amazon Rufus AI decides who gets recommended — and why. This tool
            reverse-engineers its logic and shows you exactly what to fix.
          </p>

          {/* Stats row */}
          <div className={styles.stats}>
            {[
              { value: "2 APIs", label: "Data Sources" },
              { value: "Claude", label: "AI Engine" },
              { value: "AEO", label: "Report Card" },
              { value: "~30s", label: "Analysis Time" },
            ].map((stat) => (
              <div key={stat.label} className={styles.stat}>
                <span className={styles.statValue}>{stat.value}</span>
                <span className={styles.statLabel}>{stat.label}</span>
              </div>
            ))}
          </div>
        </section>

        {/* Form card */}
        <section className={styles.formSection}>
          <div className={`card card-elevated ${styles.formCard}`}>
            <div className={styles.formHeader}>
              <h2 className={styles.formTitle}>Start Your Analysis</h2>
              <p className={styles.formSubtitle}>
                Enter your ASIN, up to 3 competitors, and the shopper query to simulate.
              </p>
            </div>
            <AsinForm />
          </div>

          {/* How it works */}
          <div className={styles.steps}>
            {[
              {
                num: "01",
                title: "Extract",
                desc: "Pulls your listing, reviews, Q&A, and BSR from Amazon via Apify.",
              },
              {
                num: "02",
                title: "Simulate",
                desc: "Claude 3.5 Sonnet evaluates your product exactly as Rufus would.",
              },
              {
                num: "03",
                title: "Diagnose",
                desc: "Get a scored AEO report card with specific, actionable fixes.",
              },
            ].map((step) => (
              <div key={step.num} className={styles.step}>
                <span className={styles.stepNum}>{step.num}</span>
                <h3 className={styles.stepTitle}>{step.title}</h3>
                <p className={styles.stepDesc}>{step.desc}</p>
              </div>
            ))}
          </div>
        </section>
      </div>

      {/* Footer */}
      <footer className={styles.footer}>
        <p>Built with Claude 3.5 Sonnet + Apify · Not affiliated with Amazon</p>
      </footer>
    </main>
  );
}
