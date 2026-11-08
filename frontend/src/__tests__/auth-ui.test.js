import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import LoginView from '../views/LoginView.vue'
import PageHeader from '../components/PageHeader.vue'
import { clearSession, session } from '../stores/session.js'
import { toasts } from '../stores/toast.js'

const json = (status, body) => new Response(JSON.stringify(body), { status })

async function mountLogin() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/', component: { template: '<i/>' } }, { path: '/login', component: LoginView }],
  })
  router.push('/login')
  await router.isReady()
  return { wrapper: mount(LoginView, { global: { plugins: [router] } }), router }
}

describe('로그인 화면', () => {
  beforeEach(() => {
    clearSession()
    toasts.splice(0)
    vi.stubGlobal('fetch', vi.fn())
  })

  it('일반 계정은 토큰을 저장하고 이동한다', async () => {
    fetch.mockResolvedValue(json(200, { otp_required: false, access_token: 'tok' }))
    const { wrapper, router } = await mountLogin()
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(session.token).toBe('tok')
    expect(sessionStorage.getItem('swp_token')).toBe('tok')
    expect(router.currentRoute.value.path).toBe('/')
  })

  it('실패 메시지를 카드 안에 표시한다', async () => {
    fetch.mockResolvedValue(json(401, { code: 'INVALID_CREDENTIALS', message: '아이디 또는 비밀번호가 올바르지 않습니다.' }))
    const { wrapper } = await mountLogin()
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(wrapper.find('.auth-err').text()).toBe('아이디 또는 비밀번호가 올바르지 않습니다.')
    expect(session.token).toBeNull()
  })

  it('OTP 계정은 2차 화면으로 가고 otp_token을 세션에 넣지 않는다', async () => {
    fetch.mockResolvedValueOnce(json(200, { otp_required: true, otp_token: 'otp', expires_in: 300 }))
    const { wrapper } = await mountLogin()
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(wrapper.find('h1').text()).toBe('구글 2차 인증')
    expect(session.token).toBeNull()
    fetch.mockResolvedValueOnce(json(200, { otp_required: false, access_token: 'full' }))
    await wrapper.find('.otp-input').setValue('123456')
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(fetch.mock.calls[1][1].headers.Authorization).toBe('Bearer otp')
    expect(session.token).toBe('full')
  })

  it('가입 성공 시 로그인으로 돌아가 토스트를 띄운다', async () => {
    fetch.mockResolvedValue(json(201, { emp_no: 'hong', status: 'pending', message: '가입 신청 완료. 관리자 승인 후 로그인할 수 있습니다.' }))
    const { wrapper } = await mountLogin()
    await wrapper.find('.auth-link').trigger('click')
    expect(wrapper.find('h1').text()).toBe('회원가입')
    expect(wrapper.findAll('.auth-fields input')).toHaveLength(8)
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(wrapper.find('h1').text()).toBe('조선소 통합관리')
    expect(toasts.at(-1).message).toBe('가입 신청 완료. 관리자 승인 후 로그인할 수 있습니다.')
  })

  it('가입 검증 오류는 카드에 표시하고 입력을 유지한다', async () => {
    fetch.mockResolvedValue(json(400, { code: 'VALIDATION_ERROR', message: '성과 이름을 입력하세요.', details: { field: 'name' } }))
    const { wrapper } = await mountLogin()
    await wrapper.find('.auth-link').trigger('click')
    await wrapper.find('input').setValue('홍')
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(wrapper.find('.auth-err').text()).toBe('성과 이름을 입력하세요.')
    expect(wrapper.find('input').element.value).toBe('홍')
  })
})

describe('조회 전용 배지', () => {
  it('can_write에 따라 표시한다', () => {
    session.menu = [{ token: 'a', title: '가', can_write: false }, { token: 'b', title: '나', can_write: true }]
    expect(mount(PageHeader, { props: { token: 'a' } }).text()).toContain('조회 전용')
    expect(mount(PageHeader, { props: { token: 'b' } }).text()).not.toContain('조회 전용')
  })
})
