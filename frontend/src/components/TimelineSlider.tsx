import { useState, useCallback } from 'react';
import * as Slider from '@radix-ui/react-slider';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { useAppStore } from '../store';
import { Button } from './ui/button';
import { Input } from './ui/input';

const MIN_YEAR = -3400;
const MAX_YEAR = 2024;
const STEP = 25;

function formatYear(year: number): string {
  if (year < 0) {
    return `${Math.abs(year)} BCE`;
  } else if (year === 0) {
    return '1 CE';
  } else {
    return `${year} CE`;
  }
}

function parseYearInput(input: string): number | null {
  const trimmed = input.trim().toUpperCase();
  const bceMatch = trimmed.match(/^(\d+)\s*BCE$/);
  if (bceMatch) return -parseInt(bceMatch[1], 10);
  const ceMatch = trimmed.match(/^(\d+)\s*CE$/);
  if (ceMatch) return parseInt(ceMatch[1], 10);
  const num = parseInt(trimmed, 10);
  if (!isNaN(num)) return num;
  return null;
}

export function TimelineSlider() {
  const { selectedYear, setSelectedYear } = useAppStore();
  const [yearInput, setYearInput] = useState('');
  const [inputError, setInputError] = useState(false);

  const handleYearSubmit = useCallback(() => {
    const parsed = parseYearInput(yearInput);
    if (parsed !== null && parsed >= MIN_YEAR && parsed <= MAX_YEAR) {
      setSelectedYear(parsed);
      setYearInput('');
      setInputError(false);
    } else {
      setInputError(true);
    }
  }, [yearInput, setSelectedYear]);

  const stepBack = () => setSelectedYear(Math.max(MIN_YEAR, selectedYear - STEP));
  const stepForward = () => setSelectedYear(Math.min(MAX_YEAR, selectedYear + STEP));

  return (
    <div className="bg-white/90 backdrop-blur-sm border-t border-b border-gray-200 px-6 py-3 pb-10">
      <div className="max-w-7xl mx-auto">
        <div className="flex items-center gap-3">
          {/* Step back arrow */}
          <Button
            variant="ghost"
            size="icon"
            onClick={stepBack}
            disabled={selectedYear <= MIN_YEAR}
            title="Step back 25 years"
            className="h-8 w-8"
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>

          <span className="text-xs text-gray-400 whitespace-nowrap">{formatYear(MIN_YEAR)}</span>

          <Slider.Root
            className="relative flex items-center select-none touch-none w-full h-5"
            value={[selectedYear]}
            onValueChange={([value]) => setSelectedYear(value)}
            min={MIN_YEAR}
            max={MAX_YEAR}
            step={1}
          >
            <Slider.Track className="bg-gray-200 relative grow rounded-full h-2">
              <Slider.Range className="absolute bg-gray-900 rounded-full h-full" />
            </Slider.Track>
            <Slider.Thumb
              className="relative block w-5 h-5 bg-white border-2 border-gray-900 rounded-full shadow-md focus:outline-none focus:ring-2 focus:ring-gray-400 cursor-grab active:cursor-grabbing"
              aria-label="Year"
            >
              <div className="absolute top-full left-1/2 -translate-x-1/2 mt-2 bg-gray-900 text-white font-bold px-3 py-1 rounded-lg text-sm whitespace-nowrap shadow-md">
                {formatYear(selectedYear)}
              </div>
            </Slider.Thumb>
          </Slider.Root>

          <span className="text-xs text-gray-400 whitespace-nowrap">{formatYear(MAX_YEAR)}</span>

          {/* Step forward arrow */}
          <Button
            variant="ghost"
            size="icon"
            onClick={stepForward}
            disabled={selectedYear >= MAX_YEAR}
            title="Step forward 25 years"
            className="h-8 w-8"
          >
            <ChevronRight className="h-4 w-4" />
          </Button>

          {/* Year input */}
          <div className="flex items-center gap-2">
            <Input
              type="text"
              value={yearInput}
              onChange={(e) => {
                setYearInput(e.target.value);
                setInputError(false);
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleYearSubmit();
              }}
              placeholder="e.g. 500 BCE"
              className={`w-28 h-8 text-sm ${inputError ? 'border-red-400 bg-red-50' : ''}`}
            />
            <Button onClick={handleYearSubmit} size="sm">
              Go
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
