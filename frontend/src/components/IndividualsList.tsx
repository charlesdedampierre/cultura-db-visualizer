import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useAppStore } from '../store';
import { getPolityIndividuals } from '../api';
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

// Debounce hook
function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => clearTimeout(handler);
  }, [value, delay]);

  return debouncedValue;
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
      {/* Active filter indicator */}
      {filterOccupation && (
        <div className="mb-2 flex items-center gap-2 flex-shrink-0">
          <span className="text-xs text-gray-500">Filtered by:</span>
          <span
            className="bg-green-100 text-green-700 text-xs px-2 py-0.5 rounded cursor-pointer hover:bg-green-200"
            onClick={() => setFilterOccupation(null)}
          >
            {filterOccupation} ✕
          </span>
        </div>
      )}

      {/* Search input */}
      <div className="mb-2 flex-shrink-0 flex gap-1">
        <div className="relative flex-1">
          <svg
            className="absolute left-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            type="text"
            value={nameSearch}
            onChange={(e) => setNameSearch(e.target.value)}
            onKeyDown={handleSearchKeyDown}
            placeholder="Search name + Enter"
            className="w-full text-xs pl-7 pr-7 py-1.5 bg-gray-50 border-0 rounded-md focus:outline-none focus:bg-white transition-colors"
          />
          {(nameSearch || submittedSearch) && (
            <button
              onClick={clearSearch}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>
      </div>
      {/* Active search indicator */}
      {submittedSearch && (
        <div className="mb-2 text-xs text-blue-600 flex-shrink-0 flex items-center gap-2">
          <span>Searching: "{submittedSearch}"</span>
          {isLoading && (
            <div className="w-3 h-3 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
          )}
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between mb-2 flex-shrink-0">
        <span className="text-sm text-gray-500">
          {data.total.toLocaleString()} individual{data.total !== 1 ? 's' : ''}
          {filterOccupation || submittedSearch ? ' (filtered)' : ''}
        </span>
        <div className="flex gap-2">
          <button
            onClick={() => handleSort('sitelinks_count')}
            className={`text-xs px-2 py-1 rounded ${
              sortField === 'sitelinks_count'
                ? 'bg-blue-100 text-blue-700'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            Fame{getSortIndicator('sitelinks_count')}
          </button>
          <button
            onClick={() => handleSort('impact_date')}
            className={`text-xs px-2 py-1 rounded ${
              sortField === 'impact_date'
                ? 'bg-blue-100 text-blue-700'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            Date{getSortIndicator('impact_date')}
          </button>
        </div>
      </div>

      {/* Scrollable table */}
      <div className="flex-1 overflow-y-auto min-h-0">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 sticky top-0">
            <tr>
              <th className="text-left px-2 py-1.5 font-medium text-gray-600">Name</th>
              <th className="text-left px-2 py-1.5 font-medium text-gray-600">Occupation</th>
              <th className="text-right px-2 py-1.5 font-medium text-gray-600">Impact Year</th>
              <th className="text-right px-2 py-1.5 font-medium text-gray-600">Fame</th>
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
                    className="text-blue-600 hover:underline"
                  >
                    {truncateText(ind.name_en, 25)}
                  </a>
                </td>
                <td className="px-2 py-1 text-gray-600">
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
          <button
            onClick={() => setCurrentPage(Math.max(1, currentPage - 1))}
            disabled={currentPage === 1}
            className="px-3 py-1 text-xs bg-gray-100 rounded hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Previous
          </button>
          <span className="text-xs text-gray-500">
            Page {currentPage} of {totalPages}
          </span>
          <button
            onClick={() => setCurrentPage(Math.min(totalPages, currentPage + 1))}
            disabled={currentPage === totalPages}
            className="px-3 py-1 text-xs bg-gray-100 rounded hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
