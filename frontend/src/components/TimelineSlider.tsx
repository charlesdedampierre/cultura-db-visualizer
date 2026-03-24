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
    <div className="flex justify-center pb-4 px-4">
      <div className="bg-white/90 backdrop-blur-sm rounded-full shadow-lg px-4 py-2 flex items-center gap-3 max-w-3xl w-full">
        {/* Step back arrow */}
        <Button
          variant="ghost"
          size="icon"
          onClick={stepBack}
          disabled={selectedYear <= MIN_YEAR}
          title="Step back 25 years"
          className="h-8 w-8 rounded-full flex-shrink-0"
        >
          <ChevronLeft className="h-4 w-4" />
        </Button>

        <span className="text-xs text-gray-400 whitespace-nowrap hidden sm:inline">{formatYear(MIN_YEAR)}</span>

        <div className="flex-1 relative">
          <Slider.Root
            className="relative flex items-center select-none touch-none w-full h-5"
            value={[selectedYear]}
            onValueChange={([value]) => setSelectedYear(value)}
            min={MIN_YEAR}
            max={MAX_YEAR}
            step={1}
          >
            <Slider.Track className="bg-gray-200 relative grow rounded-full h-1.5">
              <Slider.Range className="absolute bg-gray-900 rounded-full h-full" />
            </Slider.Track>
            <Slider.Thumb
              className="relative block w-4 h-4 bg-white border-2 border-gray-900 rounded-full shadow-md focus:outline-none focus:ring-2 focus:ring-gray-400 cursor-grab active:cursor-grabbing"
              aria-label="Year"
            >
              <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 bg-gray-900 text-white font-semibold px-2 py-0.5 rounded-md text-xs whitespace-nowrap shadow-md">
                {formatYear(selectedYear)}
              </div>
            </Slider.Thumb>
          </Slider.Root>
        </div>

        <span className="text-xs text-gray-400 whitespace-nowrap hidden sm:inline">{formatYear(MAX_YEAR)}</span>

        {/* Step forward arrow */}
        <Button
          variant="ghost"
          size="icon"
          onClick={stepForward}
          disabled={selectedYear >= MAX_YEAR}
          title="Step forward 25 years"
          className="h-8 w-8 rounded-full flex-shrink-0"
        >
          <ChevronRight className="h-4 w-4" />
        </Button>

        {/* Divider */}
        <div className="h-6 w-px bg-gray-200 flex-shrink-0 hidden md:block" />

        {/* Year input */}
        <div className="items-center gap-1.5 hidden md:flex flex-shrink-0">
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
            placeholder="500 BCE"
            className={`w-20 h-7 text-xs rounded-full px-3 ${inputError ? 'border-red-400 bg-red-50' : ''}`}
          />
          <Button onClick={handleYearSubmit} size="sm" className="h-7 rounded-full px-3 text-xs">
            Go
          </Button>
        </div>
      </div>
    </div>
  );
}
