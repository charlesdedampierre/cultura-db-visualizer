import { create } from 'zustand';

// Type for cities data from API
interface CityFromAPI {
  city_id: string;
  name: string;
  lat: number;
  lon: number;
  count: number;
}

// Cache of cities per polity (polity_id -> cities array)
type CitiesCache = Record<number, CityFromAPI[]>;

interface AppState {
  // Timeline
  selectedYear: number;
  setSelectedYear: (year: number) => void;

  // Hierarchy toggle
  hierarchyMode: 'leaf' | 'aggregate';
  setHierarchyMode: (mode: 'leaf' | 'aggregate') => void;

  // Selected polity
  selectedPolityId: number | null;
  setSelectedPolityId: (id: number | null) => void;

  // Selected city (opens the city panel)
  selectedCityId: string | null;
  setSelectedCityId: (id: string | null) => void;

  // Cities toggle
  showCities: boolean;
  setShowCities: (show: boolean) => void;

  // Dynamic cities toggle (size by year)
  dynamicCities: boolean;
  setDynamicCities: (dynamic: boolean) => void;

  // Map style
  mapStyle: 'light' | 'terrain' | 'satellite';
  setMapStyle: (style: 'light' | 'terrain' | 'satellite') => void;

  // Cities cache (per polity)
  citiesCache: CitiesCache;
  setCitiesForPolity: (polityId: number, cities: CityFromAPI[]) => void;
  getCitiesForPolity: (polityId: number) => CityFromAPI[] | undefined;

  // Fly to location
  flyToLocation: { lng: number; lat: number; zoom?: number } | null;
  setFlyToLocation: (location: { lng: number; lat: number; zoom?: number } | null) => void;

  // Highlighted city (from search) — renders a pulsing marker on the map
  highlightedCity: { id: string; lat: number; lon: number } | null;
  setHighlightedCity: (city: { id: string; lat: number; lon: number } | null) => void;

  // Individuals sorting
  sortField: 'sitelinks_count' | 'impact_date';
  sortOrder: 'asc' | 'desc';
  setSortField: (field: 'sitelinks_count' | 'impact_date') => void;
  toggleSortOrder: () => void;

  // Pagination
  currentPage: number;
  setCurrentPage: (page: number) => void;

  // Filters
  filterYear: number | null;
  setFilterYear: (year: number | null) => void;
  filterOccupation: string | null;
  setFilterOccupation: (occupation: string | null) => void;
  clearFilters: () => void;

  // Individuals count
  individualsCount: number | null;
  setIndividualsCount: (count: number | null) => void;
}

export const useAppStore = create<AppState>((set) => ({
  // Timeline - default to 200 CE (Roman Empire era)
  selectedYear: 200,
  setSelectedYear: (year) => set({ selectedYear: year, currentPage: 1 }),

  // Hierarchy toggle - default to leaf (smaller polities)
  hierarchyMode: 'leaf',
  setHierarchyMode: (mode) => set({
    hierarchyMode: mode,
    selectedPolityId: null,
    currentPage: 1,
    filterYear: null,
    filterOccupation: null,
  }),

  // Selected polity. Opening a (different) polity closes any open city panel
  // and resets list filters. Selecting the city panel itself does NOT clear
  // the current polity — we keep it so city dots stay visible on the map.
  selectedPolityId: null,
  setSelectedPolityId: (id) => set((state) => ({
    selectedPolityId: id,
    selectedCityId: id != null ? null : state.selectedCityId,
    currentPage: 1,
    filterYear: null,
    filterOccupation: null,
  })),

  // Selected city. Leaves the current polity untouched so the map still
  // shows that polity's dots under the open city panel.
  selectedCityId: null,
  setSelectedCityId: (id) => set({
    selectedCityId: id,
    currentPage: 1,
    filterYear: null,
    filterOccupation: null,
  }),

  // Cities toggle
  showCities: false,
  setShowCities: (show) => set({ showCities: show }),

  // Dynamic cities toggle
  dynamicCities: false,
  setDynamicCities: (dynamic) => set({ dynamicCities: dynamic }),

  // Map style
  mapStyle: 'light',
  setMapStyle: (style) => set({ mapStyle: style }),

  // Cities cache
  citiesCache: {},
  setCitiesForPolity: (polityId, cities) => set((state) => ({
    citiesCache: { ...state.citiesCache, [polityId]: cities }
  })),
  getCitiesForPolity: () => {
    // This is a selector, but we'll access it via getState()
    return undefined; // Placeholder - use useAppStore.getState().citiesCache[polityId]
  },

  // Fly to location
  flyToLocation: null,
  setFlyToLocation: (location) => set({ flyToLocation: location }),

  // Highlighted city
  highlightedCity: null,
  setHighlightedCity: (city) => set({ highlightedCity: city }),

  // Individuals sorting
  sortField: 'sitelinks_count',
  sortOrder: 'desc',
  setSortField: (field) => set({ sortField: field, currentPage: 1 }),
  toggleSortOrder: () =>
    set((state) => ({
      sortOrder: state.sortOrder === 'asc' ? 'desc' : 'asc',
      currentPage: 1,
    })),

  // Pagination
  currentPage: 1,
  setCurrentPage: (page) => set({ currentPage: page }),

  // Filters
  filterYear: null,
  setFilterYear: (year) => set((state) => ({
    filterYear: year === null ? null : (state.filterYear === year ? null : year),
    currentPage: 1,
  })),
  filterOccupation: null,
  setFilterOccupation: (occupation) => set((state) => ({
    filterOccupation: occupation === null ? null : (state.filterOccupation === occupation ? null : occupation),
    currentPage: 1,
  })),
  clearFilters: () => set({ filterYear: null, filterOccupation: null, currentPage: 1 }),

  // Individuals count
  individualsCount: null,
  setIndividualsCount: (count) => set({ individualsCount: count }),
}));
