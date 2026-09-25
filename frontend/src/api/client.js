import axios from 'axios'

const api = axios.create({ baseURL: import.meta.env.VITE_API_BASE_URL || '', timeout: 90000 })

api.interceptors.request.use((config) => {
  const t = localStorage.getItem('ai_token')
  if (t) config.headers.Authorization = `Bearer ${t}`
  return config
})

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('ai_token')
      localStorage.removeItem('ai_user')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  },
)

export const authApi = {
  login: (email, password) => {
    const f = new URLSearchParams()
    f.append('username', email); f.append('password', password)
    return api.post('/auth/login', f, { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } })
  },
}

export const adminApi = {
  authorities: () => api.get('/admin/authorities'),
  createAuthority: data => api.post('/admin/authorities', data),
  users: () => api.get('/admin/users'),
  createUser: data => api.post('/admin/users', data),
  updateUser: (id, data) => api.patch(`/admin/users/${id}`, data),
  resetUserPassword: (id, newPassword) => api.patch(`/admin/users/${id}/password`, { new_password: newPassword }),
  updateAuthorityModules: (id, enabledModules) => api.patch(`/admin/authorities/${id}/modules`, { enabled_modules: enabledModules }),
  dataOverview: () => api.get('/admin/data-overview'),
  deleteAuthority: id => api.delete(`/admin/authorities/${id}`),
  deleteUser: id => api.delete(`/admin/users/${id}`),
  uploads: authorityId => api.get(`/admin/authorities/${authorityId}/uploads`),
  deleteUpload: (authorityId, dataset, target) => api.delete(`/admin/authorities/${authorityId}/datasets/${dataset}`, { data: target }),
}

export const assetsApi = {
  list: (params) => api.get('/assets/', { params }),
  uploadScanner: (file) => { const fd = new FormData(); fd.append('file', file); return api.post('/assets/upload/scanner', fd) },
  uploadCvi: (file) => { const fd = new FormData(); fd.append('file', file); return api.post('/assets/upload/cvi', fd) },
  uploadReactive: (file) => { const fd = new FormData(); fd.append('file', file); return api.post('/assets/upload/reactive', fd) },
  aliases: () => api.get('/assets/schema/aliases'),
  exportUrl: () => '/assets/export',
  uploadScannerRaw:  (file) => { const fd = new FormData(); fd.append('file', file); return api.post('/assets/upload/scanner/raw',  fd, { timeout: 300000 }) },
  uploadCviRaw:      (file) => { const fd = new FormData(); fd.append('file', file); return api.post('/assets/upload/cvi/raw',      fd, { timeout: 300000 }) },
  uploadScrimRaw:    (file) => { const fd = new FormData(); fd.append('file', file); return api.post('/assets/upload/scrim/raw',    fd, { timeout: 300000 }) },
  uploadReactiveRaw: (file) => { const fd = new FormData(); fd.append('file', file); return api.post('/assets/upload/reactive/raw', fd, { timeout: 300000 }) },
  uploadNetwork: (file) => { const fd = new FormData(); fd.append('file', file); return api.post('/assets/upload/network', fd, { timeout: 300000 }) },
  networkStats: () => api.get('/assets/network-stats'),
  myDatasets: (params) => api.get('/assets/my-datasets', { params }),
  mapData: (params) => api.get('/assets/map-data', { params }),
}

export const analysisApi = {
  run: () => api.post('/analysis/run'),
  latest: () => api.get('/analysis/latest'),
  query: (question, history) => api.post('/analysis/query', { question, conversation_history: history }),
  stats: () => api.get('/analysis/stats'),
  assetNarrative: (nsg_ref) => api.post(`/analysis/asset/${encodeURIComponent(nsg_ref)}`),
  vaisalaSectionNarrative: (sectionId) => api.post(`/analysis/vaisala/${sectionId}`),
}

export const vaisalaApi = {
  uploadRaw: (file, networkKey, weights, dedupStrategy = 'latest') => {
    const fd = new FormData()
    fd.append('file', file)
    let url = `/vaisala/upload/raw?network_key=${networkKey}&dedup_strategy=${dedupStrategy}`
    if (weights) url += `&weights_json=${encodeURIComponent(JSON.stringify(weights))}`
    return api.post(url, fd, { timeout: 300000 })
  },
  uploadShp: (file, networkKey) => {
    const fd = new FormData()
    fd.append('file', file)
    return api.post(`/vaisala/upload/shp?network_key=${networkKey}`, fd, { timeout: 300000 })
  },
  surveys: () => api.get('/vaisala/surveys'),
  uploadNetworkGeometry: (file, sectionField) => {
    const fd = new FormData()
    fd.append('file', file)
    let url = '/vaisala/network-geometry/upload'
    if (sectionField) url += `?section_field=${encodeURIComponent(sectionField)}`
    return api.post(url, fd, { timeout: 300000 })
  },
  currentNetworkGeometry: () => api.get('/vaisala/network-geometry/current'),
  networkFeatures: (surveyId, view = {}) => api.get('/vaisala/network-geometry/features', { params: { survey_id: surveyId, merge_scale: view.mergeScale || 'section', split: view.split || 'combined', treatment_mode: view.treatmentMode || 'defect' } }),
  deleteNetworkGeometry: (geometryId) => api.delete(`/vaisala/network-geometry/${geometryId}`),
  stats: (surveyId, view = {}) => api.get(`/vaisala/surveys/${surveyId}/stats`, { params: { merge_scale: view.mergeScale || 'section', split: view.split || 'combined', treatment_mode: view.treatmentMode || 'defect' } }),
  sections: (surveyId, params) => api.get(`/vaisala/surveys/${surveyId}/sections`, { params }),
  allSections: (surveyId, view = {}) => api.get(`/vaisala/surveys/${surveyId}/sections/all`, { params: { merge_scale: view.mergeScale || 'section', split: view.split || 'combined', treatment_mode: view.treatmentMode || 'defect' } }),
  exportUrl: (surveyId, view = {}) => `/vaisala/surveys/${surveyId}/export?merge_scale=${view.mergeScale || 'section'}&split=${view.split || 'combined'}&treatment_mode=${view.treatmentMode || 'defect'}`,
}

export default api
