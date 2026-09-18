"use client";
import { useEffect, useRef, type ReactNode } from "react";
import { X } from "lucide-react";
import { useI18n } from "@/lib/i18n/provider";
export function Modal({ title, children, close }: { title: string; children: ReactNode; close: () => void }) {
  const ref = useRef<HTMLDialogElement>(null); const { t } = useI18n();
  useEffect(() => { const target = document.activeElement as HTMLElement | null; ref.current?.showModal(); return () => { target?.focus(); }; }, []);
  return <dialog className="modal" ref={ref} aria-labelledby="modal-title" onCancel={e => { e.preventDefault(); close(); }} onClick={e => { if (e.target === ref.current) { const r = ref.current.getBoundingClientRect(); if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) close(); } }}>
    <div className="modal-header"><h2 id="modal-title">{t(title)}</h2><button className="icon-button" onClick={close} aria-label={t("actions.close")}><X size={20} /></button></div>{children}
  </dialog>;
}
