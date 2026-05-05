"use client";

import { useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import styles from "./RufusSimulator.module.css";

interface Props {
  text: string;
  isStreaming: boolean;
}

// Custom renderers: tables get a horizontal-scroll wrapper so they
// don't overflow the narrow left column when the grid is constrained.
const markdownComponents = {
  table: ({ children, ...props }: React.TableHTMLAttributes<HTMLTableElement>) => (
    <div className={styles.tableWrapper}>
      <table {...props}>{children}</table>
    </div>
  ),
};

export default function RufusSimulator({ text, isStreaming }: Props) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [text]);

  return (
    <div className={styles.wrapper}>
      {/* Header bar mimicking Rufus UI */}
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <div className={styles.rufusAvatar}>R</div>
          <div>
            <p className={styles.rufusName}>Rufus Twin</p>
            <p className={styles.rufusSubtitle}>AI Shopping Simulation</p>
          </div>
        </div>
        {isStreaming && (
          <div className={styles.streaming}>
            <div className="pulse-dot" />
            <span>Generating…</span>
          </div>
        )}
      </div>

      <div className="divider" />

      {/* Simulated response */}
      <div className={styles.response}>
        {text ? (
          <div className={styles.responseText}>
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={markdownComponents}
            >
              {text}
            </ReactMarkdown>
            {isStreaming && <span className={styles.cursor}>|</span>}
          </div>
        ) : (
          <div className={styles.skeleton}>
            <div className="skeleton" style={{ height: "16px", width: "90%", marginBottom: "10px" }} />
            <div className="skeleton" style={{ height: "16px", width: "75%", marginBottom: "10px" }} />
            <div className="skeleton" style={{ height: "16px", width: "82%", marginBottom: "10px" }} />
            <div className="skeleton" style={{ height: "16px", width: "60%" }} />
          </div>
        )}
      </div>
      <div ref={endRef} />
    </div>
  );
}
