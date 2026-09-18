"use client";
import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import type { DashboardSnapshot } from "@/types";
import { reliefService, demoService } from "@/lib/api";
import { ServiceError } from "@/lib/services/contracts";
interface ResponseContextValue {
  data: DashboardSnapshot | null; loading: boolean; error: string | null; selectedId: string;
  select: (id: string) => void; refresh: () => Promise<void>; busy: boolean;
  act: (fn: () => Promise<void>, success?: string) => Promise<boolean>;
  notice: string | null; dismissNotice: () => void;
}
const ResponseContext = createContext<ResponseContextValue | null>(null);
export function ResponseProvider({ children }: { children: ReactNode }) {
  const [data, setData] = useState<DashboardSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, select] = useState("INC-1042");
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const version = useRef(0); const actionLock = useRef(false);
  const refresh = useCallback(async () => {
    const request = ++version.current;
    try { const result = await reliefService.getDashboard(); if (request !== version.current) return; setData(result); setError(null); }
    catch (err) { if (request === version.current) setError(err instanceof ServiceError ? err.key : "error.api"); }
    finally { if (request === version.current) setLoading(false); }
  }, []);
  useEffect(() => { const unsubscribe = reliefService.subscribe(() => { void refresh(); }); void refresh(); return () => { unsubscribe(); version.current++; }; }, [refresh]);
  useEffect(() => { if (!notice) return; const timeout = setTimeout(() => setNotice(null), 6500); return () => clearTimeout(timeout); }, [notice]);
  const act = useCallback(async (fn: () => Promise<void>, success?: string) => {
    if (actionLock.current) return false;
    actionLock.current = true; setBusy(true);
    try { await fn(); await refresh(); if (success) setNotice(success); return true; }
    catch (err) { setNotice(err instanceof ServiceError ? err.key : "error.api"); return false; }
    finally { actionLock.current = false; setBusy(false); }
  }, [refresh]);
  return <ResponseContext.Provider value={{ data, loading, error, selectedId, select, refresh, busy, act, notice, dismissNotice: () => setNotice(null) }}>{children}</ResponseContext.Provider>;
}
export function useResponse() { const ctx = useContext(ResponseContext); if (!ctx) throw new Error("ResponseProvider missing"); return ctx; }
export async function recoverSimulation() { await demoService.setScenario("normal"); }
