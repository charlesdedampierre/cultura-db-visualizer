import { useEffect, useRef, useState, useCallback } from 'react';
import maplibregl from 'maplibre-gl';
import { useQuery } from '@tanstack/react-query';
import { useAppStore } from '../store';
import { getActivePolities } from '../api';
import type { PolityWithGeometry } from '../types';

const POLITY_COLORS = [
  '#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6',
  '#ec4899', '#06b6d4', '#84cc16', '#f97316', '#6366f1',
];

// Calculate approximate area of a geometry (in square degrees, rough approximation)
function calculateApproximateArea(geometry: GeoJSON.Geometry): number {
  const getPolygonArea = (coords: number[][][]): number => {
    const ring = coords[0];
    if (!ring || ring.length < 3) return 0;

    let area = 0;
    for (let i = 0; i < ring.length - 1; i++) {
      area += ring[i][0] * ring[i + 1][1];
      area -= ring[i + 1][0] * ring[i][1];
    }
    return Math.abs(area / 2);
  };

  if (geometry.type === 'Polygon') {
    return getPolygonArea(geometry.coordinates as number[][][]);
  } else if (geometry.type === 'MultiPolygon') {
    const multiCoords = geometry.coordinates as number[][][][];
    return multiCoords.reduce((total, polygon) => total + getPolygonArea(polygon), 0);
  }
  return 0;
}

// Calculate centroid of a geometry for label placement
function calculateCentroid(geometry: GeoJSON.Geometry): [number, number] | null {
  const getPolygonCentroid = (coords: number[][][]): [number, number] => {
    const ring = coords[0];
    if (!ring || ring.length === 0) return [0, 0];

    let sumX = 0, sumY = 0;
    for (const point of ring) {
      sumX += point[0];
      sumY += point[1];
    }
    return [sumX / ring.length, sumY / ring.length];
  };

  if (geometry.type === 'Polygon') {
    return getPolygonCentroid(geometry.coordinates as number[][][]);
  } else if (geometry.type === 'MultiPolygon') {
    const multiCoords = geometry.coordinates as number[][][][];
    let maxArea = 0;
    let centroid: [number, number] = [0, 0];

    for (const polygon of multiCoords) {
      const area = Math.abs(polygon[0].reduce((sum, point, i, arr) => {
        const next = arr[(i + 1) % arr.length];
        return sum + (point[0] * next[1] - next[0] * point[1]);
      }, 0) / 2);

      if (area > maxArea) {
        maxArea = area;
        centroid = getPolygonCentroid(polygon);
      }
    }
    return centroid;
  }
  return null;
}

const MAP_STYLE: maplibregl.StyleSpecification = {
  version: 8,
  sources: {
    'carto-light': {
      type: 'raster',
      tiles: [
        'https://a.basemaps.cartocdn.com/light_all/{z}/{x}/{y}@2x.png',
        'https://b.basemaps.cartocdn.com/light_all/{z}/{x}/{y}@2x.png',
        'https://c.basemaps.cartocdn.com/light_all/{z}/{x}/{y}@2x.png',
      ],
      tileSize: 256,
      attribution: '',
    },
  },
  layers: [
    {
      id: 'background',
      type: 'background',
      paint: { 'background-color': '#e8e8e8' },
    },
    {
      id: 'carto-light-layer',
      type: 'raster',
      source: 'carto-light',
      minzoom: 0,
      maxzoom: 22,
    },
  ],
};

