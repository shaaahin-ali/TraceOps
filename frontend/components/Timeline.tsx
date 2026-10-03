"use client";

/**
 * Timeline Component
 * ====================
 * Renders the ordered list of investigation events with icons,
 * timestamps, and an animated "active" indicator for live investigations.
 *
 * Extracted from the investigation page for reuse.
 */

import {
  Clock,
  CheckCircle2,
  AlertTriangle,
  Database,
  FileText,
  BarChart2,
  Search,
  Shield,
  Zap,
} from "lucide-react";
import type { InvestigationEvent, InvestigationEventType } from "@/types";

const EVENT_ICONS: Partial<Record<InvestigationEventType, React.ElementType>> = {
  INCIDENT_RECEIVED: Zap,
  INCIDENT_CLASSIFIED: Search,
  PLAN_CREATED: FileText,
  TOOL_CALLED: Database,
  TOOL_RESULT: CheckCircle2,
  EVIDENCE_FOUND: Search,
  HYPOTHESES_GENERATED: BarChart2,
  HYPOTHESIS_TESTED: BarChart2,
  VALIDATION_COMPLETED: CheckCircle2,
  ROOT_CAUSE_RANKED: BarChart2,
  RECOMMENDATION_GENERATED: Shield,
  HUMAN_APPROVAL_REQUIRED: AlertTriangle,
  HUMAN_APPROVED: CheckCircle2,
  REPORT_GENERATED: FileText,
  INVESTIGATION_COMPLETED: CheckCircle2,
  INVESTIGATION_FAILED: AlertTriangle,
};

interface TimelineProps {
  events: InvestigationEvent[];
  isInvestigating: boolean;
}

export function Timeline({ events, isInvestigating }: TimelineProps) {
  if (events.length === 0) {
    return (
      <div className="glass-card p-6 text-center" style={{ color: "var(--text-muted)" }}>
        {isInvestigating ? "Waiting for first event..." : "No events yet"}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {events.map((event, i) => {
        const Icon = EVENT_ICONS[event.event_type as InvestigationEventType] ?? Clock;
        const isLast = i === events.length - 1;
        const isDotActive = isInvestigating && isLast;

        return (
          <div key={event.id} className="timeline-item animate-fade-in">
            <div className={`timeline-dot ${isDotActive ? "active" : "completed"}`}>
              <Icon className="w-2.5 h-2.5 text-white" />
            </div>
            <div className="glass-card p-4 ml-2">
              <div className="flex items-center justify-between mb-1">
                <span
                  className="text-xs font-mono font-medium"
                  style={{ color: "var(--accent-blue)" }}
                >
                  {event.event_type}
                </span>
                <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                  {new Date(event.timestamp).toLocaleTimeString()}
                </span>
              </div>
              {event.summary && (
                <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
                  {event.summary}
                </p>
              )}
              {event.tool_name && (
                <span
                  className="text-xs font-mono mt-1 inline-block px-2 py-0.5 rounded"
                  style={{
                    background: "rgba(59,130,246,0.1)",
                    color: "var(--accent-blue)",
                  }}
                >
                  {event.tool_name}
                </span>
              )}
              {!event.success && (
                <span
                  className="text-xs font-mono mt-1 inline-block px-2 py-0.5 rounded ml-1"
                  style={{
                    background: "rgba(239,68,68,0.1)",
                    color: "#f87171",
                  }}
                >
                  FAILED
                </span>
              )}
            </div>
          </div>
        );
      })}

      {/* Animated "working" indicator while investigating */}
      {isInvestigating && (
        <div className="timeline-item">
          <div className="timeline-dot active">
            <div className="w-2 h-2 bg-blue-400 rounded-full animate-pulse" />
          </div>
          <div className="p-4 ml-2 text-sm" style={{ color: "var(--text-muted)" }}>
            <span className="cursor-blink">Agent working</span>
          </div>
        </div>
      )}
    </div>
  );
}
