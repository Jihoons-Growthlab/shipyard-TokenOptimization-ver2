import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MAX_PDF, checkPdf, uploadPdf } from '../drawing.js'
import { setToken } from '../stores/session.js'

const file = (name, type, size = 10) => {
  const f = new File(['x'], name, { type })
  Object.defineProperty(f, 'size', { value: size })
  return f
}

describe('PDF 클라이언트 검사', () => {
  it('확장자 또는 MIME이 PDF면 통과', () => {
    expect(checkPdf(file('a.PDF', ''))).toBeNull()
    expect(checkPdf(file('a.bin', 'application/pdf'))).toBeNull()
    expect(checkPdf(file('a.txt', 'text/plain'))).toBe('PDF 파일만 업로드할 수 있습니다.')
  })
  it('30MiB 초과는 거절', () => {
    expect(checkPdf(file('a.pdf', '', MAX_PDF))).toBeNull()
    expect(checkPdf(file('a.pdf', '', MAX_PDF + 1))).toBe('파일 크기는 30MB 이하여야 합니다.')
  })
})

describe('PDF 업로드', () => {
  beforeEach(() => vi.stubGlobal('fetch', vi.fn()))
  it('원본 바이트와 파일 형식, 파일명을 보낸다', async () => {
    setToken('t1')
    fetch.mockResolvedValue(new Response('{"has_file":true}', { status: 200 }))
    const f = new File(['%PDF-'], '도면.pdf', { type: 'application/pdf' })
    await uploadPdf(3, 1, f)
    const [url, init] = fetch.mock.calls[0]
    expect(url).toBe(`/api/drawings/3/revisions/1/pdf?filename=${encodeURIComponent('도면.pdf')}`)
    expect(init.body).toBe(f)
    expect(init.headers['Content-Type']).toBe('application/pdf')
  })
})