export function WorldMap() {
  const mapContainer = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const [mapReady, setMapReady] = useState(false);
  const [isGlobe, setIsGlobe] = useState(true);

  const { selectedYear, selectedPolityId, setSelectedPolityId, flyToLocation, setFlyToLocation } = useAppStore();

  const setSelectedPolityIdRef = useRef(setSelectedPolityId);
  setSelectedPolityIdRef.current = setSelectedPolityId;

  // Fetch active polities (always using leaf mode)
  const { data: politiesData, error } = useQuery({
    queryKey: ['activePolities', selectedYear],
    queryFn: () => getActivePolities(selectedYear, 'leaf'),
    staleTime: Infinity, // Never refetch - cache forever during session
    placeholderData: (previousData) => previousData, // Keep showing previous data while loading
  });

  // Initialize map once
  useEffect(() => {
    if (!mapContainer.current || map.current) return;

    const mapInstance = new maplibregl.Map({
      container: mapContainer.current,
      style: MAP_STYLE,
      center: [15, 42], // Centered on Roman Empire (Mediterranean)
      zoom: 3,
      attributionControl: false,
    });

    mapInstance.on('load', () => {
      // Set initial globe projection
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (mapInstance as any).setProjection({ type: 'globe' });

      mapInstance.addSource('polities', {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] },
      });

      mapInstance.addLayer({
        id: 'polities-fill',
        type: 'fill',
        source: 'polities',
        paint: {
          'fill-color': ['get', 'color'],
          'fill-opacity': ['case', ['get', 'selected'], 0.6, 0.3],
        },
      });

      mapInstance.addLayer({
        id: 'polities-outline',
        type: 'line',
        source: 'polities',
        paint: {
          'line-color': ['get', 'color'],
          'line-width': ['case', ['get', 'selected'], 3, 1],
        },
      });

      // Add source for polity labels (point data at centroids)
      mapInstance.addSource('polity-labels', {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] },
      });

      // Add symbol layer for polity names
      // Labels appear based on area: larger polities visible at lower zoom levels
      mapInstance.addLayer({
        id: 'polity-labels',
        type: 'symbol',
        source: 'polity-labels',
        layout: {
          'text-field': ['get', 'name'],
          'text-size': [
            'interpolate',
            ['linear'],
            ['zoom'],
            1, ['case', ['>', ['get', 'area'], 500], 14, 0],
            2, ['case', ['>', ['get', 'area'], 100], 15, ['case', ['>', ['get', 'area'], 500], 15, 0]],
            3, ['case', ['>', ['get', 'area'], 20], 16, 14],
            5, 17,
            7, 18,
          ],
          'text-font': ['Open Sans Bold', 'Arial Unicode MS Bold'],
          'text-anchor': 'center',
          'text-allow-overlap': false,
          'text-ignore-placement': false,
          'text-padding': 3,
          'text-max-width': 10,
        },
        paint: {
          'text-color': '#1f2937',
          'text-halo-color': '#ffffff',
          'text-halo-width': 2,
          'text-opacity': [
            'interpolate',
            ['linear'],
            ['zoom'],
            1, ['case', ['>', ['get', 'area'], 500], 1, 0],
            2, ['case', ['>', ['get', 'area'], 100], 1, 0],
            3, ['case', ['>', ['get', 'area'], 20], 1, 0],
            4, ['case', ['>', ['get', 'area'], 5], 1, 0],
            5, 1,
          ],
        },
      });

      mapInstance.on('click', 'polities-fill', (e) => {
        if (e.features && e.features.length > 0) {
          const polityId = e.features[0].properties?.id;
          if (polityId) {
            setSelectedPolityIdRef.current(polityId);
          }
        }
      });

      mapInstance.on('mouseenter', 'polities-fill', () => {
        mapInstance.getCanvas().style.cursor = 'pointer';
      });
      mapInstance.on('mouseleave', 'polities-fill', () => {
        mapInstance.getCanvas().style.cursor = '';
      });

      setMapReady(true);
    });

    map.current = mapInstance;

    return () => {
      mapInstance.remove();
      map.current = null;
    };
  }, []);

  // Toggle globe projection using setProjection API
  const toggleGlobe = useCallback(() => {
    if (!map.current) return;

    const newIsGlobe = !isGlobe;
    setIsGlobe(newIsGlobe);

    // Use setProjection API directly - no style change needed
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (map.current as any).setProjection(newIsGlobe ? { type: 'globe' } : { type: 'mercator' });
  }, [isGlobe]);

  // Handle fly-to location
  useEffect(() => {
    if (!map.current || !mapReady || !flyToLocation) return;

    map.current.flyTo({
      center: [flyToLocation.lng, flyToLocation.lat],
      zoom: flyToLocation.zoom ?? 5,
      duration: 1500,
    });

    // Clear the flyToLocation after flying
    setFlyToLocation(null);
  }, [flyToLocation, mapReady, setFlyToLocation]);

  // Update polities data when year changes or selection changes
  useEffect(() => {
    if (!map.current || !mapReady || !politiesData) return;

    const politiesWithArea = politiesData.polities
      .filter((polity: PolityWithGeometry) => polity.geometry)
      .map((polity: PolityWithGeometry) => ({
        polity,
        area: calculateApproximateArea(polity.geometry!),
        centroid: calculateCentroid(polity.geometry!),
      }));

    // Create polygon features for fill/outline layers
    const features = politiesWithArea.map(({ polity, area }) => ({
      type: 'Feature' as const,
      properties: {
        id: polity.id,
        name: polity.name,
        color: POLITY_COLORS[polity.id % POLITY_COLORS.length],
        selected: polity.id === selectedPolityId,
        area,
      },
      geometry: polity.geometry!,
    }));

    // Create point features for labels at centroids
    const labelFeatures = politiesWithArea
      .filter(({ centroid }) => centroid !== null)
      .map(({ polity, area, centroid }) => ({
        type: 'Feature' as const,
        properties: {
          id: polity.id,
          name: polity.name,
          area,
        },
        geometry: {
          type: 'Point' as const,
          coordinates: centroid!,
        },
      }));

    const source = map.current.getSource('polities') as maplibregl.GeoJSONSource;
    if (source) {
      source.setData({
        type: 'FeatureCollection',
        features,
      });
    }

    // Update label source
    const labelSource = map.current.getSource('polity-labels') as maplibregl.GeoJSONSource;
    if (labelSource) {
      labelSource.setData({
        type: 'FeatureCollection',
        features: labelFeatures,
      });
    }
  }, [politiesData, selectedPolityId, mapReady]);

  return (
    <div className="absolute inset-0">
      <div ref={mapContainer} className="absolute inset-0" />
      {/* Globe/Flat toggle - segmented control */}
      <div className="absolute top-4 left-4 z-10 bg-white/90 backdrop-blur-sm rounded-full shadow-lg p-1 flex">
        <button
          onClick={() => isGlobe && toggleGlobe()}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium transition-all ${
            !isGlobe
              ? 'bg-gray-900 text-white shadow-sm'
              : 'text-gray-500 hover:text-gray-700'
          }`}
          title="Flat map view"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
              d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7"
            />
          </svg>
          Flat
        </button>
        <button
          onClick={() => !isGlobe && toggleGlobe()}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium transition-all ${
            isGlobe
              ? 'bg-gray-900 text-white shadow-sm'
              : 'text-gray-500 hover:text-gray-700'
          }`}
          title="Globe view"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
              d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
          Globe
        </button>
      </div>
      {error && (
        <div className="absolute top-4 left-28 bg-red-50 text-red-700 px-3 py-2 rounded-lg shadow-md text-sm">
          Error: {(error as Error).message}
        </div>
      )}
    </div>
  );
}
