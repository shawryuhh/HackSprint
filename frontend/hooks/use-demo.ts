"use client";
import { useEffect, useState, useRef, useCallback } from "react";
import { demoSteps } from "@/types";
import { demoService } from "@/lib/api";
import { useResponse } from "@/state/response-context";
export function useDemo() {
  const { data, act, select } = useResponse();
  const [running, setRunning] = useState(false);
  const generation = useRef(0);
  const index = data?.demoIndex ?? 0;
  const waiting = index === 5 || index === 9;
  const stop = useCallback(() => { generation.current++; setRunning(false); }, []);
  const start = async () => { stop(); const ok = await act(() => demoService.reset(true)); if (ok) { select("INC-1042"); setRunning(true); } };
  const reset = async (forRun = false) => { stop(); await act(() => demoService.reset(forRun)); select("INC-1042"); };
  useEffect(() => {
    if (!running || !data) return;
    if (index >= demoSteps.length || data.scenario !== "normal" || data.recommendations.some(r => r.incident === "INC-1042" && r.state === "rejected")) { setRunning(false); return; }
    if (waiting) return; // Human approval is never automated, even in Run Demo.
    const current = generation.current;
    const timeout = setTimeout(async () => {
      if (current !== generation.current) return;
      const ok = await act(() => demoService.step(demoSteps[index]));
      if (!ok) setRunning(false);
    }, index === 6 || index === 10 ? 3600 : 1900);
    return () => clearTimeout(timeout);
  }, [running, index, data, act, waiting]);
  useEffect(() => () => { generation.current++; }, []);
  return { running, waiting: running && waiting, start, stop, reset, complete: index === demoSteps.length };
}
