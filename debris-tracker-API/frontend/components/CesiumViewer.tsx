"use client";

import "cesium/Build/Cesium/Widgets/widgets.css";

import { useEffect, useRef, useState } from "react";
import type { TrackedObject, StateVector, ConjunctionEvent } from "@/types/api";

const TYPE_COLOR: Record<string, string> = {
  ACTIVE_SATELLITE: "#4fd8c4",
  DEBRIS: "#e8874f",
  ROCKET_BODY: "#e8b94f",
  UNKNOWN: "#7c8a99",
};

export interface ObjectMarker {
  object: TrackedObject;
  state: StateVector;
}

interface CesiumViewerProps {
  markers: ObjectMarker[];
  conjunctionMarkers?: { event: ConjunctionEvent; state: StateVector }[];
  trajectoryPoints?: { x_km: number; y_km: number; z_km: number }[] | null;
  onSelect?: (noradId: number | null) => void;
}

export default function CesiumViewer({
  markers,
  conjunctionMarkers = [],
  trajectoryPoints,
  onSelect,
}: CesiumViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<import("cesium").Viewer | null>(null);
  const cesiumRef = useRef<typeof import("cesium") | null>(null);
  const entityMapRef = useRef<Map<string, number>>(new Map());
  const [ready, setReady] = useState(false);

  // one-time viewer init
  useEffect(() => {
    let cancelled = false;

    async function init() {
      if (typeof window === "undefined" || !containerRef.current) return;
      (window as unknown as { CESIUM_BASE_URL: string }).CESIUM_BASE_URL = "/cesium/";
      const Cesium = await import("cesium");
      if (cancelled || !containerRef.current) return;

      const ionToken = process.env.NEXT_PUBLIC_CESIUM_ION_TOKEN;
      if (ionToken) {
        Cesium.Ion.defaultAccessToken = ionToken;
      }

      // Default to Cesium's bundled Natural Earth II imagery -- it ships
      // with the package, needs no network call and no token, and (unlike
      // the public OSM tile server) is fine to use at any volume. When an
      // Ion token is configured, use Ion's default (higher-resolution)
      // imagery instead. Modern Cesium's Viewer takes a `baseLayer`
      // ImageryLayer, not a raw provider -- the provider alone is silently
      // ignored if passed as `imageryProvider`.
      const baseLayer = ionToken
        ? undefined
        : Cesium.ImageryLayer.fromProviderAsync(
            Cesium.TileMapServiceImageryProvider.fromUrl(
              Cesium.buildModuleUrl("Assets/Textures/NaturalEarthII")
            )
          );

      const viewer = new Cesium.Viewer(containerRef.current, {
        baseLayerPicker: false,
        geocoder: false,
        homeButton: false,
        sceneModePicker: false,
        navigationHelpButton: false,
        animation: false,
        timeline: false,
        fullscreenButton: false,
        infoBox: false,
        selectionIndicator: false,
        ...(baseLayer ? { baseLayer } : {}),
      });
      viewer.scene.globe.enableLighting = false;
      if (viewer.scene.skyAtmosphere) {
        viewer.scene.skyAtmosphere.show = true;
      }
      viewer.camera.setView({
        destination: Cesium.Cartesian3.fromDegrees(0, 0, 25_000_000),
      });

      const handler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas);
      handler.setInputAction((movement: { position: import("cesium").Cartesian2 }) => {
        const picked = viewer.scene.pick(movement.position);
        if (Cesium.defined(picked) && picked.id?.id) {
          const noradId = entityMapRef.current.get(picked.id.id);
          onSelect?.(noradId ?? null);
        } else {
          onSelect?.(null);
        }
      }, Cesium.ScreenSpaceEventType.LEFT_CLICK);

      cesiumRef.current = Cesium;
      viewerRef.current = viewer;
      setReady(true);
    }

    init().catch((err) => {
      console.error("CesiumViewer failed to initialize:", err);
    });
    return () => {
      cancelled = true;
      viewerRef.current?.destroy();
      viewerRef.current = null;
    };
  }, [onSelect]);

  // sync object markers
  useEffect(() => {
    const Cesium = cesiumRef.current;
    const viewer = viewerRef.current;
    if (!ready || !Cesium || !viewer) return;

    const group = "object-marker";
    const existing = viewer.entities.values.filter(
      (e) => e.properties?.group?.getValue() === group
    );
    for (const e of existing) viewer.entities.remove(e);
    entityMapRef.current.clear();

    for (const { object, state } of markers) {
      const position = Cesium.Cartesian3.fromDegrees(
        state.longitude_deg ?? 0,
        state.latitude_deg ?? 0,
        (state.altitude_km ?? 0) * 1000
      );
      const entityId = `obj-${object.norad_id}`;
      viewer.entities.add({
        id: entityId,
        position,
        point: {
          pixelSize: object.object_type === "ACTIVE_SATELLITE" ? 7 : 5,
          color: Cesium.Color.fromCssColorString(
            TYPE_COLOR[object.object_type] ?? TYPE_COLOR.UNKNOWN
          ),
          outlineColor: Cesium.Color.BLACK.withAlpha(0.5),
          outlineWidth: 1,
        },
        properties: { group },
      });
      entityMapRef.current.set(entityId, object.norad_id);
    }
  }, [markers, ready]);

  // sync conjunction markers
  useEffect(() => {
    const Cesium = cesiumRef.current;
    const viewer = viewerRef.current;
    if (!ready || !Cesium || !viewer) return;

    const group = "conjunction-marker";
    const existing = viewer.entities.values.filter(
      (e) => e.properties?.group?.getValue() === group
    );
    for (const e of existing) viewer.entities.remove(e);

    for (const { event, state } of conjunctionMarkers) {
      const position = Cesium.Cartesian3.fromDegrees(
        state.longitude_deg ?? 0,
        state.latitude_deg ?? 0,
        (state.altitude_km ?? 0) * 1000
      );
      viewer.entities.add({
        id: `conj-${event.event_id}`,
        position,
        point: {
          pixelSize: 10,
          color: Cesium.Color.fromCssColorString("#e85c5c").withAlpha(0.85),
          outlineColor: Cesium.Color.WHITE,
          outlineWidth: 1,
        },
        properties: { group },
      });
    }
  }, [conjunctionMarkers, ready]);

  // sync selected trajectory
  useEffect(() => {
    const Cesium = cesiumRef.current;
    const viewer = viewerRef.current;
    if (!ready || !Cesium || !viewer) return;

    const trajectoryId = "selected-trajectory";
    const existing = viewer.entities.getById(trajectoryId);
    if (existing) viewer.entities.remove(existing);

    if (trajectoryPoints && trajectoryPoints.length > 1) {
      const positions = trajectoryPoints.map((p) =>
        new Cesium.Cartesian3(p.x_km * 1000, p.y_km * 1000, p.z_km * 1000)
      );
      viewer.entities.add({
        id: trajectoryId,
        polyline: {
          positions,
          width: 2,
          material: Cesium.Color.fromCssColorString("#4fd8c4").withAlpha(0.7),
          // ECI-ish raw coordinates; fine for a short visual trail, not
          // corrected for Earth rotation over the trajectory window.
        },
      });
    }
  }, [trajectoryPoints, ready]);

  return <div ref={containerRef} className="h-full w-full" />;
}
