import { useQuery } from '@tanstack/react-query';
import { ExternalLink } from 'lucide-react';
import { useAppStore } from '../store';
import { getCitySummary, getCityEvolution } from '../api';
import { CityEvolutionChart } from './CityEvolutionChart';
import { CityIndividualsList } from './CityIndividualsList';

function formatYear(year: number): string {
  if (year < 0) return `${Math.abs(year)} BCE`;
  return `${year} CE`;
}

export function CityPanel() {
  const { selectedCityId, individualsCount } = useAppStore();

  const { data: summary } = useQuery({
    queryKey: ['citySummary', selectedCityId],
    queryFn: () => (selectedCityId ? getCitySummary(selectedCityId) : Promise.resolve(null)),
    enabled: !!selectedCityId,
    staleTime: Infinity,
  });

  // Same query key as CityEvolutionChart — React Query dedupes, so no extra
  // request. We just need the first/last year for the header range.
  const { data: evo } = useQuery({
    queryKey: ['cityEvolution', selectedCityId],
    queryFn: () => (selectedCityId ? getCityEvolution(selectedCityId) : Promise.resolve(null)),
    enabled: !!selectedCityId,
    staleTime: Infinity,
  });
  const yearRange =
    evo && evo.evolution.length > 0
      ? { min: evo.evolution[0].year, max: evo.evolution[evo.evolution.length - 1].year }
      : null;

  if (!selectedCityId) {
    return (
      <div className="py-12 flex items-center justify-center text-gray-400 text-center">
        <div>
          <div className="text-lg mb-2">No city selected</div>
          <div className="text-sm">Click on a red city dot on the map to see details</div>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col bg-gray-100">
      <div className="px-6 pt-4 pb-2 flex-shrink-0">
        <div className="flex items-baseline gap-3 flex-wrap">
          <h2 className="text-xl font-semibold text-gray-900">{summary?.name_en ?? '…'}</h2>
          {yearRange && (
            <span className="text-sm text-gray-400">
              {formatYear(yearRange.min)} – {formatYear(yearRange.max)}
            </span>
          )}
          {summary && (
            <>
              <span className="text-sm text-gray-500">
                {summary.n_individuals.toLocaleString()} individual{summary.n_individuals === 1 ? '' : 's'}
              </span>
              <span className="text-xs text-gray-400">
                · {summary.n_birth.toLocaleString()} born
                · {summary.n_death.toLocaleString()} died
                {summary.n_both > 0 && ` · ${summary.n_both.toLocaleString()} both`}
              </span>
              <a
                href={`https://www.wikidata.org/wiki/${selectedCityId}`}
                target="_blank"
                rel="noopener noreferrer"
                className="text-gray-400 hover:text-gray-600 transition-colors"
                title="Open on Wikidata"
              >
                <ExternalLink className="h-4 w-4" />
              </a>
            </>
          )}
        </div>
      </div>

      <div className="flex-1 flex min-h-0 px-4 pb-4 gap-6">
        <div className="w-[45%] flex flex-col">
          <h3 className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-2 flex-shrink-0">Evolution</h3>
          <div className="flex-1 min-h-0 p-3">
            <CityEvolutionChart />
          </div>
        </div>

        <div className="w-[55%] flex flex-col">
          <h3 className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-2 flex-shrink-0">
            Individuals{individualsCount !== null && ` (${individualsCount.toLocaleString()})`}
          </h3>
          <div className="flex-1 min-h-0 overflow-auto p-3">
            <CityIndividualsList />
          </div>
        </div>
      </div>
    </div>
  );
}
