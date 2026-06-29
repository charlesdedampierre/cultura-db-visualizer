import { useQuery } from '@tanstack/react-query';
import { ExternalLink, ChevronUp, X } from 'lucide-react';
import { useAppStore } from '../store';
import { displayPolityName } from '../lib/utils';
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
  const { selectedPolityId, individualsCount, focusedMetaId, setFocusedMetaId, setSelectedPolityId, setCenterOnPolityId } = useAppStore();

  // Clicking a sub-polity drops out of the meta-focus view back to the normal
  // map with that single polity highlighted and centred (BUN-1139 review).
  const selectChildInNormalView = (childId: number) => {
    setFocusedMetaId(null);
    setSelectedPolityId(childId);
    setCenterOnPolityId(childId);
  };

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
    <div className="h-full flex flex-col bg-gray-100">
      {/* Clean Header - no borders */}
      <div className="px-6 pt-4 pb-2 flex-shrink-0">
        {/* Hierarchy navigation (BUN-1139) */}
        {polity && (polity.parent_id != null || focusedMetaId != null || (polity.is_meta && polity.children.length > 0)) && (
          <div className="flex items-center flex-wrap gap-2 mb-2">
            {/* Go up to the meta level when this polity has a parent */}
            {polity.parent_id != null && (
              <button
                onClick={() => setFocusedMetaId(polity.parent_id!)}
                className="inline-flex items-center gap-1 text-xs font-medium text-amber-800 bg-amber-100 hover:bg-amber-200 px-2 py-1 rounded transition-colors"
                title="Show the broader meta level this belongs to"
              >
                <ChevronUp className="h-3.5 w-3.5" />
                Up to {displayPolityName(polity.parent_name)}
              </button>
            )}

            {/* Exit the meta-focus view back to the granular map */}
            {focusedMetaId != null && (
              <button
                onClick={() => setFocusedMetaId(null)}
                className="inline-flex items-center gap-1 text-xs font-medium text-gray-500 hover:text-gray-800 px-1.5 py-1 rounded transition-colors"
                title="Exit the meta view"
              >
                <X className="h-3.5 w-3.5" />
                Exit meta
              </button>
            )}
          </div>
        )}

        <div className="flex items-baseline gap-3">
          <h2 className="text-xl font-semibold text-gray-900">{displayPolityName(polity?.name)}</h2>
          {polity?.is_meta && (
            <span className="text-[10px] font-semibold uppercase tracking-wide text-amber-700 bg-amber-100 px-1.5 py-0.5 rounded self-center">
              Meta
            </span>
          )}
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

        {/* Drill down: granular levels contained in this meta */}
        {polity && polity.is_meta && polity.children.length > 0 && (
          <div className="mt-2 flex items-center flex-wrap gap-1.5">
            <span className="text-xs text-gray-400 mr-1">Contains:</span>
            {polity.children.map((child) => (
              <button
                key={child.id}
                onClick={() => selectChildInNormalView(child.id)}
                className="text-xs text-blue-700 bg-blue-50 hover:bg-blue-100 px-2 py-0.5 rounded transition-colors"
              >
                {displayPolityName(child.name)}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Three-column layout with subtle separators */}
      <div className="flex-1 flex min-h-0 px-4 pb-4 gap-6">
        {/* Left: Evolution Chart */}
        <div className="w-[30%] flex flex-col">
          <h3 className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-2 flex-shrink-0">Evolution</h3>
          <div className="flex-1 min-h-0 p-3">
            <EvolutionChart />
          </div>
        </div>

        {/* Middle: Occupations */}
        <div className="w-[35%] flex flex-col">
          <h3 className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-2 flex-shrink-0">Occupations</h3>
          <div className="flex-1 min-h-0 p-3">
            <OccupationsChart />
          </div>
        </div>

        {/* Right: Individuals List */}
        <div className="w-[35%] flex flex-col">
          <h3 className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-2 flex-shrink-0">
            Notable Individuals{individualsCount !== null && ` (${individualsCount.toLocaleString()})`}
          </h3>
          <div className="flex-1 min-h-0 overflow-auto p-3">
            <IndividualsList />
          </div>
        </div>
      </div>
    </div>
  );
}
