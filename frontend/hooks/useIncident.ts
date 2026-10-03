/**
 * useIncident — Investigation Data Hook
 * ========================================
 * Fetches and polls all data for an investigation page.
 *
 * - Loads incident + events + hypotheses + evidence + recommendations
 * - Polls every 3 seconds while the investigation is active
 * - Stops polling when investigation reaches a terminal state
 *
 * Usage:
 *   const { data, loading, error, reload } = useIncident(id);
 */

"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { api } from "@/lib/api";
import type { InvestigationData, Incident } from "@/types";

const POLL_INTERVAL_MS = 3000;
const TERMINAL_STATUSES = new Set(["RESOLVED", "CLOSED", "OPEN"]);

export function useIncident(id: string) {
  const [data, setData] = useState<InvestigationData>({
    incident: null,
    events: [],
    hypotheses: [],
    evidence: [],
    recommendations: [],
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  const load = useCallback(async () => {
    try {
      const [incident, events, hypotheses, evidence, recommendations] =
        await Promise.all([
          api.getIncident(id),
          api.getEvents(id),
          api.getHypotheses(id),
          api.getEvidence(id),
          api.getRecommendations(id),
        ]);

      setData({ incident, events, hypotheses, evidence, recommendations });
      setError(null);

      // Stop polling once investigation completes
      if (TERMINAL_STATUSES.has(incident?.status)) {
        stopPolling();
      }
    } catch (e: any) {
      setError(e.message || "Failed to load investigation data");
    } finally {
      setLoading(false);
    }
  }, [id, stopPolling]);

  // Initial load
  useEffect(() => {
    setLoading(true);
    load();
  }, [id, load]);

  // Polling effect — starts when status is INVESTIGATING
  useEffect(() => {
    if (!data.incident) return;
    if (data.incident.status === "INVESTIGATING") {
      // Only start polling if not already polling
      if (!intervalRef.current) {
        intervalRef.current = setInterval(load, POLL_INTERVAL_MS);
      }
    } else {
      stopPolling();
    }
    return stopPolling;
  }, [data.incident?.status, load, stopPolling]);

  return {
    data,
    loading,
    error,
    reload: load,
    isInvestigating: data.incident?.status === "INVESTIGATING",
    isPolling: !!intervalRef.current,
  };
}
