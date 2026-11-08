import { reactive } from 'vue'

export const toasts = reactive([])
let id = 0

function show(message, kind) {
  const item = { id: ++id, message, kind }
  toasts.push(item)
  setTimeout(() => {
    const at = toasts.findIndex((t) => t.id === item.id)
    if (at >= 0) toasts.splice(at, 1)
  }, 3500)
}

export const toast = {
  info: (message) => show(message, ''),
  error: (message) => show(message, 'err'),
  success: (message) => show(message, 'ok'),
}
