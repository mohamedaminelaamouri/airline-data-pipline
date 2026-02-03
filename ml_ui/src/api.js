const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001'

export async function getSummary() {
  const res = await fetch(`${API_URL}/stats/summary`)
  return res.json()
}

export async function getPredictions(params = {}) {
  const url = new URL(`${API_URL}/predictions`)
  Object.entries(params).forEach(([k, v]) => {
    if (v) url.searchParams.append(k, v)
  })
  const res = await fetch(url)
  return res.json()
}

export async function getGlobalExplainability() {
  const res = await fetch(`${API_URL}/explainability/global`)
  return res.json()
}

export async function getRouteExplainability(carrier, airport) {
  const url = new URL(`${API_URL}/explainability/route`)
  url.searchParams.append('carrier', carrier)
  url.searchParams.append('airport', airport)
  const res = await fetch(url)
  return res.json()
}

export async function getMonitoring() {
  const res = await fetch(`${API_URL}/monitoring`)
  return res.json()
}

export async function getMetadata() {
  const res = await fetch(`${API_URL}/metadata`)
  return res.json()
}

export async function getMonthlyStats() {
  const res = await fetch(`${API_URL}/stats/monthly`)
  return res.json()
}
