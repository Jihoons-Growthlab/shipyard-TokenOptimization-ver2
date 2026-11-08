import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import HullList from '../screens/HullList.vue'
import HullDetailModal from '../components/HullDetailModal.vue'
import ProgressInput from '../screens/ProgressInput.vue'
import { session } from '../stores/session.js'

const json = (body) => new Response(JSON.stringify(body), { status: 200 })
const hull = (no, extra = {}) => ({ hull_no: no, hull_nm: `선 ${no}`, hull_status: 'BUILD', progress: null, delay_count: 0, ...extra })

function setMenu(canWrite) {
  session.menu = [
    { menu_id: 'M11', token: 'hull-list', title: '호선 목록', can_write: canWrite },
    { menu_id: 'M22', token: 'progress', title: '공정 실적', can_write: canWrite },
  ]
  session.me = { emp_no: 'park.pm' }
}

describe('호선 목록', () => {
  let wrapper
  afterEach(() => {
    wrapper?.unmount()
    document.body.innerHTML = ''
  })

  it('HULL-T08 조회 전용은 등록 버튼이 없고 상세 저장이 비활성', async () => {
    setMenu(false)
    vi.stubGlobal('fetch', vi.fn(async (url) => json(url.startsWith('/api/codes') ? {} : url === '/api/hulls/8001' ? hull('8001') : [hull('8001')])))
    wrapper = mount(HullList, { props: { token: 'hull-list' }, attachTo: document.body })
    await flushPromises()
    expect(wrapper.text()).toContain('조회 전용')
    expect(wrapper.text()).not.toContain('+ 호선 등록')
    expect(wrapper.text()).toContain('계획 없음')
    expect(wrapper.text()).toContain('총 1척')
    await wrapper.find('tbody tr').trigger('dblclick')
    await flushPromises()
    const save = [...document.querySelectorAll('.modal button')].find((b) => b.textContent === '저장')
    expect(save.disabled).toBe(true)
  })

  it('HULL-T01 늦게 도착한 이전 조회가 최신 결과를 덮지 않는다', async () => {
    setMenu(true)
    let release
    vi.stubGlobal('fetch', vi.fn((url) => {
      if (url.startsWith('/api/codes')) return Promise.resolve(json({}))
      if (url.includes('q=')) return Promise.resolve(json([hull('8003')]))
      return new Promise((r) => (release = () => r(json([hull('8001'), hull('8002')]))))
    }))
    wrapper = mount(HullList, { props: { token: 'hull-list' } })
    await wrapper.find('input.q').setValue('8003')
    await wrapper.findAll('button').find((b) => b.text() === '조회').trigger('click')
    await flushPromises()
    release()
    await flushPromises()
    expect(wrapper.findAll('tbody tr')).toHaveLength(1)
    expect(wrapper.text()).toContain('8003')
  })
})

