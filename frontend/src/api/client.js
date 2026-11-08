export class ApiError extends Error {
  constructor(status, body) {
    super(body?.message ?? '요청을 처리하지 못했습니다.')
    this.status = status
    this.code = body?.code ?? 'UNKNOWN'
    this.details = body?.details ?? {}
  }
}

// 세션 스토어·라우터가 채운다. 이 파일이 그쪽을 import하면 순환 참조가 된다.
export const auth = { token: () => null, onExpired: () => {} }

// body가 Blob(File)이면 그대로 보낸다. blob: true면 응답을 Blob으로 돌려준다.
export async function api(path, { method = 'GET', body, params, token, blob = false } = {}) {
  const used = token ?? auth.token()
  const query = params ? `?${new URLSearchParams(params)}` : ''
  const headers = {}
  if (used) headers.Authorization = `Bearer ${used}`
  const raw = body instanceof Blob
  if (raw) headers['Content-Type'] = body.type || 'application/octet-stream'
  else if (body !== undefined) headers['Content-Type'] = 'application/json'

  let res
  try {
    res = await fetch(path + query, {
      method,
      headers,
      body: raw || body === undefined ? body : JSON.stringify(body),
    })
  } catch {
    throw new ApiError(0, { code: 'NETWORK', message: '서버에 연결할 수 없습니다.' })
  }
  if (res.status === 204) return null
  if (res.ok && blob) return res.blob()
  const data = await res.json().catch(() => null)
  if (res.ok) return data
  // 늦게 도착한 이전 세션의 401이 새 세션을 지우지 않게 현재 토큰일 때만 만료 처리한다.
  if (res.status === 401 && used && used === auth.token()) auth.onExpired()
  throw new ApiError(res.status, data)
}
