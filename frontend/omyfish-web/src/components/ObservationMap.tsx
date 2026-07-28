"use client";

import { useEffect, useRef } from "react";
import type { Observation } from "@/lib/api";

interface Props {
  observations: Observation[];
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type LeafletLib = any;

declare global {
  interface Window {
    L?: LeafletLib;
  }
}

export function ObservationMap({ observations }: Props) {
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInstance = useRef<LeafletLib>(null);

  useEffect(() => {
    if (!mapRef.current || mapInstance.current) return;

    function initMap(L: LeafletLib) {
      if (!mapRef.current) return;
      const map = L.map(mapRef.current).setView([20, 0], 2);
      mapInstance.current = map;

      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      }).addTo(map);

      const located = observations.filter((o) => o.latitude != null && o.longitude != null);
      if (located.length > 0) {
        const bounds: [number, number][] = located.map((o) => [o.latitude!, o.longitude!]);
        located.forEach((o) => {
          L.marker([o.latitude!, o.longitude!])
            .addTo(map)
            .bindPopup(`<b>${o.speciesName}</b><br/>${new Date(o.observedAt).toLocaleDateString()}`);
        });
        map.fitBounds(bounds, { padding: [40, 40], maxZoom: 10 });
      }
    }

    if (window.L) {
      initMap(window.L);
      return;
    }

    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";
    document.head.appendChild(link);

    const script = document.createElement("script");
    script.src = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";
    script.onload = () => initMap(window.L);
    document.body.appendChild(script);

    return () => {
      if (mapInstance.current) {
        mapInstance.current.remove();
        mapInstance.current = null;
      }
    };
  }, [observations]);

  return <div ref={mapRef} className="w-full h-64 rounded-xl overflow-hidden" />;
}
