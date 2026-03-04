import { useEffect, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useAppStore } from '../store';
import { getPolityDetails } from '../api';
import { EvolutionChart } from './EvolutionChart';
import { OccupationsChart } from './OccupationsChart';
import { IndividualsList } from './IndividualsList';

function formatYear(year: number | null): string {
  if (year === null) return '?';
  if (year < 0) {
    return `${Math.abs(year)} BCE`;
  }
  return `${year} CE`;
}

export function PolityDrawer() {
  const { selectedPolityId, setSelectedPolityId } = useAppStore();
  const drawerRef = useRef<HTMLDivElement>(null);

  const { data: polity } = useQuery({
    queryKey: ['polityDetails', selectedPolityId],
    queryFn: () => (selectedPolityId ? getPolityDetails(selectedPolityId) : Promise.resolve(null)),
    enabled: !!selectedPolityId,
  });

  // Handle click outside to close
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (drawerRef.current && !drawerRef.current.contains(event.target as Node)) {
        // Don't close if clicking on map polities
        const target = event.target as HTMLElement;
        if (target.closest('.maplibregl-canvas')) return;
      }
    };

    if (selectedPolityId) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [selectedPolityId, setSelectedPolityId]);

  // Handle escape key
  useEffect(() => {
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setSelectedPolityId(null);
      }
    };

    if (selectedPolityId) {
      document.addEventListener('keydown', handleEscape);
    }
    return () => document.removeEventListener('keydown', handleEscape);
  }, [selectedPolityId, setSelectedPolityId]);

  const isOpen = !!selectedPolityId;

  return (
    <>
      {/* Backdrop */}
      <div
        className={`fixed inset-0 bg-black/20 transition-opacity duration-300 z-40 ${
          isOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'
        }`}
        onClick={() => setSelectedPolityId(null)}
      />

      {/* Drawer */}
      <div
        ref={drawerRef}
        className={`fixed top-0 right-0 h-full bg-white shadow-2xl z-50 transform transition-transform duration-300 ease-out overflow-hidden flex flex-col
          w-[90vw] md:w-[60vw] lg:w-[50vw] xl:w-[45vw]
          ${isOpen ? 'translate-x-0' : 'translate-x-full'}`}
      >
        {/* Header */}
        <div className="flex items-start justify-between p-4 border-b border-gray-200 bg-white flex-shrink-0">
          <div className="flex-1 min-w-0 pr-4">
            <h2 className="text-xl font-semibold text-gray-900 truncate">{polity?.name ?? 'Loading...'}</h2>
            {polity && (
              <div className="text-sm text-gray-500 mt-1 flex flex-wrap items-center gap-x-3 gap-y-1">
                {polity.type && <span>{polity.type}</span>}
                <span>
                  {formatYear(polity.from_year)} - {formatYear(polity.to_year)}
                </span>
                {polity.wikipedia_url && (
                  <a
                    href={polity.wikipedia_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-600 hover:underline"
                  >
                    Wikipedia
                  </a>
                )}
              </div>
            )}
          </div>
          <button
            onClick={() => setSelectedPolityId(null)}
            className="text-gray-400 hover:text-gray-600 p-2 -mr-2 flex-shrink-0"
            title="Close panel (Esc)"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content - scrollable */}
        <div className="flex-1 overflow-y-auto">
          {/* Evolution Chart */}
          <div className="p-4 border-b border-gray-100">
            <h3 className="text-sm font-medium text-gray-700 mb-2">Evolution</h3>
            <div className="h-48">
              <EvolutionChart />
            </div>
          </div>

          {/* Occupations Chart */}
          <div className="p-4 border-b border-gray-100">
            <h3 className="text-sm font-medium text-gray-700 mb-2">Occupations</h3>
            <div className="h-72">
              <OccupationsChart />
            </div>
          </div>

          {/* Individuals List */}
          <div className="p-4">
            <h3 className="text-sm font-medium text-gray-700 mb-2">Notable Individuals</h3>
            <div className="min-h-[400px]">
              <IndividualsList />
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
