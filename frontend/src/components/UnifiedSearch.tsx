import { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useAppStore } from '../store';
import { searchPolities, searchCities } from '../api';

interface SearchResult {
  type: 'polity' | 'city';
  name: string;
  id: string | number;
  polityId?: number;
  polityName?: string;
  // For city results: timeline target year (peak_year with fallbacks)
  // and the polity's active window so we can clamp the target inside it.
  cityTargetYear?: number | null;
  polityFromYear?: number | null;
  polityToYear?: number | null;
  lat: number;
  lon: number;
  count?: number;
  fromYear?: number | null;
  toYear?: number | null;
}

function formatYear(year: number | null | undefined): string {
  if (year === null || year === undefined) return '?';
  if (year < 0) return `${Math.abs(year)} BCE`;
  return `${year} CE`;
}

function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => {
      clearTimeout(handler);
    };
  }, [value, delay]);

  return debouncedValue;
}

export function UnifiedSearch() {
  const [query, setQuery] = useState('');
  const [isOpen, setIsOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const { setSelectedPolityId, setFlyToLocation, setSelectedYear, setShowCities, setHighlightedCity } = useAppStore();

  const debouncedQuery = useDebounce(query, 300);

  // Fetch polities from API
  const { data: politiesData, isLoading: isLoadingPolities } = useQuery({
    queryKey: ['politySearch', debouncedQuery],
    queryFn: () => searchPolities(debouncedQuery),
    enabled: debouncedQuery.length >= 2,
    staleTime: 60000,
  });

  // Fetch cities from API
  const { data: citiesData, isLoading: isLoadingCities } = useQuery({
    queryKey: ['citySearch', debouncedQuery],
    queryFn: () => searchCities(debouncedQuery, 10),
    enabled: debouncedQuery.length >= 2,
    staleTime: 60000,
  });

  // Combine polity and city results
  const combinedResults = useMemo<SearchResult[]>(() => {
    const polityResults: SearchResult[] = (politiesData?.results ?? []).map(p => ({
      type: 'polity' as const,
      name: p.name,
      id: p.id,
      lat: p.centroid?.[1] ?? 0,
      lon: p.centroid?.[0] ?? 0,
      fromYear: p.from_year,
      toYear: p.to_year,
    }));

    const cityResults: SearchResult[] = (citiesData?.results ?? []).map(c => ({
      type: 'city' as const,
      name: c.name,
      id: c.city_id,
      polityId: c.polity_id,
      polityName: c.polity_name,
      // Jump the timeline to the city's peak year (most individuals in a 25-year
      // window) so it's prominent in both Dynamic and non-Dynamic modes.
      // Fall back to first_individual_year, then the polity's start year.
      cityTargetYear: c.peak_year ?? c.first_individual_year ?? c.polity_from_year,
      polityFromYear: c.polity_from_year,
      polityToYear: c.polity_to_year,
      lat: c.lat,
      lon: c.lon,
      count: c.count,
    }));

    // Interleave results: polities first (up to 5), then cities (up to 10)
    return [...polityResults.slice(0, 5), ...cityResults.slice(0, 10)];
  }, [politiesData, citiesData]);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target as Node) &&
        inputRef.current &&
        !inputRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSelectPolity = useCallback(
    (result: SearchResult) => {
      setSelectedPolityId(result.id as number);
      if (result.fromYear !== null && result.fromYear !== undefined) {
        setSelectedYear(result.fromYear);
      }
      if (result.lat && result.lon) {
        setFlyToLocation({
          lng: result.lon,
          lat: result.lat,
          zoom: 5,
        });
      }
      setHighlightedCity(null);
      setQuery('');
      setIsOpen(false);
    },
    [setSelectedPolityId, setFlyToLocation, setSelectedYear, setHighlightedCity]
  );

  const handleSelectCity = useCallback(
    (result: SearchResult) => {
      if (result.polityId) {
        setSelectedPolityId(result.polityId);
      }
      // Jump to the city's target year (peak_year with fallbacks), but clamp
      // inside the polity's active range — otherwise the polity isn't
      // rendered at that year and the city dot never appears.
      let targetYear = result.cityTargetYear ?? result.polityFromYear;
      if (targetYear !== null && targetYear !== undefined) {
        if (result.polityFromYear != null && targetYear < result.polityFromYear) {
          targetYear = result.polityFromYear;
        }
        if (result.polityToYear != null && targetYear > result.polityToYear) {
          targetYear = result.polityToYear;
        }
        setSelectedYear(targetYear);
      }
      setShowCities(true);
      setFlyToLocation({
        lng: result.lon,
        lat: result.lat,
        zoom: 8,
      });
      setHighlightedCity({ id: result.id as string, lat: result.lat, lon: result.lon });
      setQuery('');
      setIsOpen(false);
    },
    [setSelectedPolityId, setFlyToLocation, setShowCities, setSelectedYear, setHighlightedCity]
  );

  const handleSelect = useCallback(
    (result: SearchResult) => {
      if (result.type === 'polity') {
        handleSelectPolity(result);
      } else {
        handleSelectCity(result);
      }
    },
    [handleSelectPolity, handleSelectCity]
  );

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      setIsOpen(false);
      inputRef.current?.blur();
    }
  };

  const showDropdown = isOpen && query.length >= 2;
  const isLoading = isLoadingPolities || isLoadingCities;

  return (
    <div className="relative">
      <div className="relative">
        <svg
          className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
          />
        </svg>
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setIsOpen(true);
          }}
          onFocus={() => query.length >= 2 && setIsOpen(true)}
          onKeyDown={handleKeyDown}
          placeholder="Search polities or cities..."
          className="w-56 md:w-72 pl-9 pr-3 py-1.5 text-sm bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
        {isLoading && (
          <div className="absolute right-3 top-1/2 -translate-y-1/2">
            <div className="w-4 h-4 border-2 border-gray-400 border-t-transparent rounded-full animate-spin" />
          </div>
        )}
      </div>

      {showDropdown && (
        <div
          ref={dropdownRef}
          className="absolute top-full left-0 right-0 mt-1 bg-white rounded-lg shadow-lg border border-gray-200 overflow-hidden z-50 max-h-80 overflow-y-auto min-w-[320px]"
        >
          {combinedResults.length === 0 ? (
            <div className="px-4 py-3 text-sm text-gray-500">
              {isLoading ? 'Searching...' : 'No results found'}
            </div>
          ) : (
            <>
              {/* Polity results */}
              {combinedResults.filter(r => r.type === 'polity').length > 0 && (
                <>
                  <div className="px-3 py-1.5 bg-gray-50 text-xs font-semibold text-gray-500 uppercase tracking-wider">
                    Polities
                  </div>
                  {combinedResults.filter(r => r.type === 'polity').map((result) => (
                    <button
                      key={`polity-${result.id}`}
                      onClick={() => handleSelect(result)}
                      className="w-full px-4 py-2 text-left hover:bg-blue-50 transition-colors border-b border-gray-100"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-sm font-medium text-gray-900">{result.name}</span>
                        <span className="text-xs text-gray-400 whitespace-nowrap">
                          {formatYear(result.fromYear)} - {formatYear(result.toYear)}
                        </span>
                      </div>
                    </button>
                  ))}
                </>
              )}

              {/* City results */}
              {combinedResults.filter(r => r.type === 'city').length > 0 && (
                <>
                  <div className="px-3 py-1.5 bg-gray-50 text-xs font-semibold text-gray-500 uppercase tracking-wider">
                    Cities
                  </div>
                  {combinedResults.filter(r => r.type === 'city').map((result, idx) => (
                    <button
                      key={`city-${result.id}-${idx}`}
                      onClick={() => handleSelect(result)}
                      className="w-full px-4 py-2 text-left hover:bg-red-50 transition-colors border-b border-gray-100 last:border-b-0"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-sm font-medium text-gray-900">{result.name}</span>
                        {result.polityName && (
                          <span className="text-xs text-gray-400 whitespace-nowrap truncate max-w-[55%]">
                            {result.polityName}
                          </span>
                        )}
                      </div>
                    </button>
                  ))}
                </>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
