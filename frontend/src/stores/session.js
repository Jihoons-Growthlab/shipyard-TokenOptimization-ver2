import { reactive } from 'vue'
import { api, auth } from '../api/client.js'

const TOKEN_KEY = 'swp_token'

export const session = reactive({
  token: sessionStorage.getItem(TOKEN_KEY),
  me: null,
  menu: [],
})

auth.token = () => session.token

let codes = null

export function setToken(token) {
  session.token = token
  sessionStorage.setItem(TOKEN_KEY, token)
}

export function clearSession() {
  session.token = null
  session.me = null
  session.menu = []
  codes = null
  sessionStorage.removeItem(TOKEN_KEY)
  sessionStorage.removeItem('swp_tabs')
}

export async function loadSession() {
  const [me, menu] = await Promise.all([api('/api/auth/me'), api('/api/me/menu')])
  session.me = me
  session.menu = menu
}

export function loadCodes() {
  codes ??= api('/api/codes').catch((e) => {
    codes = null
    throw e
  })
  return codes
}

export function logout() {
  const token = session.token
  clearSession()
  api('/api/auth/logout', { method: 'POST', token }).catch(() => {})
}

export const menuOf = (token) => session.menu.find((m) => m.token === token)
export const canWrite = (token) => Boolean(menuOf(token)?.can_write)

// 공통 코드 이름. 없으면 코드 그대로.
export const codeName = (codes, group, code) => codes?.[group]?.find((c) => c.code === code)?.name ?? code
