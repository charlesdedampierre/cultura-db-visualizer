import { useQuery } from '@tanstack/react-query';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine, Label,
} from 'recharts';
import { useAppStore } from '../store';
import { getCityEvolution } from '../api';

function formatYear(year: number): string {
  if (year < 0) return `${Math.abs(year)} BCE`;
  return `${year} CE`;
}

export function CityEvolutionChart() {
  const { selectedCityId, filterYear, setFilterYear } = useAppStore();

  const { data, isLoading } = useQuery({
    queryKey: ['cityEvolution', selectedCityId],
    queryFn: () => (selectedCityId ? getCityEvolution(selectedCityId) : Promise.resolve(null)),
    enabled: !!selectedCityId,
    staleTime: Infinity,
  });

  if (!selectedCityId) {
    return <div className="h-full flex items-center justify-center text-gray-400">Select a city</div>;
  }
  if (isLoading || !data) {
    return <div className="h-full flex items-center justify-center text-gray-400">Loading…</div>;
  }
  if (data.evolution.length === 0) {
    return <div className="h-full flex items-center justify-center text-gray-400">No timeline data</div>;
  }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const handleChartClick = (e: any) => {
    if (e?.activePayload?.[0]) setFilterYear(e.activePayload[0].payload.year);
  };

  return (
    <div className="h-full relative">
      {filterYear != null && (
        <div
          className="absolute top-0 right-0 z-10 bg-gray-200 text-gray-900 text-xs px-2 py-0.5 rounded cursor-pointer"
          onClick={() => setFilterYear(null)}
        >
          {formatYear(filterYear)} ✕
        </div>
      )}
      <ResponsiveContainer width="100%" height="100%">
        <LineChart
          data={data.evolution}
          margin={{ top: 5, right: 20, left: 10, bottom: 5 }}
          onClick={handleChartClick}
          style={{ cursor: 'pointer' }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          {/* Numeric X axis so the ReferenceLine can render at any year —
              even one that isn't exactly a bucket present in this city's
              evolution data (e.g. main timeline at 200 CE while the city's
              chart only has data from 1500 onward). */}
          <XAxis
            dataKey="year"
            type="number"
            domain={['dataMin', 'dataMax']}
            tickFormatter={(y) => formatYear(y)}
            tick={{ fontSize: 11 }}
            stroke="#9ca3af"
          />
          <YAxis tickFormatter={(v) => v.toLocaleString()} tick={{ fontSize: 11 }} stroke="#9ca3af">
            <Label
              value="Individuals"
              angle={-90}
              position="insideLeft"
              style={{ textAnchor: 'middle', fill: '#6b7280', fontSize: 11 }}
              offset={0}
            />
          </YAxis>
          <Tooltip
            labelFormatter={(year) => formatYear(year as number)}
            formatter={(v) => [(v as number).toLocaleString(), 'Individuals']}
            contentStyle={{ backgroundColor: 'white', border: '1px solid #e5e7eb', borderRadius: 8, fontSize: 12 }}
          />
          {filterYear != null && (
            <ReferenceLine x={filterYear} stroke="#111827" strokeWidth={2} strokeDasharray="4 4" />
          )}
          <Line
            type="monotone"
            dataKey="count"
            stroke="#111827"
            strokeWidth={2}
            dot={(props) => {
              const { cx, cy, payload, index } = props;
              if (cx == null || cy == null) return <circle key={`dot-${index}`} r={0} />;
              const isSel = filterYear === payload.year;
              return (
                <circle
                  key={`dot-${index}`}
                  cx={cx}
                  cy={cy}
                  r={isSel ? 6 : 3}
                  fill={isSel ? '#030712' : '#111827'}
                  stroke={isSel ? '#030712' : 'none'}
                  strokeWidth={isSel ? 2 : 0}
                />
              );
            }}
            activeDot={{ r: 6, fill: '#1f2937' }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
