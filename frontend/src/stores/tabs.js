import { reactive } from 'vue'
import { api } from '../api/client.js'
import { menuOf, session } from './session.js'
import { toast } from './toast.js'

const STORAGE_KEY = 'swp_tabs'
const MAX_TABS = 12
const FORBIDDEN = '해당 화면에 대한 권한이 없습니다.'

// nonce: 같은 탭으로 다시 이동할 때 화면이 param 맥락을 재적용하는 신호. navCount: 이동 시 모달을 닫는 신호.
export const tabs = reactive({ list: [], active: null, navCount: 0 })

const keyOf = (token, param) => `${token}:${param ?? ''}`
const makeTab = (token, param) => ({
  key: keyOf(token, param),
  token,
  param: param ?? null,
  title: menuOf(token).title,
  nonce: 0,
})

function persist() {
  sessionStorage.setItem(
    STORAGE_KEY,
    JSON.stringify({ tabs: tabs.list.map(({ token, param }) => ({ token, param })), active: tabs.active }),
  )
}

export function activate(key) {
  tabs.active = key
  persist()
}

export function closeTab(key) {
  const at = tabs.list.findIndex((t) => t.key === key)
  if (at < 0) return
  tabs.list.splice(at, 1)
  if (tabs.active === key) tabs.active = (tabs.list[at] ?? tabs.list[at - 1])?.key ?? null
  persist()
}

export function closeOthers() {
  tabs.list = tabs.list.filter((t) => t.key === tabs.active)
  persist()
}

export async function navigate(token, param = null) {
  const menu = menuOf(token)
  if (!menu) {
    toast.error(FORBIDDEN)
    return false
  }
  const key = keyOf(token, param)
  const existing = tabs.list.find((t) => t.key === key)
  if (existing) {
    existing.nonce++
    tabs.navCount++
    activate(key)
    return true
  }
  if (tabs.list.length >= MAX_TABS) {
    toast.error('탭은 최대 12개까지 열 수 있습니다. 사용하지 않는 탭을 닫아주세요.')
    return false
  }
  tabs.list.push(makeTab(token, param))
  tabs.navCount++
  activate(key)
  try {
    await api('/api/me/menu-access', { method: 'POST', body: { menu_id: menu.menu_id } })
  } catch (e) {
    if (e.status !== 403) return true // 접근 기록 실패가 화면 사용을 막지는 않는다
    closeTab(key)
    toast.error(FORBIDDEN)
    return false
  }
  return true
}

function readSaved() {
  try {
    return JSON.parse(sessionStorage.getItem(STORAGE_KEY)) ?? {}
  } catch {
    return {}
  }
}

export function restoreTabs() {
  const saved = readSaved()
  const seen = new Set()
  tabs.list = (Array.isArray(saved.tabs) ? saved.tabs : [])
    .filter((t) => menuOf(t.token) && !seen.has(keyOf(t.token, t.param)) && seen.add(keyOf(t.token, t.param)))
    .slice(0, MAX_TABS)
    .map((t) => makeTab(t.token, t.param))
  if (tabs.list.length) {
    activate(tabs.list.some((t) => t.key === saved.active) ? saved.active : tabs.list[0].key)
    return
  }
  tabs.active = null
  const home = menuOf('dashboard') ?? session.menu.find((m) => m.token)
  if (home) navigate(home.token)
}
