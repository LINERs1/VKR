export async function apiFetch(endpoint, options = {}) {
  const baseUrl = 'http://127.0.0.1:8000/api'
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
  submitHomework: (assignmentId, data) => apiFetch(`/homework/assignments/${assignmentId}/submit`, { method: 'PUT', body: JSON.stringify(data) }),
  gradeHomework: (assignmentId, data) => apiFetch(`/homework/assignments/${assignmentId}/grade`, { method: 'PUT', body: JSON.stringify(data) })
}
