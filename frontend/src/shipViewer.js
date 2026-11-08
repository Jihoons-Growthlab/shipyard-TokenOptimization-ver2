// Unity 샘플 호선 뷰어 수명주기. 인스턴스는 동시에 하나만 둔다.
export const BUILD_BASE = '/unity/ship-viewer/Build/'
export const NO_BUILD = '3D 뷰어 빌드를 찾을 수 없습니다.'
export const NO_RESPONSE = '3D 뷰어가 응답하지 않습니다.'
export const READY_TIMEOUT = 20000

let loader = null
let tail = Promise.resolve()

export const firstLine = (e) => String(e?.message ?? e ?? '').split('\n')[0]
const settle = (p) => Promise.resolve(p).then((v) => v, () => null)

async function loadConfig() {
  const res = await fetch(`${BUILD_BASE}build.json`, { cache: 'no-store' })
  try {
    if (!res.ok) throw new Error()
    return await res.json()
  } catch {
    // Vite는 없는 파일에 index.html(SPA 폴백)을 돌려준다.
    throw new Error(NO_BUILD)
  }
}

function loadLoader(src) {
  loader ??= new Promise((resolve, reject) => {
    const tag = document.createElement('script')
    tag.src = src
    tag.onload = resolve
    tag.onerror = () => {
      tag.remove()
      loader = null
      reject(new Error(`3D 뷰어 로더를 불러오지 못했습니다: ${src}`))
    }
    document.head.append(tag)
  })
  return loader
}

// canvas에는 id가 있어야 한다(Unity가 '#'+id로 찾는다).
export function startViewer(canvas, onProgress) {
  const prev = tail
  let release
  tail = new Promise((r) => (release = r))
  const s = { instance: null, closed: false }
  let creating = null
  let banner = null
  let onReady = null

  s.ready = (async () => {
    await prev
    if (s.closed) throw new Error('closed')
    const cfg = await loadConfig()
    await loadLoader(BUILD_BASE + cfg.loaderUrl)
    if (s.closed) throw new Error('closed')
    const signaled = new Promise((resolve) => {
      onReady = resolve
      canvas.addEventListener('shipviewer-ready', resolve, { once: true })
    })
    let fail
    banner = new Promise((_, reject) => (fail = reject))
    banner.catch(() => {})
    creating = window.createUnityInstance(
      canvas,
      {
        dataUrl: BUILD_BASE + cfg.dataUrl,
        frameworkUrl: BUILD_BASE + cfg.frameworkUrl,
        codeUrl: BUILD_BASE + cfg.codeUrl,
        companyName: cfg.companyName,
        productName: cfg.productName,
        productVersion: cfg.productVersion,
        devicePixelRatio: Math.min(window.devicePixelRatio || 1, 2),
        // 6000.5 로더가 호출한다. type=error면 시작 실패다.
        showBanner: (msg, type) => type === 'error' && fail(new Error(msg)),
      },
      (p) => onProgress?.(p),
    )
    s.instance = await Promise.race([creating, banner])
    if (s.closed) throw new Error('closed')
    let timer
    const timeout = new Promise((_, reject) => (timer = setTimeout(() => reject(new Error(NO_RESPONSE)), READY_TIMEOUT)))
    try {
      await Promise.race([signaled, timeout])
    } finally {
      clearTimeout(timer)
    }
    return s.instance
  })()
  s.ready.catch(() => {})

  s.close = () =>
    (s.closing ??= (async () => {
      s.closed = true
      await prev
      if (onReady) canvas.removeEventListener('shipviewer-ready', onReady)
      // 로딩 중에 닫히면 늦게 온 인스턴스를 받아 바로 종료한다.
      const inst = s.instance ?? (creating && (await settle(Promise.race([creating, banner]))))
      if (inst) {
        await settle(inst.Quit())
        canvas.getContext('webgl2')?.getExtension('WEBGL_lose_context')?.loseContext()
      }
      release()
    })())

  s.setView = (view) => s.instance?.SendMessage('ShipViewer', 'SetView', view)
  return s
}
