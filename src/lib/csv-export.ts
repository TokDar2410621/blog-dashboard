/**
 * Lightweight CSV/JSON export helpers. No external dependency.
 *
 * Robust escaping per RFC 4180 :
 *   - Any field containing `,` `"` `\n` `\r` is wrapped in double quotes.
 *   - Inner double quotes are doubled (`"` -> `""`).
 *   - Newlines inside fields are preserved (the wrapping quotes make the row safe).
 *
 * Tested mentally :
 *   - 100 rows : instant (synchronous string concat + a single Blob).
 *   - `title` containing `,` : wrapped in quotes.
 *   - `description` containing `"guillemets"` : doubled and wrapped.
 *   - multi-line content : wrapped in quotes, newlines preserved.
 */

export type ExportColumn<T = Record<string, unknown>> = {
  /** Object key to read on each row. */
  key: keyof T & string;
  /** Human-readable header (FR). */
  label: string;
  /**
   * Optional value transformer. Receives the raw cell value AND the full row
   * (useful for nested data, e.g. keyword.latest.position).
   * Return value is coerced to string via `formatCell`.
   */
  format?: (value: unknown, row: T) => unknown;
};

const NEEDS_ESCAPE = /[",\r\n]/;

/**
 * Escape a single CSV field. Always returns a string.
 *
 * - `null` / `undefined` -> empty string
 * - numbers / booleans -> stringified
 * - Date -> ISO string
 * - objects / arrays -> JSON.stringify (safer than `[object Object]`)
 */
function escapeCell(value: unknown): string {
  if (value === null || value === undefined) return "";

  let str: string;
  if (value instanceof Date) {
    str = value.toISOString();
  } else if (typeof value === "object") {
    try {
      str = JSON.stringify(value);
    } catch {
      str = String(value);
    }
  } else {
    str = String(value);
  }

  if (NEEDS_ESCAPE.test(str)) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

function getCellRaw<T>(row: T, col: ExportColumn<T>): unknown {
  const raw = (row as Record<string, unknown>)[col.key];
  return col.format ? col.format(raw, row) : raw;
}

/**
 * Build the CSV body. Exported for testability / non-download use cases.
 */
export function buildCsv<T>(rows: T[], columns: ExportColumn<T>[]): string {
  const header = columns.map((c) => escapeCell(c.label)).join(",");
  const body = rows
    .map((row) =>
      columns.map((col) => escapeCell(getCellRaw(row, col))).join(",")
    )
    .join("\r\n");
  // BOM so Excel detects UTF-8 (accents in FR labels render correctly).
  return `﻿${header}\r\n${body}`;
}

function triggerDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.style.display = "none";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  // Defer revoke so Safari finishes the download.
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

/**
 * Trigger a CSV download in the browser.
 *
 * @param filename - file name including extension (e.g. `keywords.csv`)
 * @param rows - array of row objects
 * @param columns - column definitions (key + label)
 */
export function exportToCsv<T>(
  filename: string,
  rows: T[],
  columns: ExportColumn<T>[]
): void {
  const csv = buildCsv(rows, columns);
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  triggerDownload(blob, filename);
}

/**
 * Trigger a JSON download. Re-shapes rows so only the declared columns are
 * exported, with FR labels as keys (consistent with the CSV header).
 */
export function exportToJson<T>(
  filename: string,
  rows: T[],
  columns: ExportColumn<T>[]
): void {
  const shaped = rows.map((row) => {
    const out: Record<string, unknown> = {};
    for (const col of columns) {
      out[col.label] = getCellRaw(row, col);
    }
    return out;
  });
  const json = JSON.stringify(shaped, null, 2);
  const blob = new Blob([json], { type: "application/json;charset=utf-8" });
  triggerDownload(blob, filename);
}
