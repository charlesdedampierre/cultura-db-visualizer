import { useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { TimelineSlider } from './components/TimelineSlider';
import { WorldMap } from './components/WorldMap';
import { PolityPanel } from './components/PolityPanel';
import { PolitySearch } from './components/PolitySearch';
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
            The <strong>Cultura Visualiser</strong> is an interactive tool for exploring
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
                <a href="https://github.com/charlesdedampierre/cultura" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">Cultura Database</a>
                {' '}- Historical figures and cultural data
              </li>
              <li>
                <a href="https://github.com/Seshat-Global-History-Databank/cliopatria" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">Cliopatria Project</a>
                {' '}- Historical polity boundaries
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

  return (
    <QueryClientProvider client={queryClient}>
      <div className="h-screen flex flex-col overflow-hidden">
        {/* Header */}
        <header className="bg-gray-900 text-white px-6 py-3 flex items-center justify-between flex-shrink-0 z-20">
          <h1 className="text-lg font-semibold tracking-tight">Cultura Visualiser</h1>
          <nav className="flex items-center gap-4">
            <PolitySearch />
            <button
              onClick={() => setShowAbout(true)}
              className="text-sm text-gray-300 hover:text-white transition-colors"
            >
              About
            </button>
          </nav>
        </header>

        {/* Map - takes remaining space, shrinks when panel opens */}
        <div className={`relative overflow-hidden flex-shrink-0 transition-all duration-300 ${
          selectedPolityId ? 'h-[55vh]' : 'flex-1'
        }`}>
          <WorldMap />
          {/* Timeline Slider - floating at bottom of map */}
          <div className="absolute bottom-0 left-0 right-0 z-10">
            <TimelineSlider />
          </div>
        </div>

        {/* Polity Panel - below map, expands when polity selected */}
        {selectedPolityId && (
          <div className="flex-1 bg-white overflow-auto relative">
            {/* Collapse handle - subtle line at top */}
            <button
              onClick={() => useAppStore.getState().setSelectedPolityId(null)}
              className="absolute left-1/2 -translate-x-1/2 top-1 z-10 py-1 px-4 group"
              title="Collapse panel"
            >
              <div className="w-8 h-1 bg-gray-200 rounded-full group-hover:bg-gray-400 transition-colors" />
            </button>
            <PolityPanel />
          </div>
        )}

        {/* Footer */}
        <footer className="bg-gray-900 text-gray-400 px-6 py-2 flex items-center justify-center gap-2 text-xs flex-shrink-0">
          <span>© 2026</span>
          <span className="text-gray-600">·</span>
          <span>Made by <a href="https://bunka.ai" target="_blank" rel="noopener noreferrer" className="text-gray-300 hover:text-white transition-colors">bunka.ai</a></span>
        </footer>

        {/* About modal */}
        {showAbout && <AboutModal onClose={() => setShowAbout(false)} />}
      </div>
    </QueryClientProvider>
  );
}

export default App;
