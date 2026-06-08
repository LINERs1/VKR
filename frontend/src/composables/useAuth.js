import { ref } from 'vue'
import { apiFetch, getApiBaseUrl } from '../api'

const user = ref(null)
const token = ref(localStorage.getItem('token'))

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
    await fetchUser()
  }

  const register = async (username, password, role) => {
    const data = await apiFetch('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ username, password, role })
    })
    return data
  }

  const fetchUser = async () => {
    if (!token.value) return null
    try {
      const data = await apiFetch('/auth/me')
      user.value = data
      return data
    } catch (e) {
      user.value = null
      token.value = null
      localStorage.removeItem('token')
      return null
    }
  }

  const logout = () => {
    user.value = null
    token.value = null
    localStorage.removeItem('token')
    window.location.href = '/login'
  }

  return {
    user,
    token,
    isAuthenticated: () => !!token.value,
    login,
    register,
    fetchUser,
    logout
  }
}
