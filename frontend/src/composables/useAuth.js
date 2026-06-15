import { ref } from 'vue'
import { apiFetch, getApiBaseUrl } from '../api'

const user = ref(null)
const token = ref(localStorage.getItem('token'))
const customNodes = ref([])
let fetchingUserPromise = null

export function useAuth() {
  const login = async (username, password) => {
    const formData = new FormData()
    formData.append('username', username)
    formData.append('password', password)

    const res = await fetch(`${getApiBaseUrl('/auth/login')}/auth/login`, {
      method: 'POST',
      body: formData
    })
    
    if (!res.ok) {
      const data = await res.json()
      throw new Error(data.detail || 'Login failed')
    }
    
    const data = await res.json()
    token.value = data.access_token
    localStorage.setItem('token', data.access_token)
    await fetchUser(true)
  }

  const register = async (username, password, email) => {
    const data = await apiFetch('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ username, password, email })
    })
    return data
  }

  const forgotPassword = async (email) => {
    return await apiFetch('/auth/forgot-password', {
      method: 'POST',
      body: JSON.stringify({ email })
    })
  }

  const resetPassword = async (token, new_password) => {
    return await apiFetch('/auth/reset-password', {
      method: 'POST',
      body: JSON.stringify({ token, new_password })
    })
  }

  const fetchUser = async (force = false) => {
    if (!token.value) return null
    if (user.value && customNodes.value.length > 0 && !force) {
      return user.value
    }
    if (fetchingUserPromise && !force) {
      return fetchingUserPromise
    }

    fetchingUserPromise = (async () => {
      try {
        const data = await apiFetch('/auth/me')
        user.value = data
        try {
          customNodes.value = await apiFetch(`/navigation/custom-nodes?t=${Date.now()}`)
        } catch (err) {
          console.error('Failed to load custom navigation nodes:', err)
          customNodes.value = []
        }
        return data
      } catch (e) {
        user.value = null
        token.value = null
        localStorage.removeItem('token')
        customNodes.value = []
        return null
      } finally {
        fetchingUserPromise = null
      }
    })()

    return fetchingUserPromise
  }

  const logout = () => {
    user.value = null
    token.value = null
    customNodes.value = []
    localStorage.removeItem('token')
    window.location.href = '/login'
  }

  const hasAccess = (path, meta = {}) => {
    if (!user.value) return false
    if (path === '/admin' || meta.adminOnly) return user.value.role === 'admin'

    const node = customNodes.value.find(n => n.identifier === path)
    if (node) {
      const roles = node.allowed_roles || []
      if (roles.includes('all') || roles.length === 0) return true
      return roles.includes(user.value.role)
    }

    if (meta.adminOrTeacherOnly) {
      return ['teacher', 'admin'].includes(user.value.role)
    }
    if (meta.teacherOnly) {
      return user.value.role === 'teacher'
    }

    if (path === '/journal' || path === '/analytics') {
      return ['teacher', 'admin'].includes(user.value.role)
    }
    if (path.startsWith('/homeworks/workshop')) {
      return ['teacher', 'admin'].includes(user.value.role)
    }
    return true
  }

  return {
    user,
    token,
    customNodes,
    isAuthenticated: () => !!token.value,
    login,
    logout,
    register,
    forgotPassword,
    resetPassword,
    fetchUser,
    hasAccess
  }
}
