/** Keep in sync with backend `LARO_PDF_UPLOAD_MAX_MB` (default 50). */
const DEFAULT_MB = 50;

function parseMaxMb() {
  const raw = process.env.REACT_APP_PDF_UPLOAD_MAX_MB;
  if (raw == null || raw === '') return DEFAULT_MB;
  const n = Number.parseInt(String(raw), 10);
  if (!Number.isFinite(n) || n < 1) return DEFAULT_MB;
  return Math.min(n, 200);
}

export const PDF_UPLOAD_MAX_MB = parseMaxMb();
export const PDF_UPLOAD_MAX_BYTES = PDF_UPLOAD_MAX_MB * 1024 * 1024;

export function isPdfFileTooLarge(file) {
  return Boolean(file && file.size > PDF_UPLOAD_MAX_BYTES);
}

export function pdfUploadLimitParams() {
  return { maxMb: PDF_UPLOAD_MAX_MB };
}
