import { api } from './api/client.js'

export const MAX_PDF = 30 * 1024 * 1024
export const STEP_NAME = { 1: '검토', 2: '승인' }
export const RESULT = { WAIT: ['대기', 'warn'], APPROVE: ['승인', 'ok'], REJECT: ['반려', 'bad'] }

// 서버와 같은 PDF 판정. 통과하면 null, 아니면 오류 메시지.
export function checkPdf(file) {
  if (!file.name.toLowerCase().endsWith('.pdf') && file.type !== 'application/pdf') return 'PDF 파일만 업로드할 수 있습니다.'
  if (file.size > MAX_PDF) return '파일 크기는 30MB 이하여야 합니다.'
  return null
}

export const uploadPdf = (drawingId, revNo, file) =>
  api(`/api/drawings/${drawingId}/revisions/${revNo}/pdf`, { method: 'POST', params: { filename: file.name }, body: file })
