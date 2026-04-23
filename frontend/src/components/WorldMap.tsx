import { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import maplibregl from 'maplibre-gl';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useAppStore } from '../store';
import { getActivePolities, getPolityTopCities, getPolityIndividualsCities } from '../api';
import type { PolityWithGeometry } from '../types';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
import { Toggle } from '@/components/ui/toggle';

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

// Point-in-polygon test using ray casting algorithm
function pointInPolygon(point: [number, number], polygon: number[][]): boolean {
  const [x, y] = point;
  let inside = false;

  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const xi = polygon[i][0], yi = polygon[i][1];
    const xj = polygon[j][0], yj = polygon[j][1];

    if (((yi > y) !== (yj > y)) && (x < (xj - xi) * (y - yi) / (yj - yi) + xi)) {
      inside = !inside;
    }
  }

  return inside;
}

// Check if a point is inside a geometry (Polygon or MultiPolygon)
function pointInGeometry(lon: number, lat: number, geometry: GeoJSON.Geometry): boolean {
  const point: [number, number] = [lon, lat];

  if (geometry.type === 'Polygon') {
    const coords = geometry.coordinates as number[][][];
    // Check outer ring (first ring)
    if (!pointInPolygon(point, coords[0])) return false;
    // Check holes (remaining rings) - point should NOT be in any hole
    for (let i = 1; i < coords.length; i++) {
      if (pointInPolygon(point, coords[i])) return false;
    }
    return true;
  } else if (geometry.type === 'MultiPolygon') {
    const multiCoords = geometry.coordinates as number[][][][];
    // Point should be in at least one polygon
    for (const polygon of multiCoords) {
      if (pointInPolygon(point, polygon[0])) {
        // Check holes
        let inHole = false;
        for (let i = 1; i < polygon.length; i++) {
          if (pointInPolygon(point, polygon[i])) {
            inHole = true;
            break;
          }
        }
        if (!inHole) return true;
      }
    }
    return false;
  }

  return false;
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

const MAP_STYLES: Record<'light' | 'terrain' | 'satellite', maplibregl.StyleSpecification> = {
  light: {
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
  },
  terrain: {
    version: 8,
    sources: {
      'stamen-terrain': {
        type: 'raster',
        tiles: [
          'https://tiles.stadiamaps.com/tiles/stamen_terrain_background/{z}/{x}/{y}.png',
        ],
        tileSize: 256,
        attribution: '',
      },
      'carto-labels': {
        type: 'raster',
        tiles: [
          'https://a.basemaps.cartocdn.com/light_only_labels/{z}/{x}/{y}@2x.png',
          'https://b.basemaps.cartocdn.com/light_only_labels/{z}/{x}/{y}@2x.png',
          'https://c.basemaps.cartocdn.com/light_only_labels/{z}/{x}/{y}@2x.png',
        ],
        tileSize: 256,
        attribution: '',
      },
    },
    layers: [
      {
        id: 'background',
        type: 'background',
        paint: { 'background-color': '#f5f3f0' },
      },
      {
        id: 'stamen-terrain-layer',
        type: 'raster',
        source: 'stamen-terrain',
        minzoom: 0,
        maxzoom: 18,
      },
      {
        id: 'carto-labels-layer',
        type: 'raster',
        source: 'carto-labels',
        minzoom: 0,
        maxzoom: 22,
        paint: {
          'raster-opacity': 0.7,
        },
      },
    ],
  },
  satellite: {
    version: 8,
    sources: {
      'esri-satellite': {
        type: 'raster',
        tiles: [
          'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        ],
        tileSize: 256,
        attribution: '',
      },
      'carto-labels-dark': {
        type: 'raster',
        tiles: [
          'https://a.basemaps.cartocdn.com/dark_only_labels/{z}/{x}/{y}@2x.png',
          'https://b.basemaps.cartocdn.com/dark_only_labels/{z}/{x}/{y}@2x.png',
          'https://c.basemaps.cartocdn.com/dark_only_labels/{z}/{x}/{y}@2x.png',
        ],
        tileSize: 256,
        attribution: '',
      },
    },
    layers: [
      {
        id: 'background',
        type: 'background',
        paint: { 'background-color': '#1a1a2e' },
      },
      {
        id: 'esri-satellite-layer',
        type: 'raster',
        source: 'esri-satellite',
        minzoom: 0,
        maxzoom: 19,
      },
      {
        id: 'carto-labels-dark-layer',
        type: 'raster',
        source: 'carto-labels-dark',
        minzoom: 0,
        maxzoom: 22,
        paint: {
          'raster-opacity': 0.9,
        },
      },
    ],
  },
};

export function WorldMap() {
  const mapContainer = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const [mapReady, setMapReady] = useState(false);
  const [isGlobe, setIsGlobe] = useState(true);
  const queryClient = useQueryClient();

  const { selectedYear, selectedPolityId, setSelectedPolityId, flyToLocation, setFlyToLocation, showCities, setShowCities, dynamicCities, setDynamicCities, setCitiesForPolity, mapStyle, setMapStyle, highlightedCity, setHighlightedCity } = useAppStore();

  const setSelectedPolityIdRef = useRef(setSelectedPolityId);
  setSelectedPolityIdRef.current = setSelectedPolityId;
  const setHighlightedCityRef = useRef(setHighlightedCity);
  setHighlightedCityRef.current = setHighlightedCity;

  // Prefetch cities and individuals data when hovering over a polity
  const prefetchCitiesRef = useRef<(polityId: number) => void>(() => {});
  prefetchCitiesRef.current = useCallback((polityId: number) => {
    // Prefetch static cities
    queryClient.prefetchQuery({
      queryKey: ['polityTopCities', polityId],
      queryFn: () => getPolityTopCities(polityId),
      staleTime: Infinity,
    });
    // Prefetch individuals data for dynamic mode
    queryClient.prefetchQuery({
      queryKey: ['polityIndividualsCities', polityId],
      queryFn: () => getPolityIndividualsCities(polityId),
      staleTime: Infinity,
    });
  }, [queryClient]);

  // Fetch cities for selected polity (prefetch in background when polity is selected)
  const { data: citiesData } = useQuery({
    queryKey: ['polityTopCities', selectedPolityId],
    queryFn: () => getPolityTopCities(selectedPolityId!),
    enabled: !!selectedPolityId, // Only fetch when a polity is selected
    staleTime: Infinity, // Cache forever during session
    gcTime: Infinity, // Keep in cache
  });

  // Fetch individuals-cities data for client-side dynamic computation
  const { data: individualsCitiesData } = useQuery({
    queryKey: ['polityIndividualsCities', selectedPolityId],
    queryFn: () => getPolityIndividualsCities(selectedPolityId!),
    enabled: !!selectedPolityId, // Prefetch when polity is selected
    staleTime: Infinity,
    gcTime: Infinity,
  });

  // Compute dynamic cities client-side (instant, no network request)
  const dynamicCitiesComputed = useMemo(() => {
    if (!dynamicCities || !individualsCitiesData || !citiesData) return null;

    const yearStart = selectedYear - 12;
    const yearEnd = selectedYear + 12;

    // Count individuals per city in the year range
    const cityCounts: Record<string, number> = {};
    for (const ind of individualsCitiesData.individuals) {
      if (ind.y >= yearStart && ind.y <= yearEnd) {
        cityCounts[ind.c] = (cityCounts[ind.c] || 0) + 1;
      }
    }

    // Map to city objects with coordinates (from static cities data)
    const cityMap = new Map(citiesData.cities.map(c => [c.city_id, c]));
    const cities = Object.entries(cityCounts)
      .map(([cityId, count]) => {
        const cityInfo = cityMap.get(cityId);
        if (!cityInfo) return null;
        return {
          city_id: cityId,
          name: cityInfo.name,
          lat: cityInfo.lat,
          lon: cityInfo.lon,
          count,
        };
      })
      .filter((c): c is NonNullable<typeof c> => c !== null)
      .sort((a, b) => b.count - a.count);

    return { cities };
  }, [dynamicCities, individualsCitiesData, citiesData, selectedYear]);

  // Cache cities when they arrive
  useEffect(() => {
    if (citiesData && selectedPolityId) {
      setCitiesForPolity(selectedPolityId, citiesData.cities);
    }
  }, [citiesData, selectedPolityId, setCitiesForPolity]);

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
      style: MAP_STYLES.light,
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

      // Add source for cities
      mapInstance.addSource('cities', {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] },
      });

      // Add circle layer for cities
      // Size based on normalized size (1-10), visibility based on zoom level
      mapInstance.addLayer({
        id: 'cities-circles',
        type: 'circle',
        source: 'cities',
        paint: {
          'circle-color': '#dc2626',
          'circle-opacity': 0.85,
          'circle-stroke-color': '#ffffff',
          'circle-stroke-width': 1,
          // Size based on normalized size (1-10) and zoom level
          'circle-radius': [
            'interpolate',
            ['linear'],
            ['zoom'],
            3, ['interpolate', ['linear'], ['get', 'size'], 1, 3, 5, 5, 10, 10],
            6, ['interpolate', ['linear'], ['get', 'size'], 1, 4, 5, 8, 10, 14],
            10, ['interpolate', ['linear'], ['get', 'size'], 1, 5, 5, 10, 10, 20],
          ],
        },
      });

      // Add labels for cities
      // Labels appear based on zoom and normalized size - biggest first, then smaller as you zoom
      mapInstance.addLayer({
        id: 'cities-labels',
        type: 'symbol',
        source: 'cities',
        layout: {
          'text-field': ['get', 'name'],
          'text-size': [
            'interpolate',
            ['linear'],
            ['zoom'],
            3, ['interpolate', ['linear'], ['get', 'size'], 8, 12, 10, 14],
            6, ['interpolate', ['linear'], ['get', 'size'], 5, 13, 10, 16],
            10, 15,
          ],
          'text-font': ['Open Sans Bold', 'Arial Unicode MS Bold'],
          'text-anchor': 'bottom',
          'text-offset': [0, -0.5],
          'text-allow-overlap': false,
          'text-optional': true,
        },
        paint: {
          'text-color': '#7f1d1d',
          'text-halo-color': '#ffffff',
          'text-halo-width': 2,
          // Opacity based on zoom and size - big cities always visible, small ones appear when zooming
          'text-opacity': [
            'interpolate',
            ['linear'],
            ['zoom'],
            3, ['case', ['>=', ['get', 'size'], 8], 1, 0],
            5, ['case', ['>=', ['get', 'size'], 5], 1, 0],
            7, ['case', ['>=', ['get', 'size'], 3], 1, 0],
            9, 1,
          ],
        },
      });

      mapInstance.on('click', 'polities-fill', (e) => {
        if (e.features && e.features.length > 0) {
          const polityId = e.features[0].properties?.id;
          if (polityId) {
            setSelectedPolityIdRef.current(polityId);
            setHighlightedCityRef.current(null);
          }
        }
      });

      mapInstance.on('mouseenter', 'polities-fill', (e) => {
        mapInstance.getCanvas().style.cursor = 'pointer';
        // Prefetch cities for hovered polity
        if (e.features && e.features.length > 0) {
          const polityId = e.features[0].properties?.id;
          if (polityId) {
            prefetchCitiesRef.current(polityId);
          }
        }
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

  // Change base map tiles when style changes
  useEffect(() => {
    if (!map.current || !mapReady) return;

    const m = map.current;
    const firstPolityLayer = m.getLayer('polities-fill') ? 'polities-fill' : undefined;

    // Remove all base map layers and sources (all styles)
    const layersToRemove = ['carto-light-layer', 'stamen-terrain-layer', 'carto-labels-layer', 'esri-satellite-layer', 'carto-labels-dark-layer'];
    const sourcesToRemove = ['carto-light', 'stamen-terrain', 'carto-labels', 'esri-satellite', 'carto-labels-dark'];

    for (const layerId of layersToRemove) {
      if (m.getLayer(layerId)) {
        m.removeLayer(layerId);
      }
    }
    for (const sourceId of sourcesToRemove) {
      if (m.getSource(sourceId)) {
        m.removeSource(sourceId);
      }
    }

    // Add sources and layers for the current style
    const styleSpec = MAP_STYLES[mapStyle];

    // Add all sources
    for (const [sourceId, sourceSpec] of Object.entries(styleSpec.sources)) {
      if (!m.getSource(sourceId)) {
        m.addSource(sourceId, sourceSpec as maplibregl.SourceSpecification);
      }
    }

    // Add all layers (except background) in order, before polities
    for (const layerSpec of styleSpec.layers) {
      if (layerSpec.id !== 'background' && !m.getLayer(layerSpec.id)) {
        m.addLayer(layerSpec as maplibregl.LayerSpecification, firstPolityLayer);
      }
    }
  }, [mapStyle, mapReady]);

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

  // Update cities when polity changes or showCities changes
  // Cities are filtered to only show within the current polity's borders
  // When dynamicCities is enabled, sizes are based on individuals in a 25-year window
  useEffect(() => {
    if (!map.current || !mapReady) return;

    const citiesSource = map.current.getSource('cities') as maplibregl.GeoJSONSource;
    if (!citiesSource) return;

    // If cities are hidden or no polity selected, clear the cities
    if (!showCities || !selectedPolityId || !politiesData) {
      citiesSource.setData({ type: 'FeatureCollection', features: [] });
      return;
    }

    // Choose data source based on dynamic mode
    const cityDataSource = dynamicCities && dynamicCitiesComputed
      ? dynamicCitiesComputed.cities
      : citiesData?.cities;

    if (!cityDataSource) {
      citiesSource.setData({ type: 'FeatureCollection', features: [] });
      return;
    }

    // Get the current polity's geometry at the selected time
    const currentPolity = politiesData.polities.find(
      (p: PolityWithGeometry) => p.id === selectedPolityId
    );

    if (!currentPolity?.geometry) {
      citiesSource.setData({ type: 'FeatureCollection', features: [] });
      return;
    }

    // Filter cities to only those within the current polity's borders
    const citiesInBorders = cityDataSource.filter(city =>
      pointInGeometry(city.lon, city.lat, currentPolity.geometry!)
    );

    if (citiesInBorders.length === 0) {
      citiesSource.setData({ type: 'FeatureCollection', features: [] });
      return;
    }

    // Calculate normalized sizes using log transformation (1-10 range)
    // Based on cities within borders
    const counts = citiesInBorders.map(c => c.count);
    const minCount = Math.min(...counts);
    const maxCount = Math.max(...counts);
    const logMin = Math.log(minCount + 1);
    const logMax = Math.log(maxCount + 1);
    const logRange = logMax - logMin || 1;

    // Convert to GeoJSON features with normalized size
    const cityFeatures = citiesInBorders.map(city => {
      // Log transform and normalize to 1-10 range
      const logValue = Math.log(city.count + 1);
      const normalizedSize = 1 + ((logValue - logMin) / logRange) * 9; // 1 to 10

      return {
        type: 'Feature' as const,
        properties: {
          name: city.name,
          count: city.count,
          size: normalizedSize, // 1-10 normalized size
        },
        geometry: {
          type: 'Point' as const,
          coordinates: [city.lon, city.lat],
        },
      };
    });

    citiesSource.setData({
      type: 'FeatureCollection',
      features: cityFeatures,
    });
  }, [selectedPolityId, showCities, citiesData, mapReady, politiesData, dynamicCities, dynamicCitiesComputed]);

  // Pulse marker for a city picked from search, so the user can spot it
  // amid the other city dots.
  const pulseMarkerRef = useRef<maplibregl.Marker | null>(null);
  useEffect(() => {
    if (!map.current || !mapReady) return;

    if (pulseMarkerRef.current) {
      pulseMarkerRef.current.remove();
      pulseMarkerRef.current = null;
    }
    if (!highlightedCity) return;

    const el = document.createElement('div');
    el.className = 'city-highlight-pulse';
    pulseMarkerRef.current = new maplibregl.Marker({ element: el, anchor: 'center' })
      .setLngLat([highlightedCity.lon, highlightedCity.lat])
      .addTo(map.current);

    return () => {
      if (pulseMarkerRef.current) {
        pulseMarkerRef.current.remove();
        pulseMarkerRef.current = null;
      }
    };
  }, [highlightedCity, mapReady]);

  return (
    <div className="absolute inset-0">
      <div ref={mapContainer} className="absolute inset-0" />
      {/* Unified map controls using shadcn/ui */}
      <div className="absolute top-4 left-4 z-10 flex flex-col gap-2">
        {/* View & Style row */}
        <div className="flex gap-2">
          {/* Globe/Flat toggle */}
          <div className="bg-white/95 backdrop-blur-sm rounded-lg shadow-lg p-1">
            <ToggleGroup
              value={[isGlobe ? 'globe' : 'flat']}
              onValueChange={(value) => {
                const newValue = value[0] || (isGlobe ? 'globe' : 'flat');
                if ((newValue === 'globe') !== isGlobe) toggleGlobe();
              }}
            >
              <ToggleGroupItem value="flat" className="gap-1.5 px-3" title="Flat map projection">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                    d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7"
                  />
                </svg>
                Flat
              </ToggleGroupItem>
              <ToggleGroupItem value="globe" className="gap-1.5 px-3" title="3D globe projection">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                    d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
                Globe
              </ToggleGroupItem>
            </ToggleGroup>
          </div>
          {/* Map style toggle */}
          <div className="bg-white/95 backdrop-blur-sm rounded-lg shadow-lg p-1">
            <ToggleGroup
              value={[mapStyle]}
              onValueChange={(value) => {
                const newValue = value[0] as typeof mapStyle;
                if (newValue) setMapStyle(newValue);
              }}
            >
              <ToggleGroupItem value="light" className="px-2.5" title="Light style">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                    d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"
                  />
                </svg>
              </ToggleGroupItem>
              <ToggleGroupItem value="terrain" className="px-2.5" title="Terrain with mountains">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                    d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
                  />
                </svg>
              </ToggleGroupItem>
              <ToggleGroupItem value="satellite" className="px-2.5" title="Satellite imagery">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                    d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064"
                  />
                </svg>
              </ToggleGroupItem>
            </ToggleGroup>
          </div>
        </div>
        {/* Cities row - only show when polity is selected */}
        {selectedPolityId && (
          <div className="bg-white/95 backdrop-blur-sm rounded-lg shadow-lg p-1 flex gap-1">
            <Toggle
              pressed={showCities}
              onPressedChange={setShowCities}
              className="gap-1.5 px-3"
              title={showCities ? 'Hide cities' : 'Show cities on map'}
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                  d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"
                />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                  d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"
                />
              </svg>
              Cities
            </Toggle>
            <Toggle
              pressed={dynamicCities}
              onPressedChange={setDynamicCities}
              disabled={!showCities}
              className="gap-1.5 px-3"
              title={dynamicCities ? 'Showing 25-year window' : 'Size cities by current year'}
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                {/* City dot at the center, with two concentric rings evoking a
                    time window expanding around it. Outer ring is dashed. */}
                <circle cx="12" cy="12" r="1.5" fill="currentColor" stroke="none" />
                <circle cx="12" cy="12" r="5" strokeWidth={1.5} />
                <circle cx="12" cy="12" r="9" strokeWidth={1.5} strokeDasharray="2 2.5" />
              </svg>
              Dynamic
            </Toggle>
          </div>
        )}
      </div>
      {error && (
        <div className="absolute top-4 left-28 bg-red-50 text-red-700 px-3 py-2 rounded-lg shadow-md text-sm">
          Error: {(error as Error).message}
        </div>
      )}
    </div>
  );
}
