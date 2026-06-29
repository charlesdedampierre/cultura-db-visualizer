import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

// Cliopatria stores meta polities parenthesised, e.g. "(Roman Empire)". We never
// want the parens in the UI — meta status is shown via a badge/column instead.
export function displayPolityName(name: string | null | undefined): string {
  if (!name) return "";
  return name.trim().replace(/^\((.*)\)$/, "$1").trim();
}
