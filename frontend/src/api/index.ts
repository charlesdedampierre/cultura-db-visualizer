import type {
  ActivePolitiesResponse,
  PolityEvolution,
  PolityTopCities,
  PaginatedIndividuals,
  PolityDetails,
  PolitySearchResult,
} from '../types';

const API_BASE = '/api';

async function fetchJson<T>(url: string): Promise<T> {
  const response = await fetch(url, { cache: 'no-store' });
  if (!response.ok) {
    const text = await response.text();
    let detail = text;
    try {
      const body = JSON.parse(text);
      detail = body.detail || text;
    } catch { /* use raw text */ }
    throw new Error(`${response.status}: ${detail}`);
  }
  return response.json();
}

// Get active polities at a specific year
export async function getActivePolities(year: number, hierarchy: 'leaf' | 'aggregate' = 'leaf'): Promise<ActivePolitiesResponse> {
  return fetchJson<ActivePolitiesResponse>(`${API_BASE}/polities/active?year=${year}&hierarchy=${hierarchy}`);
}

// Get polity details
export async function getPolityDetails(polityId: number): Promise<PolityDetails> {
  return fetchJson<PolityDetails>(`${API_BASE}/polities/${polityId}`);
}

// Get polity evolution data
export async function getPolityEvolution(polityId: number): Promise<PolityEvolution> {
  return fetchJson<PolityEvolution>(`${API_BASE}/polities/${polityId}/evolution`);
}

// Get top cities for a polity
export async function getPolityTopCities(polityId: number, limit = 500): Promise<PolityTopCities> {
  return fetchJson<PolityTopCities>(`${API_BASE}/cities/polity/${polityId}?limit=${limit}`);
}

// Get individuals with cities for client-side dynamic computation
export interface IndividualsCitiesResponse {
  polity_id: number;
  individuals: Array<{
    c: string;  // city_id
    y: number;  // impact year
  }>;
}

export async function getPolityIndividualsCities(polityId: number): Promise<IndividualsCitiesResponse> {
  return fetchJson<IndividualsCitiesResponse>(`${API_BASE}/cities/polity/${polityId}/individuals-cities`);
}

// Get individuals for a polity
export async function getPolityIndividuals(
  polityId: number,
  page: number,
  limit: number,
  sort: 'sitelinks_count' | 'impact_date',
  order: 'asc' | 'desc',
  impactYear?: number | null,
  occupation?: string | null,
  nameSearch?: string | null,
): Promise<PaginatedIndividuals> {
  let url = `${API_BASE}/individuals/polity/${polityId}?page=${page}&limit=${limit}&sort=${sort}&order=${order}`;
  if (impactYear != null) url += `&impact_year=${impactYear}`;
  if (occupation) url += `&occupation=${encodeURIComponent(occupation)}`;
  if (nameSearch) url += `&name_search=${encodeURIComponent(nameSearch)}`;
  return fetchJson<PaginatedIndividuals>(url);
}

// Search polities by name
export async function searchPolities(query: string, limit = 10): Promise<{ results: PolitySearchResult[] }> {
  return fetchJson<{ results: PolitySearchResult[] }>(`${API_BASE}/polities/search?q=${encodeURIComponent(query)}&limit=${limit}`);
}

// Search cities by name
export interface CitySearchResult {
  city_id: string;
  name: string;
  lat: number;
  lon: number;
  count: number;
  polity_id: number;
  polity_name: string;
  polity_from_year: number | null;
  polity_to_year: number | null;
  first_individual_year: number | null;
  peak_year: number | null;
}

export async function searchCities(query: string, limit = 20): Promise<{ results: CitySearchResult[] }> {
  return fetchJson<{ results: CitySearchResult[] }>(`${API_BASE}/cities/search?q=${encodeURIComponent(query)}&limit=${limit}`);
}
