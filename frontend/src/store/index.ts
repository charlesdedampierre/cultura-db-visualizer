import { create } from 'zustand';

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

  // Fly to location
  flyToLocation: { lng: number; lat: number; zoom?: number } | null;
  setFlyToLocation: (location: { lng: number; lat: number; zoom?: number } | null) => void;

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

  // Selected polity
  selectedPolityId: null,
  setSelectedPolityId: (id) => set({
    selectedPolityId: id,
    currentPage: 1,
    filterYear: null,
    filterOccupation: null,
  }),

  // Fly to location
  flyToLocation: null,
  setFlyToLocation: (location) => set({ flyToLocation: location }),

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
