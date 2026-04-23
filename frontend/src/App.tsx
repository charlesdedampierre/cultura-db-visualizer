import { useState, useEffect, useCallback, useRef } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { TimelineSlider } from './components/TimelineSlider';
import { WorldMap } from './components/WorldMap';
import { PolityPanel } from './components/PolityPanel';
import { UnifiedSearch } from './components/UnifiedSearch';
import { useAppStore } from './store';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 minutes
      retry: 3,
      refetchOnWindowFocus: false,
    },
  },
});

function AboutModal({ onClose }: { onClose: () => void }) {
  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-xl shadow-2xl max-w-lg w-full p-6" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-bold text-gray-900">About</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 p-1">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <div className="space-y-3 text-sm text-gray-600 leading-relaxed">
          <p>
            <strong>Our History in Data</strong> is an interactive tool for exploring
            the rise and fall of political entities throughout human history, from ancient
            civilizations to modern states.
          </p>
          <p>
            Navigate through time using the timeline slider to see which polities were active
            at any given period. Click on a polity on the map to explore its notable individuals,
            occupational breakdown, and population evolution over centuries.
          </p>
          <p>
            Use the charts to filter individuals by occupation or time period. Toggle between
            a flat map and a 3D globe view for different perspectives on historical geography.
          </p>
          <div className="pt-3 border-t border-gray-200">
            <h3 className="font-semibold text-gray-900 mb-2">Data Sources</h3>
            <ul className="space-y-1 text-gray-600">
              <li>
                <a href="https://github.com/charlesdedampierre/cultura_database" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">Cultura Database</a>
                {' '}- Historical figures and cultural data
              </li>
              <li>
                <a href="https://github.com/Seshat-Global-History-Databank/cliopatria" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">Cliopatria Project</a>
                {' '}- Historical polity boundaries
              </li>
              <li>
                <a href="https://seshat-db.com/" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">Seshat Database</a>
                {' '}- Global history databank
              </li>
              <li>
                <a href="https://www.wikidata.org" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">Wikidata</a>
                {' '}- Linked open data
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}

function App() {
  const [showAbout, setShowAbout] = useState(false);
  const { selectedPolityId } = useAppStore();

  // Track panel visibility with delayed unmount for smooth animation
  const [isPanelVisible, setIsPanelVisible] = useState(false);
  const [shouldRenderPanel, setShouldRenderPanel] = useState(false);

  // Draggable panel height (percentage of viewport height for the map)
  const [mapHeightPercent, setMapHeightPercent] = useState(55);
  const [isDragging, setIsDragging] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (selectedPolityId) {
      // Reset height to default when selecting a new polity
      setMapHeightPercent(55);

      // Opening: render immediately, then show
      setShouldRenderPanel(true);
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          setIsPanelVisible(true);
        });
      });
    } else {
      // Closing: hide first, then unmount after transition
      setIsPanelVisible(false);
      const timer = setTimeout(() => {
        setShouldRenderPanel(false);
      }, 300); // Match transition duration
      return () => clearTimeout(timer);
    }
  }, [selectedPolityId]);

  // Handle drag to resize panel
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  useEffect(() => {
    if (!isDragging) return;

    const handleMouseMove = (e: MouseEvent) => {
      if (!containerRef.current) return;

      const containerRect = containerRef.current.getBoundingClientRect();
      const headerHeight = 52; // Approximate header height
      const footerHeight = 36; // Approximate footer height
      const availableHeight = containerRect.height - headerHeight - footerHeight;
      const mouseY = e.clientY - containerRect.top - headerHeight;

      // Calculate percentage (clamped between 25% and 85%)
      const percent = Math.min(85, Math.max(25, (mouseY / availableHeight) * 100));
      setMapHeightPercent(percent);
    };

    const handleMouseUp = () => {
      setIsDragging(false);
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging]);

  return (
    <QueryClientProvider client={queryClient}>
      <div ref={containerRef} className="h-screen flex flex-col overflow-hidden">
        {/* Header */}
        <header className="bg-gray-900 text-white px-6 py-3 flex items-center justify-between flex-shrink-0 z-20">
          <h1 className="text-lg font-semibold tracking-tight">Our History in Data</h1>
          <nav className="flex items-center gap-4">
            <UnifiedSearch />
            <button
              onClick={() => setShowAbout(true)}
              className="text-sm text-gray-300 hover:text-white transition-colors"
            >
              About
            </button>
          </nav>
        </header>

        {/* Map - takes remaining space, shrinks when panel opens */}
        <div
          className={`relative overflow-hidden flex-shrink-0 ${
            isDragging ? '' : 'transition-all duration-300 ease-in-out'
          } ${!isPanelVisible ? 'flex-1' : ''}`}
          style={isPanelVisible ? { height: `${mapHeightPercent}%` } : undefined}
        >
          <WorldMap />
          {/* Timeline Slider - floating at bottom of map */}
          <div className="absolute bottom-0 left-0 right-0 z-10">
            <TimelineSlider />
          </div>
        </div>

        {/* Polity Panel - below map, expands when polity selected */}
        <div
          className={`overflow-hidden relative ${
            isDragging ? '' : 'transition-all duration-300 ease-in-out'
          } ${isPanelVisible ? 'flex-1' : 'h-0'}`}
          style={{
            opacity: isPanelVisible ? 1 : 0,
            transform: isPanelVisible ? 'translateY(0)' : 'translateY(20px)'
          }}
        >
          {/* Drag handle - drag to resize, click to collapse */}
          <div
            onMouseDown={handleMouseDown}
            onDoubleClick={() => useAppStore.getState().setSelectedPolityId(null)}
            className={`absolute left-0 right-0 top-0 z-10 h-4 flex items-center justify-center cursor-ns-resize group ${
              isDragging ? 'bg-gray-200' : 'hover:bg-gray-200/50'
            } transition-colors`}
            title="Drag to resize, double-click to close"
          >
            <div className={`w-10 h-1 rounded-full transition-colors ${
              isDragging ? 'bg-gray-500' : 'bg-gray-300 group-hover:bg-gray-400'
            }`} />
          </div>
          {shouldRenderPanel && <PolityPanel />}
        </div>

        {/* Footer */}
        <footer className="bg-gray-900 text-gray-400 px-6 py-2 flex items-center justify-center gap-2 text-xs flex-shrink-0">
          <span>© 2026</span>
          <span className="text-gray-600">·</span>
          <span>Made by <a href="https://bunka.ai" target="_blank" rel="noopener noreferrer" className="text-gray-300 hover:text-white transition-colors">Bunka.ai</a></span>
        </footer>

        {/* About modal */}
        {showAbout && <AboutModal onClose={() => setShowAbout(false)} />}
      </div>
    </QueryClientProvider>
  );
}

export default App;
