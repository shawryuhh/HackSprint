"use client";
import { createContext, useContext, useEffect, useState, useCallback, type ReactNode } from "react";
import type { Language } from "@/types";
import { languages } from "./languages";
import { translate } from "./catalog";
interface I18nContextValue { language: Language; setLanguage: (language: Language) => void; t: (key: string, params?: Record<string,string|number>) => string; dir: "ltr" | "rtl"; storageError: boolean }
const I18nContext = createContext<I18nContextValue | null>(null);
export function I18nProvider({ children }: { children: ReactNode }) {
  const [language, set] = useState<Language>("en");
  const [storageError, setStorageError] = useState(false);
  useEffect(() => { try { const stored = localStorage.getItem("reliefmesh.language"); if (languages.some(l => l.code === stored)) set(stored as Language); } catch { setStorageError(true); } }, []);
  const dir = language === "ur" ? "rtl" : "ltr";
  useEffect(() => { document.documentElement.lang = language; document.documentElement.dir = dir; }, [language, dir]);
  const setLanguage = useCallback((value: Language) => { set(value); try { localStorage.setItem("reliefmesh.language", value); setStorageError(false); } catch { setStorageError(true); } }, []);
  const t = useCallback((key: string, params?: Record<string,string|number>) => translate(language, key, params), [language]);
  return <I18nContext.Provider value={{ language, setLanguage, t, dir, storageError }}>{children}</I18nContext.Provider>;
}
export function useI18n() { const ctx = useContext(I18nContext); if (!ctx) throw new Error("I18nProvider missing"); return ctx; }
