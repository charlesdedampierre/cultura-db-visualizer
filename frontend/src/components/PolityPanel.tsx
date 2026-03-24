import { useQuery } from '@tanstack/react-query';
import { ExternalLink } from 'lucide-react';
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
      {/* Clean Header - no borders */}
      <div className="px-6 pt-4 pb-2 flex-shrink-0">
        <div className="flex items-baseline gap-3">
          <h2 className="text-xl font-semibold text-gray-900">{polity?.name ?? ''}</h2>
          {polity && (
            <>
              <span className="text-sm text-gray-400">
                {formatYear(polity.from_year)} – {formatYear(polity.to_year)}
              </span>
              {polity.wikipedia_url && (
                <a
                  href={polity.wikipedia_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-gray-400 hover:text-gray-600 transition-colors"
                >
                  <ExternalLink className="h-4 w-4" />
                </a>
              )}
            </>
          )}
        </div>
      </div>

      {/* Three-column layout with subtle separators */}
      <div className="flex-1 flex min-h-0 px-4 pb-4 gap-6">
        {/* Left: Evolution Chart */}
        <div className="w-[30%] flex flex-col">
          <h3 className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-2 flex-shrink-0">Evolution</h3>
          <div className="flex-1 min-h-0 bg-gray-50/50 rounded-xl p-3">
            <EvolutionChart />
          </div>
        </div>

        {/* Middle: Occupations */}
        <div className="w-[35%] flex flex-col">
          <h3 className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-2 flex-shrink-0">Occupations</h3>
          <div className="flex-1 min-h-0 bg-gray-50/50 rounded-xl p-3">
            <OccupationsChart />
          </div>
        </div>

        {/* Right: Individuals List */}
        <div className="w-[35%] flex flex-col">
          <h3 className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-2 flex-shrink-0">Notable Individuals</h3>
          <div className="flex-1 min-h-0 overflow-auto bg-gray-50/50 rounded-xl p-3">
            <IndividualsList />
          </div>
        </div>
      </div>
    </div>
  );
}
