// Receipts identify unresolved commands. They never replace server-owned state.
export function readReceipt<T>(name: string, parse: (value: unknown) => T | null): T | null {
  try { return parse(JSON.parse(sessionStorage.getItem(name) ?? 'null')); }
  catch { return null; }
}
export function saveReceipt(name: string, value: unknown | null): boolean {
  try {
    if (value === null) sessionStorage.removeItem(name);
    else sessionStorage.setItem(name, JSON.stringify(value));
    return true;
  } catch { return false; }
}
