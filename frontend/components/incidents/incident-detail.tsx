"use client";
import { useEffect, useState } from "react";
import { MapPin, Languages, Users, ArrowDown, MessageSquareText, HeartHandshake } from "lucide-react";
import { useResponse } from "@/state/response-context";
import { useI18n } from "@/lib/i18n/provider";
import { languages } from "@/lib/i18n/languages";
import { reliefService } from "@/lib/api";
import { ServiceError } from "@/lib/services/contracts";
import type { EmergencyReport } from "@/types";
import { SeverityBadge, StatusBadge, StateMessage } from "@/components/common/ui";
import { RecommendationPanel } from "@/components/recommendations/recommendation-panel";
export function IncidentDetail() {
  const { data, selectedId } = useResponse(); const { t, language } = useI18n();
  const incident = data?.incidents.find(i => i.id === selectedId);
  const plan = data?.recommendations.find(r => r.incident === selectedId);
  const [translated, setTranslated] = useState<EmergencyReport | null>(null); const [translating, setTranslating] = useState(false); const [translationError, setTranslationError] = useState<string | null>(null);
  useEffect(() => { setTranslated(null); setTranslationError(null); setTranslating(false); }, [selectedId, language]);
  if (!incident) return <aside className="panel detail-panel"><StateMessage message="empty.selection" /></aside>;
  const report = incident.reports[0];
  const translation = translated?.id === report.id && translated.translatedLanguage === language ? translated : report.translatedLanguage === language ? report : null;
  const translate = async () => { setTranslating(true); setTranslationError(null); try { const result = await reliefService.translateReport(report, language); setTranslated(result); } catch (err) { setTranslationError(err instanceof ServiceError ? err.key : "error.translation"); } finally { setTranslating(false); } };
  return <aside className="panel detail-panel" aria-label={`${selectedId} ${t("incident.structured")}`}><div className="detail-header"><div><span className="incident-id" dir="ltr">{incident.id}</span><SeverityBadge severity={incident.severity} /></div><h2>{incident.location}</h2><p><MapPin size={13} />{incident.latitude.toFixed(4)}, {incident.longitude.toFixed(4)}<span>·</span>{t(`type.${incident.type}`)}</p><StatusBadge status={incident.status} /></div>
    <section className="report-section"><div className="detail-step"><span>01</span><h3>{t("incident.original")}</h3><MessageSquareText size={16} /></div><blockquote lang={report.originalLanguage} dir={report.originalLanguage === "ur" ? "rtl" : "auto"}>{report.originalText}</blockquote><div className="report-meta"><span>{t("incident.detected")}: {languages.find(l => l.code === report.originalLanguage)?.label}</span><span>{t("incident.duplicates")}: {incident.duplicates}</span></div>{report.originalLanguage !== language && <button className="translate-button" onClick={translate} disabled={translating}><Languages size={14} />{t(translating ? "loading.translation" : "actions.translate")}</button>}{translation?.translatedText && <div className="translated-report"><small>{t("incident.translation")} · {languages.find(l => l.code === translation.translatedLanguage)?.label}</small><p lang={translation.translatedLanguage} dir={translation.translatedLanguage === "ur" ? "rtl" : "auto"}>{translation.translatedText}</p></div>}{translationError && <p className="inline-error" role="alert">{t(translationError)}</p>}</section>
    <div className="detail-connector"><ArrowDown size={13} /></div>
    <section className="structured-section"><div className="detail-step"><span>02</span><h3>{t("incident.structured")}</h3><Users size={16} /></div><dl className="incident-facts"><div><dt>{t("incident.priority")}</dt><dd className={incident.priority >= 90 ? "text-red" : ""}>{incident.priority}<small>/ 100</small></dd></div><div><dt>{t("incident.people")}</dt><dd>{incident.people}</dd></div><div><dt>{t("incident.severity")}</dt><dd>{incident.severity}<small>/ 5</small></dd></div><div><dt>{t("incident.confidence")}</dt><dd>{Math.round(incident.confidence * 100)}<small>%</small></dd></div></dl>{incident.vulnerabilities.length > 0 && <div className="vulnerability"><HeartHandshake size={16} /><div><small>{t("incident.vulnerabilities")}</small>{incident.vulnerabilities.map(v => <strong key={v}>{t(`cap.${v}`)}</strong>)}</div></div>}<div className="needs"><span>{t("incident.needs")}</span>{incident.needs.map(n => <b key={n}>{t(`cap.${n}`)}</b>)}</div></section>
    <div className="detail-connector"><ArrowDown size={13} /></div><RecommendationPanel key={incident.id} incident={incident} plan={plan} />
  </aside>;
}
