// 统一 HTTP 封装：Bearer 注入、access 过期自动刷新一次、统一 {code,message,data} 解包。
// 开发期经 Vite proxy 转发到 127.0.0.1:8000，生产同源，无需写绝对地址。
import { useAuthStore } from '../stores/auth'

const BASE = '/api/v1'

// 共享同一个 refresh，避免并发请求各自刷新
let refreshPromise = null

async function perform(url, options) {
  const res = await fetch(url, options)
  let data = null
  try {
    data = await res.json()
  } catch {
    /* 非 JSON（如图片流）由调用方用 raw 处理 */
  }
  return { res, data }
}

function buildOptions(method, body, headers) {
  const options = { method, headers: { ...headers } }
  if (body !== undefined && body !== null) {
    if (body instanceof FormData) {
      options.body = body
    } else {
      options.headers['Content-Type'] = 'application/json'
      options.body = JSON.stringify(body)
    }
  }
  return options
}

async function request(method, path, { body, query, auth = true, raw = false } = {}) {
  const authStore = useAuthStore()
  const url = BASE + path + (query ? '?' + new URLSearchParams(query).toString() : '')
  const headers = {}
  if (auth && authStore.accessToken) {
    headers['Authorization'] = 'Bearer ' + authStore.accessToken
  }

  let options = buildOptions(method, body, headers)
  let { res, data } = await perform(url, options)

  // access 过期：用 refresh 换一次，重试原请求（只重试一次）
  if (res.status === 401 && auth && authStore.refreshToken && !path.includes('/auth/refresh')) {
    refreshPromise = refreshPromise || authStore.tryRefresh()
    const ok = await refreshPromise
    refreshPromise = null
    if (ok) {
      headers['Authorization'] = 'Bearer ' + authStore.accessToken
      options = buildOptions(method, body, headers)
      const retried = await perform(url, options)
      res = retried.res
      data = retried.data
    }
  }

  if (raw) {
    if (!res.ok) {
      const err = new Error(data?.message || '请求失败')
      err.status = res.status
      err.data = data
      throw err
    }
    return { res, data }
  }

  if (!res.ok || !data || data.code !== 0) {
    const err = new Error(data?.message || `请求失败（${res.status}）`)
    err.code = data?.code
    err.status = res.status
    err.data = data?.data
    throw err
  }
  return data.data
}

export const http = {
  get: (path, opts) => request('GET', path, opts),
  post: (path, body, opts) => request('POST', path, { ...opts, body }),
  put: (path, body, opts) => request('PUT', path, { ...opts, body }),
  del: (path, opts) => request('DELETE', path, opts),
}

// 带鉴权拉取二进制（图片附件 view 接口需要 Authorization 头，<img> 标签无法带 token）
export async function fetchBlob(url) {
  const authStore = useAuthStore()
  const doFetch = (token) =>
    fetch(url, { headers: token ? { Authorization: 'Bearer ' + token } : {} })
  let res = await doFetch(authStore.accessToken)
  // access 过期：复用全局刷新一次后重试，避免令牌过期瞬间图片被误判为加载失败
  if (res.status === 401 && authStore.refreshToken) {
    refreshPromise = refreshPromise || authStore.tryRefresh()
    const ok = await refreshPromise
    refreshPromise = null
    if (ok) res = await doFetch(authStore.accessToken)
  }
  if (!res.ok) throw new Error('图片加载失败')
  return res.blob()
}
