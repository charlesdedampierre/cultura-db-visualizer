import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Search, X, ChevronLeft, ChevronRight } from 'lucide-react';
import { useAppStore } from '../store';
import { getCityIndividuals, type CityIndividual } from '../api';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Input } from './ui/input';

const ITEMS_PER_PAGE = 50;

function formatYear(year: number | null): string {
  if (year === null) return '-';
  if (year < 0) return `${Math.abs(year)} BCE`;
  return `${year} CE`;
}
function truncate(s: string | null, n: number): string {
  if (!s) return '-';
  return s.length <= n ? s : s.slice(0, n) + '…';
}

type LinkFilter = 'any' | 'birth' | 'death';

export function CityIndividualsList() {
  const [nameSearch, setNameSearch] = useState('');
  const [submittedSearch, setSubmittedSearch] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [linkFilter, setLinkFilter] = useState<LinkFilter>('any');

  const {
    selectedCityId,
    sortField,
    sortOrder,
    setSortField,
    toggleSortOrder,
    filterOccupation,
    setFilterOccupation,
    filterYear,
    setFilterYear,
    setIndividualsCount,
  } = useAppStore();

  useEffect(() => {
    setCurrentPage(1);
  }, [submittedSearch, filterOccupation, filterYear, sortField, sortOrder, linkFilter]);

  useEffect(() => {
    setNameSearch('');
    setSubmittedSearch(null);
    setLinkFilter('any');
  }, [selectedCityId]);

  const handleSearchSubmit = () => {
    const trimmed = nameSearch.trim();
    setSubmittedSearch(trimmed.length >= 2 ? trimmed : null);
    setCurrentPage(1);
  };

  const { data, isLoading, error } = useQuery({
    queryKey: ['cityIndividuals', selectedCityId, currentPage, sortField, sortOrder, filterYear, filterOccupation, submittedSearch, linkFilter],
    queryFn: () =>
      selectedCityId
        ? getCityIndividuals(selectedCityId, currentPage, ITEMS_PER_PAGE, sortField, sortOrder, filterYear, filterOccupation, submittedSearch, linkFilter)
        : Promise.resolve(null),
    enabled: !!selectedCityId,
  });

  useEffect(() => {
    if (data?.total != null) setIndividualsCount(data.total);
  }, [data?.total, setIndividualsCount]);

  if (!selectedCityId) return <div className="py-8 text-center text-gray-400">Select a city</div>;
  if (isLoading) return <div className="py-8 text-center text-gray-400">Loading…</div>;
  if (error || !data) return <div className="py-8 text-center text-red-400">Error loading data</div>;

  const totalPages = Math.ceil(data.total / ITEMS_PER_PAGE);
  const handleSort = (f: 'sitelinks_count' | 'impact_date') => {
    if (sortField === f) toggleSortOrder(); else setSortField(f);
  };
  const sortInd = (f: 'sitelinks_count' | 'impact_date') => sortField === f ? (sortOrder === 'asc' ? ' ↑' : ' ↓') : null;

  const linkLabel = (ind: CityIndividual): string | null => {
    if (ind.is_birth && ind.is_death) return '(born, died)';
    if (ind.is_birth) return '(born)';
    if (ind.is_death) return '(died)';
    return null;
  };

  return (
    <div className="flex flex-col h-full">
      {/* Filters */}
      <div className="flex flex-wrap items-center gap-1 mb-2 flex-shrink-0">
        {(['any', 'birth', 'death'] as LinkFilter[]).map((v) => (
          <button
            key={v}
            onClick={() => setLinkFilter(v)}
            className={`text-xs px-2 py-0.5 rounded border transition-colors ${
              linkFilter === v
                ? 'bg-gray-900 text-white border-gray-900'
                : 'bg-white text-gray-700 border-gray-200 hover:bg-gray-50'
            }`}
          >
            {v === 'any' ? 'All' : v === 'birth' ? 'Born here' : 'Died here'}
          </button>
        ))}
      </div>

      {(filterOccupation || filterYear != null) && (
        <div className="mb-2 flex items-center gap-2 flex-shrink-0 flex-wrap">
          <span className="text-xs text-gray-500">Filtered by:</span>
          {filterYear != null && (
            <Badge variant="secondary" className="cursor-pointer hover:bg-gray-200" onClick={() => setFilterYear(null)}>
              {formatYear(filterYear)}–{formatYear(filterYear + 24)} <X className="ml-1 h-3 w-3" />
            </Badge>
          )}
          {filterOccupation && (
            <Badge variant="secondary" className="cursor-pointer hover:bg-gray-200" onClick={() => setFilterOccupation(null)}>
              {filterOccupation} <X className="ml-1 h-3 w-3" />
            </Badge>
          )}
        </div>
      )}

      <div className="mb-2 flex-shrink-0">
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-gray-400" />
          <Input
            type="text"
            value={nameSearch}
            onChange={(e) => setNameSearch(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearchSubmit()}
            placeholder="Search name + Enter"
            className="h-8 text-xs pl-8 pr-8"
          />
          {(nameSearch || submittedSearch) && (
            <button
              onClick={() => { setNameSearch(''); setSubmittedSearch(null); }}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto min-h-0">
        <table className="w-full text-sm">
          <thead className="bg-gray-100 sticky top-0">
            <tr>
              <th className="text-left px-2 py-1.5 font-medium text-gray-600">Name</th>
              <th className="text-left px-2 py-1.5 font-medium text-gray-600">Occupation</th>
              <th
                className="text-right px-2 py-1.5 font-medium text-gray-600 cursor-pointer hover:text-gray-900 select-none"
                onClick={() => handleSort('impact_date')}
              >
                Year{sortInd('impact_date')}
              </th>
              <th
                className="text-right px-2 py-1.5 font-medium text-gray-600 cursor-pointer hover:text-gray-900 select-none"
                onClick={() => handleSort('sitelinks_count')}
              >
                Fame{sortInd('sitelinks_count')}
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {data.individuals.map((ind) => (
              <tr key={ind.wikidata_id} className="hover:bg-gray-50">
                <td className="px-2 py-1">
                  <a
                    href={`https://www.wikidata.org/wiki/${ind.wikidata_id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-gray-900 hover:underline font-medium"
                  >
                    {truncate(ind.name_en, 22)}
                  </a>
                  {linkLabel(ind) && (
                    <span className="ml-1 text-xs text-gray-500">{linkLabel(ind)}</span>
                  )}
                </td>
                <td className="px-2 py-1 text-gray-800">{truncate(ind.occupations_en, 26)}</td>
                <td className="px-2 py-1 text-right text-gray-600 whitespace-nowrap">{formatYear(ind.impact_date_raw)}</td>
                <td className="px-2 py-1 text-right text-gray-600">
                  {ind.sitelinks_count != null ? (ind.sitelinks_count + 1).toLocaleString() : '-'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between pt-2 border-t border-gray-100 flex-shrink-0">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setCurrentPage(Math.max(1, currentPage - 1))}
            disabled={currentPage === 1}
            className="h-7 text-xs"
          >
            <ChevronLeft className="h-3 w-3 mr-1" /> Previous
          </Button>
          <span className="text-xs text-gray-500">Page {currentPage} of {totalPages}</span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setCurrentPage(Math.min(totalPages, currentPage + 1))}
            disabled={currentPage === totalPages}
            className="h-7 text-xs"
          >
            Next <ChevronRight className="h-3 w-3 ml-1" />
          </Button>
        </div>
      )}
    </div>
  );
}
