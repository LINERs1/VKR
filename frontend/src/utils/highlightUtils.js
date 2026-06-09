const MIN_WORDS = 3
const MIN_WORDS_CODE = 2
const MAX_WORDS = 8
const CODE_HINTS = new Set(['for', 'in', 'while', 'def', 'class', 'import', 'return', 'if', 'else'])

export function sanitizeHighlightText(text) {
  if (!text) return ''
  let t = String(text)
    .replace(/<[^>]+>/g, ' ')
    .replace(/https?:\/\/\S+|www\.\S+/gi, ' ')
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/[*_#]/g, ' ')
  const words = t.split(/\s+/).filter(Boolean)
  if (!words.length) return ''
  const minWords = words.slice(0, 5).some((w) => CODE_HINTS.has(w.toLowerCase().replace(/[:,]/g, '')))
    ? MIN_WORDS_CODE
    : MIN_WORDS
  if (words.length < minWords) return ''
  return words.slice(0, MAX_WORDS).join(' ')
}

export function normalizeForHighlightMatch(text) {
  return String(text || '')
    .toLowerCase()
    .replace(/[.,/#!$%^&*;:{}=\-_`~()«»""''\n\r\t]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

export function highlightSearchKey(text, wordLimit = 5) {
  return normalizeForHighlightMatch(text).split(' ').filter(Boolean).slice(0, wordLimit).join(' ')
}

export function textExistsInContent(highlight, content) {
  const key = highlightSearchKey(highlight, 5)
  if (!key) return false
  const hay = normalizeForHighlightMatch(content)
  if (hay.includes(key)) return true
  const words = key.split(' ')
  if (words.length >= 3 && hay.includes(words.slice(0, 3).join(' '))) return true
  if (words.length >= 2 && CODE_HINTS.has(words[0]) && hay.includes(words.slice(0, 2).join(' '))) return true
  return false
}

export function prepareHighlightText(raw, pageContent = '', { validateOnPage = false } = {}) {
  const sanitized = sanitizeHighlightText(raw)
  if (!sanitized) return { ok: false, text: '', reason: 'invalid' }
  if (validateOnPage && pageContent && !textExistsInContent(sanitized, pageContent)) {
    return { ok: false, text: sanitized, reason: 'not_found' }
  }
  return { ok: true, text: sanitized, reason: '' }
}

export function dispatchHighlight(text, delayMs = 600) {
  if (!text) return
  window.pendingHighlightText = text
  setTimeout(() => {
    window.dispatchEvent(new CustomEvent('eduai-highlight-text', { detail: { text } }))
  }, delayMs)
}
