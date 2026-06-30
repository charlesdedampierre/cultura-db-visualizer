import { useState } from 'react';
import { Info } from 'lucide-react';

// The four kinds of polity-to-polity relationship recorded by Cliopatria
// (52 in total). Unlike territorial nesting ("Contains"), these link polities
// that stay distinct — and they differ in nature, from subordination to
// partnership. Surfaced next to the polity header (BUN-1139 review).
const RELATION_TYPES = [
  {
    kind: 'Allegiance',
    pattern: 'Allegiance of … to …',
    count: 21,
    nature: 'Subordination',
    meaning: 'One polity owes loyalty or submission to a dominant one (suzerainty).',
    example: 'Allegiance of Joseon to Ming Dynasty',
    tone: 'text-amber-800 bg-amber-50 border-amber-200',
  },
  {
    kind: 'Personal union',
    pattern: 'Personal union of … with …',
    count: 13,
    nature: 'Shared crown',
    meaning: 'Two polities share one monarch but stay distinct.',
    example: 'Personal union of Spanish Empire with Habsburg Monarchy',
    tone: 'text-violet-800 bg-violet-50 border-violet-200',
  },
  {
    kind: 'Alliance',
    pattern: 'Alliance between … and …',
    count: 12,
    nature: 'Between equals',
    meaning: 'Two peers bound by a treaty or pact.',
    example: 'Alliance between Han Dynasty and Xiongnu',
    tone: 'text-emerald-800 bg-emerald-50 border-emerald-200',
  },
  {
    kind: 'Vassalage',
    pattern: 'Vassalage of … to …',
    count: 6,
    nature: 'Subordination',
    meaning: 'Feudal subordination of a vassal to a lord.',
    example: 'Vassalage of Kingdom of Bohemia to Holy Roman Empire',
    tone: 'text-amber-800 bg-amber-50 border-amber-200',
  },
];

function RelationTypesModal({ onClose }: { onClose: () => void }) {
  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div
        className="bg-white rounded-xl shadow-2xl max-w-2xl w-full p-6 max-h-[85vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-bold text-gray-900">Relationships between polities</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 p-1">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <p className="text-sm text-gray-600 leading-relaxed mb-5">
          Beyond <strong>territorial nesting</strong> (the <em>Contains</em> hierarchy above, where
          one polity sits inside a larger one), the data also records <strong>relationships</strong>{' '}
          that link polities which stay distinct. These come in four kinds — and they differ in
          nature, from subordination to partnership.
        </p>
        <div className="space-y-3">
          {RELATION_TYPES.map((r) => (
            <div key={r.kind} className="rounded-lg border border-gray-200 p-4">
              <div className="flex items-center flex-wrap gap-2 mb-1.5">
                <span className={`text-xs font-semibold px-2 py-0.5 rounded-full border ${r.tone}`}>
                  {r.kind}
                </span>
                <span className="text-[11px] font-medium text-gray-400 uppercase tracking-wide">
                  {r.nature}
                </span>
                <span className="ml-auto text-xs text-gray-400">{r.count} in the data</span>
              </div>
              <div className="text-sm text-gray-700">{r.meaning}</div>
              <div className="mt-1.5 text-xs text-gray-500">
                <span className="font-mono text-gray-400">{r.pattern}</span>
                <span className="mx-1.5 text-gray-300">·</span>
                e.g. {r.example}
              </div>
            </div>
          ))}
        </div>
        <p className="text-xs text-gray-400 leading-relaxed mt-5 pt-3 border-t border-gray-200">
          Vassalage and Allegiance are hierarchical (one polity under another); Alliance is between
          equals; a Personal union is a shared-crown link rather than one polity absorbing the
          other. None of them should be read as a territorial parent.
        </p>
      </div>
    </div>
  );
}

/** Subtle inline trigger + modal explaining the kinds of polity relationship. */
export function RelationTypesInfo() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button
        onClick={() => setOpen(true)}
        title="The kinds of relationship that can link polities (alliance, allegiance, …)"
        className="inline-flex items-center text-gray-400 hover:text-gray-700 transition-colors"
      >
        <Info className="h-4 w-4" />
      </button>
      {open && <RelationTypesModal onClose={() => setOpen(false)} />}
    </>
  );
}
