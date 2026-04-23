import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Search, X, ChevronLeft, ChevronRight } from 'lucide-react';
import { useAppStore } from '../store';
import { getPolityIndividuals } from '../api';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Input } from './ui/input';
import type { Individual } from '../types';

const ITEMS_PER_PAGE = 50;

function formatYear(year: number | null): string {
  if (year === null) return '-';
  if (year < 0) {
    return `${Math.abs(year)} BCE`;
  }
  return `${year} CE`;
}

function truncateText(text: string | null, maxLength: number): string {
  if (!text) return '-';
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength) + '...';
}

export function IndividualsList() {
  const [nameSearch, setNameSearch] = useState('');
  const [submittedSearch, setSubmittedSearch] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(1);

  const {
    selectedPolityId,
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

  // Reset page when filters change
  useEffect(() => {
    setCurrentPage(1);
  }, [submittedSearch, filterOccupation, filterYear, sortField, sortOrder]);

  // Clear search when polity changes
  useEffect(() => {
    setNameSearch('');
    setSubmittedSearch(null);
  }, [selectedPolityId]);

  const handleSearchSubmit = () => {
    const trimmed = nameSearch.trim();
    setSubmittedSearch(trimmed.length >= 2 ? trimmed : null);
    setCurrentPage(1);
  };

  const handleSearchKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSearchSubmit();
    }
  };

  const clearSearch = () => {
    setNameSearch('');
    setSubmittedSearch(null);
  };

  const { data, isLoading, error } = useQuery({
    queryKey: ['polityIndividuals', selectedPolityId, currentPage, sortField, sortOrder, filterYear, filterOccupation, submittedSearch],
    queryFn: () =>
      selectedPolityId
        ? getPolityIndividuals(selectedPolityId, currentPage, ITEMS_PER_PAGE, sortField, sortOrder, filterYear, filterOccupation, submittedSearch)
        : Promise.resolve(null),
    enabled: !!selectedPolityId,
  });

  // Update individuals count in store
  useEffect(() => {
    if (data?.total != null) {
      setIndividualsCount(data.total);
    }
  }, [data?.total, setIndividualsCount]);

  if (!selectedPolityId) {
    return (
      <div className="py-8 text-center text-gray-400">
        Select a polity to view individuals
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="py-8 text-center text-gray-400">
        Loading...
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="py-8 text-center text-red-400">
        Error loading data
      </div>
    );
  }

  const totalPages = Math.ceil(data.total / ITEMS_PER_PAGE);

  const handleSort = (field: 'sitelinks_count' | 'impact_date') => {
    if (sortField === field) {
      toggleSortOrder();
    } else {
      setSortField(field);
    }
  };

  const getSortIndicator = (field: 'sitelinks_count' | 'impact_date') => {
    if (sortField !== field) return null;
    return sortOrder === 'asc' ? ' ↑' : ' ↓';
  };

  return (
    <div className="flex flex-col h-full">
      {/* Active filter indicators */}
      {(filterOccupation || filterYear != null) && (
        <div className="mb-2 flex items-center gap-2 flex-shrink-0 flex-wrap">
          <span className="text-xs text-gray-500">Filtered by:</span>
          {filterYear != null && (
            <Badge
              variant="secondary"
              className="cursor-pointer hover:bg-gray-200"
              onClick={() => setFilterYear(null)}
              title="Click to clear year filter"
            >
              {formatYear(filterYear)}–{formatYear(filterYear + 24)} <X className="ml-1 h-3 w-3" />
            </Badge>
          )}
          {filterOccupation && (
            <Badge
              variant="secondary"
              className="cursor-pointer hover:bg-gray-200"
              onClick={() => setFilterOccupation(null)}
              title="Click to clear occupation filter"
            >
              {filterOccupation} <X className="ml-1 h-3 w-3" />
            </Badge>
          )}
        </div>
      )}

      {/* Search input */}
      <div className="mb-2 flex-shrink-0">
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-gray-400" />
          <Input
            type="text"
            value={nameSearch}
            onChange={(e) => setNameSearch(e.target.value)}
            onKeyDown={handleSearchKeyDown}
            placeholder="Search name + Enter"
            className="h-8 text-xs pl-8 pr-8"
          />
          {(nameSearch || submittedSearch) && (
            <button
              onClick={clearSearch}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Active search indicator */}
      {submittedSearch && (
        <div className="mb-2 text-xs text-gray-900 flex-shrink-0 flex items-center gap-2">
          <span>Searching: "{submittedSearch}"</span>
          {isLoading && (
            <div className="w-3 h-3 border-2 border-gray-900 border-t-transparent rounded-full animate-spin" />
          )}
        </div>
      )}

      {/* Scrollable table */}
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
                Year{getSortIndicator('impact_date')}
              </th>
              <th
                className="text-right px-2 py-1.5 font-medium text-gray-600 cursor-pointer hover:text-gray-900 select-none"
                onClick={() => handleSort('sitelinks_count')}
              >
                Fame{getSortIndicator('sitelinks_count')}
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {data.individuals.map((ind: Individual) => (
              <tr key={ind.wikidata_id} className="hover:bg-gray-50">
                <td className="px-2 py-1">
                  <a
                    href={`https://www.wikidata.org/wiki/${ind.wikidata_id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-gray-900 hover:underline font-medium"
                  >
                    {truncateText(ind.name_en, 25)}
                  </a>
                </td>
                <td className="px-2 py-1 text-gray-800">
                  {truncateText(ind.occupations_en, 30)}
                </td>
                <td className="px-2 py-1 text-right text-gray-600 whitespace-nowrap">
                  {formatYear(ind.impact_date_raw)}
                </td>
                <td className="px-2 py-1 text-right text-gray-600">
                  {ind.sitelinks_count != null ? (ind.sitelinks_count + 1).toLocaleString() : '-'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between pt-2 border-t border-gray-100 flex-shrink-0">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setCurrentPage(Math.max(1, currentPage - 1))}
            disabled={currentPage === 1}
            className="h-7 text-xs"
          >
            <ChevronLeft className="h-3 w-3 mr-1" />
            Previous
          </Button>
          <span className="text-xs text-gray-500">
            Page {currentPage} of {totalPages}
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setCurrentPage(Math.min(totalPages, currentPage + 1))}
            disabled={currentPage === totalPages}
            className="h-7 text-xs"
          >
            Next
            <ChevronRight className="h-3 w-3 ml-1" />
          </Button>
        </div>
      )}
    </div>
  );
}
