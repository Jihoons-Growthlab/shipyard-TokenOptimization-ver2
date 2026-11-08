import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api, ApiError, auth } from '../api/client.js'
import { clearSession, loadCodes, logout, session, setToken } from '../stores/session.js'

const respond = (status, body) => new Response(body === undefined ? null : JSON.stringify(body), { status })

describe('API 클라이언트', () => {
  beforeEach(() => {
    clearSession()
    auth.onExpired = vi.fn()
    vi.stubGlobal('fetch', vi.fn())
  })

  it('토큰과 JSON 본문을 보낸다', async () => {
    setToken('t1')
    fetch.mockResolvedValue(respond(200, { ok: true }))
    await api('/api/x', { method: 'POST', body: { a: 1 }, params: { region: '울산' } })
    const [url, init] = fetch.mock.calls[0]
    expect(url).toBe(`/api/x?region=${encodeURIComponent('울산')}`)
    expect(init.headers.Authorization).toBe('Bearer t1')
    expect(init.body).toBe('{"a":1}')
  })

  it('오류 본문을 ApiError로 바꾼다', async () => {
    fetch.mockResolvedValue(respond(400, { code: 'VALIDATION_ERROR', message: '오류', details: { field: 'name' } }))
    const error = await api('/api/x').catch((e) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect([error.status, error.code, error.message, error.details.field]).toEqual([400, 'VALIDATION_ERROR', '오류', 'name'])
  })

  it('토큰 없는 401(로그인 실패)은 세션 만료가 아니다', async () => {
    fetch.mockResolvedValue(respond(401, { code: 'INVALID_CREDENTIALS', message: '틀림' }))
    await expect(api('/api/auth/login', { method: 'POST', body: {} })).rejects.toThrow('틀림')
    expect(auth.onExpired).not.toHaveBeenCalled()
  })

  it('현재 토큰의 401이면 만료 처리한다', async () => {
    setToken('t1')
    fetch.mockResolvedValue(respond(401, {}))
    await api('/api/x').catch(() => {})
    expect(auth.onExpired).toHaveBeenCalledOnce()
  })

  it('이전 세션의 늦은 401은 새 세션을 지우지 않는다', async () => {
    setToken('old')
    let finish
    fetch.mockReturnValue(new Promise((r) => (finish = r)))
    const pending = api('/api/x').catch(() => {})
    setToken('new')
    finish(respond(401, {}))
    await pending
    expect(auth.onExpired).not.toHaveBeenCalled()
  })

  it('네트워크 실패도 화면 표시용 오류로 바꾼다', async () => {
    fetch.mockRejectedValue(new TypeError('failed'))
    await expect(api('/api/x')).rejects.toThrow('서버에 연결할 수 없습니다.')
  })

  it('로그아웃은 API 실패와 무관하게 세션을 지운다', async () => {
    setToken('t1')
    sessionStorage.setItem('swp_tabs', '{}')
    fetch.mockRejectedValue(new TypeError('failed'))
    logout()
    expect(session.token).toBeNull()
    expect(sessionStorage.getItem('swp_token')).toBeNull()
    expect(sessionStorage.getItem('swp_tabs')).toBeNull()
    expect(fetch.mock.calls[0][1].headers.Authorization).toBe('Bearer t1')
  })

  it('공통 코드는 세션당 한 번 불러온다', async () => {
    fetch.mockImplementation(async () => respond(200, { A: [] }))
    await Promise.all([loadCodes(), loadCodes()])
    await loadCodes()
    expect(fetch).toHaveBeenCalledOnce()
    clearSession()
    await loadCodes()
    expect(fetch).toHaveBeenCalledTimes(2)
  })
})
