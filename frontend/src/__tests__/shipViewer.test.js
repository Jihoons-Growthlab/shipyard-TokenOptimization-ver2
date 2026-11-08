import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

const CFG = {
  loaderUrl: 'v.loader.js', dataUrl: 'v.data', frameworkUrl: 'v.framework.js', codeUrl: 'v.wasm',
  companyName: 'SWP', productName: 'ShipyardViewer', productVersion: '1.0',
}
const jsonRes = (b) => new Response(JSON.stringify(b), { status: 200 })
const htmlRes = () => new Response('<!doctype html><html></html>', { status: 200, headers: { 'Content-Type': 'text/html' } })

let mod
let lose
beforeEach(async () => {
  vi.resetModules()
  mod = await import('../shipViewer.js')
  lose = vi.fn()
  HTMLCanvasElement.prototype.getContext = vi.fn(() => ({ getExtension: () => ({ loseContext: lose }) }))
})
afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
  delete window.createUnityInstance
  document.head.innerHTML = ''
  document.body.innerHTML = ''
})

const loaderTag = () => document.head.querySelector('script')
const tick = async () => {
  for (let i = 0; i < 30; i++) await Promise.resolve()
}
async function fireLoader(type = 'load') {
  await tick()
  loaderTag().dispatchEvent(new Event(type))
  await tick()
}
function canvas() {
  const c = document.createElement('canvas')
  c.id = 'cv'
  document.body.append(c)
  return c
}
function fakeUnity({ ready = true } = {}) {
  const made = []
  window.createUnityInstance = vi.fn((cv, config) => {
    const inst = { Quit: vi.fn(async () => {}), SendMessage: vi.fn(), config }
    made.push(inst)
    if (ready) setTimeout(() => cv.dispatchEvent(new CustomEvent('shipviewer-ready')))
    return Promise.resolve(inst)
  })
  return made
}

describe('3D 뷰어 수명주기', () => {
  it('VIEWER-T04 build.json이 JSON이 아니면 빌드 없음 안내', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => htmlRes()))
    const s = mod.startViewer(canvas())
    await expect(s.ready).rejects.toThrow(mod.NO_BUILD)
    expect(fetch).toHaveBeenCalledWith('/unity/ship-viewer/Build/build.json', { cache: 'no-store' })
  })

  it('VIEWER-T06 로더 실패 시 태그를 지우고 재시도에서 다시 불러온다', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonRes(CFG)))
    const s1 = mod.startViewer(canvas())
    await fireLoader('error')
    await expect(s1.ready).rejects.toThrow('로더')
    expect(loaderTag()).toBeNull()
    await s1.close()

    const made = fakeUnity()
    const s2 = mod.startViewer(canvas())
    await fireLoader()
    expect(await s2.ready).toBe(made[0])
    expect(document.head.querySelectorAll('script')).toHaveLength(1)
    const cfg = made[0].config
    expect(cfg.codeUrl).toBe('/unity/ship-viewer/Build/v.wasm')
    expect(cfg.devicePixelRatio).toBeLessThanOrEqual(2)

    // 로더는 첫 진입에 한 번만 불러온다.
    await s2.close()
    const s3 = mod.startViewer(canvas())
    expect(await s3.ready).toBe(made[1])
    expect(document.head.querySelectorAll('script')).toHaveLength(1)
  })

  it('VIEWER-T06 종료 시 Quit 후 WebGL 컨텍스트를 해제하고 시점은 SendMessage로 보낸다', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonRes(CFG)))
    const made = fakeUnity()
    const s = mod.startViewer(canvas())
    await fireLoader()
    await s.ready
    s.setView('top')
    expect(made[0].SendMessage).toHaveBeenCalledWith('ShipViewer', 'SetView', 'top')
    await s.close()
    expect(made[0].Quit).toHaveBeenCalledTimes(1)
    expect(lose).toHaveBeenCalledTimes(1)
  })

  it('VIEWER-T05 로딩 중 닫으면 늦게 온 인스턴스를 바로 종료하고 다음 시작은 종료를 기다린다', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonRes(CFG)))
    let finish
    const late = { Quit: vi.fn(async () => {}), SendMessage: vi.fn() }
    window.createUnityInstance = vi.fn(() => new Promise((r) => (finish = r)))
    const s1 = mod.startViewer(canvas())
    await fireLoader()
    expect(window.createUnityInstance).toHaveBeenCalledTimes(1)
    const closing = s1.close()

    const made = []
    const s2 = mod.startViewer(canvas())
    await flushPromises()
    expect(window.createUnityInstance).toHaveBeenCalledTimes(1) // 이전 종료 전에는 시작하지 않는다.

    window.createUnityInstance = vi.fn((cv) => {
      const inst = { Quit: vi.fn(async () => {}), SendMessage: vi.fn() }
      made.push(inst)
      setTimeout(() => cv.dispatchEvent(new CustomEvent('shipviewer-ready')))
      return Promise.resolve(inst)
    })
    finish(late)
    await closing
    expect(late.Quit).toHaveBeenCalledTimes(1)
    expect(await s2.ready).toBe(made[0])
  })

  it('VIEWER-T04 준비 신호가 20초 안에 없으면 응답 없음', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonRes(CFG)))
    fakeUnity({ ready: false })
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    const s = mod.startViewer(canvas())
    await fireLoader()
    const result = expect(s.ready).rejects.toThrow(mod.NO_RESPONSE)
    await vi.advanceTimersByTimeAsync(mod.READY_TIMEOUT)
    await result
  })

  it('VIEWER-T04 showBanner error면 실패하고 오류는 첫 줄만', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonRes(CFG)))
    window.createUnityInstance = vi.fn((cv, config) => {
      config.showBanner('경고', 'warning')
      config.showBanner('wasm 실패\n  at stack', 'error')
      return new Promise(() => {})
    })
    const s = mod.startViewer(canvas())
    await fireLoader()
    const err = await s.ready.catch((e) => e)
    expect(mod.firstLine(err)).toBe('wasm 실패')
  })
})

describe('3D 보기 화면', () => {
  it('VIEWER-T04 빌드 없음 안내 후 재시도로 복구, 준비 전 시점 버튼 비활성', async () => {
    const { default: ShipViewer3D } = await import('../components/ShipViewer3D.vue')
    let build = false
    vi.stubGlobal('fetch', vi.fn(async () => (build ? jsonRes(CFG) : htmlRes())))
    const made = fakeUnity()
    const w = mount(ShipViewer3D, { attachTo: document.body })
    await flushPromises()
    expect(w.text()).toContain('3D 뷰어를 불러오지 못했습니다.')
    expect(w.text()).toContain(mod.NO_BUILD)
    expect(w.text()).toContain('예시 모델 — 실제 호선 형상과 다름')
    const views = () => w.findAll('.views button')
    expect(views().every((b) => b.element.disabled)).toBe(true)
    const firstCanvas = w.find('canvas').element

    build = true
    await w.find('.cover button').trigger('click')
    await fireLoader()
    await new Promise((r) => setTimeout(r))
    await flushPromises()
    expect(w.find('canvas').element).not.toBe(firstCanvas)
    expect(w.find('canvas').attributes('id')).toBeTruthy()
    expect(w.find('.cover').exists()).toBe(false)
    expect(views().some((b) => b.element.disabled)).toBe(false)
    await views()[1].trigger('click')
    expect(made[0].SendMessage).toHaveBeenCalledWith('ShipViewer', 'SetView', 'side')

    w.unmount()
    await flushPromises()
    expect(made[0].Quit).toHaveBeenCalledTimes(1)
  })
})