describe('호선 상세 모달', () => {
  afterEach(() => (document.body.innerHTML = ''))

  it('조회 완료 전에는 폼을 비활성화하고, 서브탭 전환 시 재조회한다', async () => {
    let release
    const calls = []
    vi.stubGlobal('fetch', vi.fn((url) => {
      calls.push(url)
      if (url === '/api/hulls/8001' && !release) return new Promise((r) => (release = () => r(json(hull('8001')))))
      return Promise.resolve(json(url.endsWith('/blocks') ? [] : hull('8001')))
    }))
    const w = mount(HullDetailModal, { props: { hullNo: '8001', writable: true }, attachTo: document.body })
    await flushPromises()
    expect(document.querySelector('.modal fieldset').disabled).toBe(true)
    release()
    await flushPromises()
    expect(document.querySelector('.modal fieldset').disabled).toBe(false)
    expect(document.querySelector('.modal input').value).toBe('8001')
    const tab = (label) => [...document.querySelectorAll('.subtab')].find((b) => b.textContent.trim() === label)
    tab('블록 구성').click()
    await flushPromises()
    expect(document.body.textContent).toContain('블록이 없습니다.')
    tab('블록 구성').click()
    await flushPromises()
    expect(calls.filter((u) => u.endsWith('/blocks'))).toHaveLength(2)
    expect(document.querySelector('.subtab.on').textContent.trim()).toBe('블록 구성')
    w.unmount()
  })

  it('VIEWER-T01 3D 탭 왕복 시 작성 내용 유지, 다른 탭은 재조회, 신규에는 탭 없음', async () => {
    const calls = []
    vi.stubGlobal('fetch', vi.fn(async (url) => {
      calls.push(url)
      if (url.includes('build.json')) return new Response('<!doctype html>', { status: 200 })
      return json(url.endsWith('/milestones') ? [] : hull('8001'))
    }))
    const w = mount(HullDetailModal, { props: { hullNo: '8001', writable: true }, attachTo: document.body })
    await flushPromises()
    const tab = (label) => [...document.querySelectorAll('.subtab')].find((b) => b.textContent.trim() === label)
    const name = () => document.querySelectorAll('.modal input')[1]
    name().value = '작성 중'
    name().dispatchEvent(new Event('input'))
    tab('3D 보기').click()
    await flushPromises()
    expect(document.body.textContent).toContain('3D 뷰어 빌드를 찾을 수 없습니다.')
    expect(document.body.textContent).toContain('Demo Ship 01')
    tab('기본정보').click()
    await flushPromises()
    expect(name().value).toBe('작성 중')
    expect(calls.filter((u) => u === '/api/hulls/8001')).toHaveLength(1)
    tab('주요일정').click()
    await flushPromises()
    expect(calls.filter((u) => u.endsWith('/milestones'))).toHaveLength(1)
    w.unmount()

    const n = mount(HullDetailModal, { props: { hullNo: null, writable: true }, attachTo: document.body })
    expect(document.body.textContent).not.toContain('3D 보기')
    n.unmount()
  })
})

describe('공정 실적', () => {
  let wrapper
  beforeEach(() => setMenu(true))
  afterEach(() => wrapper?.unmount())

  const routes = (url) => {
    if (url === '/api/progress-hulls') return { hulls: [{ hull_no: '8001', hull_nm: 'A' }, { hull_no: '8002', hull_nm: 'B' }], default_hull_no: '8001' }
    if (url === '/api/users/options') return [{ emp_no: 'park.pm', display_name: '박공정' }]
    if (url.startsWith('/api/codes')) return {}
    if (url.includes('progress-targets')) return { today: '2026-10-19', plans: [{ plan_id: 7, label: '[101] 도장', progress_rate: 30, plan_status: 'WORK' }] }
    return { plan: { plan_id: 7, label: '[101] 도장', progress_rate: 30, plan_status: 'WORK' }, history: [] }
  }

  it('PROG-T01 선택 전 안내, 선택 시 폼 기본값, 호선 변경 시 선택 해제', async () => {
    vi.stubGlobal('fetch', vi.fn(async (url) => json(routes(url))))
    wrapper = mount(ProgressInput, { props: { token: 'progress' } })
    await flushPromises()
    expect(wrapper.text()).toContain('위 목록에서 공정을 선택하세요.')
    await wrapper.find('tbody tr').trigger('click')
    await flushPromises()
    expect(wrapper.find('input[type=date]').element.value).toBe('2026-10-19')
    expect(wrapper.find('input[type=number]').element.value).toBe('30')
    expect(wrapper.find('.detail select').element.value).toBe('park.pm')
    expect(wrapper.text()).toContain('실적 이력이 없습니다.')
    await wrapper.find('select').setValue('8002')
    await flushPromises()
    expect(wrapper.text()).toContain('위 목록에서 공정을 선택하세요.')
  })

  it('PROG-T06 조회 전용은 입력 폼이 없다', async () => {
    setMenu(false)
    vi.stubGlobal('fetch', vi.fn(async (url) => json(routes(url))))
    wrapper = mount(ProgressInput, { props: { token: 'progress' } })
    await flushPromises()
    await wrapper.find('tbody tr').trigger('click')
    await flushPromises()
    expect(wrapper.find('.detail form').exists()).toBe(false)
    expect(wrapper.text()).toContain('실적 이력')
  })
})
