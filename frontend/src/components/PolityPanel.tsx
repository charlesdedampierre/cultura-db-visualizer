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

export function PolityPanel() {
  const { selectedPolityId } = useAppStore();

  const { data: polity } = useQuery({
    queryKey: ['polityDetails', selectedPolityId],
    queryFn: () => (selectedPolityId ? getPolityDetails(selectedPolityId) : Promise.resolve(null)),
    enabled: !!selectedPolityId,
  });

  if (!selectedPolityId) {
    return (
      <div className="py-12 flex items-center justify-center text-gray-400 text-center">
        <div>
          <div className="text-lg mb-2">No polity selected</div>
          <div className="text-sm">Click on a polity on the map to see details</div>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      {/* Compact Header */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-gray-200 flex-shrink-0">
        <div className="flex items-center gap-4">
          <h2 className="text-lg font-semibold text-gray-900">{polity?.name ?? ''}</h2>
          {polity && (
            <div className="text-xs text-gray-500 flex items-center gap-2">
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
      </div>

      {/* Three-column layout for compact view */}
      <div className="flex-1 flex min-h-0">
        {/* Left: Evolution Chart */}
        <div className="w-[30%] p-3 border-r border-gray-200 flex flex-col">
          <h3 className="text-xs font-medium text-gray-700 mb-1 flex-shrink-0">Evolution</h3>
          <div className="flex-1 min-h-0">
            <EvolutionChart />
          </div>
        </div>

        {/* Middle: Occupations */}
        <div className="w-[35%] p-3 border-r border-gray-200 flex flex-col">
          <h3 className="text-xs font-medium text-gray-700 mb-1 flex-shrink-0">Occupations</h3>
          <div className="flex-1 min-h-0">
            <OccupationsChart />
          </div>
        </div>

        {/* Right: Individuals List */}
        <div className="w-[35%] p-3 flex flex-col">
          <h3 className="text-xs font-medium text-gray-700 mb-1 flex-shrink-0">Notable Individuals</h3>
          <div className="flex-1 min-h-0 overflow-auto">
            <IndividualsList />
          </div>
        </div>
      </div>
    </div>
  );
}
