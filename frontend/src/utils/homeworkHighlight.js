/** Подсветка фрагментов ошибок в коде/тексте ученика. */

export function escapeHtml(text) {
  return String(text || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

export function extractErrorFragments(feedback) {
  if (!feedback) return []
  const frags = new Set()
  const re = /<span\s+class=["']hw-error["'][^>]*>([\s\S]*?)<\/span>/gi
  let m
  const norm = String(feedback)
    .replace(/<span\s+style=['"][^'"]*#ef4444[^'"]*['"][^>]*>([\s\S]*?)<\/span>/gi, '<span class="hw-error">$1</span>')
  while ((m = re.exec(norm))) {
    const f = m[1].trim()
    if (f.length >= 2) frags.add(f)
  }
  return [...frags].sort((a, b) => b.length - a.length)
}

/**
 * Подсвечивает в исходнике ученика фрагменты из отзыва ИИ.
 */
export function highlightSubmission(source, fragments) {
  if (!source || !fragments?.length) return escapeHtml(source)

  const ranges = []
  for (const frag of fragments) {
    if (!frag) continue
    let start = 0
    while (start < source.length) {
      const i = source.indexOf(frag, start)
      if (i === -1) break
      ranges.push({ start: i, end: i + frag.length })
      start = i + frag.length
    }
  }
  if (!ranges.length) return escapeHtml(source)

  ranges.sort((a, b) => a.start - b.start || b.end - a.end)
  const merged = []
  for (const r of ranges) {
    const last = merged[merged.length - 1]
    if (last && r.start < last.end) {
      last.end = Math.max(last.end, r.end)
    } else {
      merged.push({ ...r })
    }
  }

  let html = ''
  let pos = 0
  for (const { start, end } of merged) {
    html += escapeHtml(source.slice(pos, start))
    html += `<span class="hw-error">${escapeHtml(source.slice(start, end))}</span>`
    pos = end
  }
  html += escapeHtml(source.slice(pos))
  return html
}
