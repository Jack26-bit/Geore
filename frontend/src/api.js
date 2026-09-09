const API_BASE = import.meta.env.VITE_API_URL;

/**
 * Send images + query to the GEORE backend for analysis.
 *
 * @param {FormData} formData  — must contain: image1, query; optionally image2, has_sar
 * @returns {Promise<object>}  — the JSON response from POST /analyze
 */
export async function analyzeImages(formData) {
  const res = await fetch(`${API_BASE}/analyze`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Analysis failed (${res.status}): ${text}`);
  }

  return res.json();
}
