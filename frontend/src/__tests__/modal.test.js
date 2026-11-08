import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import BaseModal from '../components/BaseModal.vue'
import { session } from '../stores/session.js'
import { navigate, tabs } from '../stores/tabs.js'

const mountModal = () => mount(BaseModal, { props: { title: '상세' }, attachTo: document.body })
const esc = () => document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))

describe('SHELL-T04 모달', () => {
  let wrappers
  beforeEach(() => {
    wrappers = []
    document.body.innerHTML = ''
  })
  afterEach(() => wrappers.forEach((w) => w.unmount()))

  it('Esc·닫기 버튼·배경 클릭으로 닫는다', async () => {
    const w = mountModal()
    wrappers.push(w)
    esc()
    document.querySelector('.modal-head button').click()
    document.querySelector('.modal-back').click()
    document.querySelector('.modal-head').click() // 패널 안쪽 클릭은 닫지 않는다
    expect(w.emitted('close')).toHaveLength(3)
  })

  it('겹치면 Esc는 맨 위만 닫는다', () => {
    const lower = mountModal()
    const upper = mountModal()
    wrappers.push(lower, upper)
    esc()
    expect(upper.emitted('close')).toHaveLength(1)
    expect(lower.emitted('close')).toBeUndefined()
  })

  it('화면 이동 후 닫힌다', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(null, { status: 204 })))
    session.menu = [{ menu_id: 'M11', token: 'hull-list', title: '호선 목록' }]
    tabs.list = []
    const w = mountModal()
    wrappers.push(w)
    await navigate('hull-list')
    await nextTick()
    expect(w.emitted('close')).toHaveLength(1)
  })
})
