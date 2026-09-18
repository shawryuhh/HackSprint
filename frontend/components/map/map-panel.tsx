"use client";
import dynamic from "next/dynamic";
import { MapPinned } from "lucide-react";
import { useI18n } from "@/lib/i18n/provider";
import { StateMessage } from "@/components/common/ui";
function MapLoading() { return <StateMessage kind="loading" message="common.loading" />; }
const LeafletMap = dynamic(() => import("./leaflet-map"), { ssr: false, loading: MapLoading });
export function MapPanel() {
  const { t } = useI18n();
  return <section className="panel map-panel"><div className="panel-heading"><h2><MapPinned size={17} />{t("map.title")}</h2><span className="map-sector" dir="ltr">12.9347° N &nbsp; 77.6269° E</span></div><LeafletMap /></section>;
}
