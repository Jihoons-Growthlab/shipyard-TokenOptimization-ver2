import { beforeEach, describe, expect, it, vi } from 'vitest'
import { closeOthers, closeTab, navigate, restoreTabs, tabs, activate } from '../stores/tabs.js'
import { session } from '../stores/session.js'
import { toasts } from '../stores/toast.js'

const item = (menu_id, token, title = token) => ({ menu_id, token, title, parent_id: null, can_write: true })
const manyMenus = () => Array.from({ length: 14 }, (_, i) => item(`M${i}`, `s${i}`))

describe('탭', () => {
  beforeEach(() => {
    sessionStorage.clear()
    toasts.splice(0)
    tabs.list = []
    tabs.active = null
    tabs.navCount = 0
    session.menu = [item('M00', 'dashboard', '대시보드'), item('M11', 'hull-list', '호선 목록'), item('M21', 'plan-gantt', '공정 계획')]
    vi.stubGlobal('fetch', vi.fn(async () => new Response(null, { status: 204 })))
  })

  it('SHELL-T02 같은 화면은 탭 하나, 재이동은 param 맥락 신호를 올린다', async () => {
    await navigate('hull-list', '8001')
    await navigate('hull-list', '8001')
    expect(tabs.list).toHaveLength(1)
    expect(tabs.list[0].nonce).toBe(1)
    await navigate('hull-list', '8002')
    expect(tabs.list.map((t) => t.key)).toEqual(['hull-list:8001', 'hull-list:8002'])
    expect(fetch).toHaveBeenCalledTimes(2)
  })

  it('SHELL-T03 13번째 탭은 오류, 기존 탭 유지', async () => {
    session.menu = manyMenus()
    for (let i = 0; i < 12; i++) await navigate(`s${i}`)
    const active = tabs.active
    expect(await navigate('s12')).toBe(false)
    expect(tabs.list).toHaveLength(12)
    expect(tabs.active).toBe(active)
    expect(toasts.at(-1).message).toBe('탭은 최대 12개까지 열 수 있습니다. 사용하지 않는 탭을 닫아주세요.')
    expect(await navigate('s0')).toBe(true)
  })

  it('권한 없는 화면은 토스트만 띄운다', async () => {
    expect(await navigate('user-mgmt')).toBe(false)
    expect(tabs.list).toHaveLength(0)
    expect(toasts.at(-1)).toMatchObject({ message: '해당 화면에 대한 권한이 없습니다.', kind: 'err' })
  })

  it('menu-access 403이면 탭을 닫고 토스트를 띄운다', async () => {
    await navigate('dashboard')
    fetch.mockResolvedValue(new Response(JSON.stringify({ code: 'FORBIDDEN', message: 'x' }), { status: 403 }))
    expect(await navigate('hull-list')).toBe(false)
    expect(tabs.list.map((t) => t.token)).toEqual(['dashboard'])
    expect(tabs.active).toBe('dashboard:')
    expect(toasts.at(-1).kind).toBe('err')
  })

  it('닫으면 같은 위치의 다음 탭, 마지막이면 이전 탭이 활성', async () => {
    await navigate('dashboard')
    await navigate('hull-list')
    await navigate('plan-gantt')
    activate('hull-list:')
    closeTab('hull-list:')
    expect(tabs.active).toBe('plan-gantt:')
    closeTab('plan-gantt:')
    expect(tabs.active).toBe('dashboard:')
    closeTab('dashboard:')
    expect(tabs.active).toBeNull()
  })

  it('다른 탭 닫기', async () => {
    await navigate('dashboard')
    await navigate('hull-list')
    closeOthers()
    expect(tabs.list.map((t) => t.key)).toEqual(['hull-list:'])
  })

  it('swp_tabs 형식으로 저장한다', async () => {
    await navigate('hull-list', '8001')
    expect(JSON.parse(sessionStorage.getItem('swp_tabs'))).toEqual({
      tabs: [{ token: 'hull-list', param: '8001' }],
      active: 'hull-list:8001',
    })
  })

  it('SHELL-T05 복구 시 권한 없는 탭을 제외한다', () => {
    sessionStorage.setItem('swp_tabs', JSON.stringify({
      tabs: [{ token: 'user-mgmt', param: null }, { token: 'hull-list', param: '8001' }],
      active: 'user-mgmt:',
    }))
    restoreTabs()
    expect(tabs.list.map((t) => t.key)).toEqual(['hull-list:8001'])
    expect(tabs.active).toBe('hull-list:8001')
    expect(fetch).not.toHaveBeenCalled()
  })

  it('복구할 탭이 없으면 대시보드, 대시보드 권한도 없으면 첫 화면', async () => {
    sessionStorage.setItem('swp_tabs', 'broken-json')
    restoreTabs()
    expect(tabs.active).toBe('dashboard:')
    tabs.list = []
    sessionStorage.clear()
    session.menu = [{ ...item('M10', null), token: null }, item('M11', 'hull-list')]
    restoreTabs()
    expect(tabs.active).toBe('hull-list:')
  })
})
