export function getApiBaseUrl() {
  const v = import.meta.env.VITE_API_BASE_URL
  if (v === '/api' || v === '') return '/api'
  if (typeof v === 'string' && v.startsWith('http')) return v.replace(/\/$/, '')
  return 'http://127.0.0.1:8000/api'
}

export async function apiFetch(endpoint, options = {}) {
  const baseUrl = getApiBaseUrl()
  const url = endpoint.startsWith('http') ? endpoint : `${baseUrl}${endpoint}`
  
  const headers = { ...options.headers }
  const token = localStorage.getItem('token')
  
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  if (!(options.body instanceof FormData) && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json'
  }

  const res = await fetch(url, { ...options, headers })
  
  // Если токен протух или невалиден
  if (res.status === 401) {
    localStorage.removeItem('token')
    window.location.href = '/login'
    throw new Error('Unauthorized')
  }

  // Не пытаемся парсить JSON если это поток или нет контента
  if (res.status === 204) return null
  
  const contentType = res.headers.get('content-type')
  if (contentType && contentType.includes('application/json')) {
    const data = await res.json()
    if (!res.ok) throw new Error(data.detail || 'API Error')
    return data
  }
  
  if (!res.ok) throw new Error(`API Error: ${res.statusText}`)
  return res
}

export const hwApi = {
  getStudents: () => apiFetch('/auth/students'),
  getHomeworks: () => apiFetch('/homework'),
  getHomework: (id) => apiFetch(`/homework/${id}`),
  createHomework: (data) => apiFetch('/homework', { method: 'POST', body: JSON.stringify(data) }),
  getJournalSummary: () => apiFetch('/homework/journal/summary'),
  getReminders: () => apiFetch('/homework/reminders'),
  getHomeworkHint: (assignmentId, draft) =>
    apiFetch(`/homework/assignments/${assignmentId}/hint`, {
      method: 'POST',
      body: JSON.stringify(draft || {}),
    }),
  submitHomework: (assignmentId, data) => apiFetch(`/homework/assignments/${assignmentId}/submit`, { method: 'PUT', body: JSON.stringify(data) }),
  gradeHomework: (assignmentId, data) => apiFetch(`/homework/assignments/${assignmentId}/grade`, { method: 'PUT', body: JSON.stringify(data) }),
  aiReviewHomework: (assignmentId) => apiFetch(`/homework/assignments/${assignmentId}/ai-review`, { method: 'POST' })
}

export const workshopApi = {
  listTemplates: () => apiFetch('/homework/templates'),
  getTemplate: (id) => apiFetch(`/homework/templates/${id}`),
  createTemplate: (data) =>
    apiFetch('/homework/templates', { method: 'POST', body: JSON.stringify(data) }),
  updateTemplate: (id, data) =>
    apiFetch(`/homework/templates/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteTemplate: (id) => apiFetch(`/homework/templates/${id}`, { method: 'DELETE' }),
  assignTemplate: (id, studentIds) =>
    apiFetch(`/homework/templates/${id}/assign`, {
      method: 'POST',
      body: JSON.stringify({ student_ids: studentIds }),
    }),
}
