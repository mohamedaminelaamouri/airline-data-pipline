import React, { useEffect, useState, useMemo, useCallback } from 'react'
import {
  getSummary,
  getPredictions,
  getGlobalExplainability,
  getRouteExplainability,
  getMonitoring,
  getMetadata,
  getMonthlyStats
} from './api'

// Icons as SVG components
const Icons = {
  Home: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/>
      <polyline points="9,22 9,12 15,12 15,22"/>
    </svg>
  ),
  Chart: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>
    </svg>
  ),
  Brain: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 2a4 4 0 014 4c0 1.1-.9 2-2 2h-4c-1.1 0-2-.9-2-2a4 4 0 014-4z"/>
      <path d="M8 8v8a4 4 0 008 0V8"/>
      <circle cx="12" cy="13" r="1"/>
    </svg>
  ),
  Activity: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="22,12 18,12 15,21 9,3 6,12 2,12"/>
    </svg>
  ),
  Plane: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M17.8 19.2L16 11l3.5-3.5C21 6 21.5 4 21 3c-1-.5-3 0-4.5 1.5L13 8 4.8 6.2c-.5-.1-.9.1-1.1.5l-.3.5c-.2.5-.1 1 .3 1.3L9 12l-2 3H4l-1 1 3 2 2 3 1-1v-3l3-2 3.5 5.3c.3.4.8.5 1.3.3l.5-.2c.4-.3.6-.7.5-1.2z"/>
    </svg>
  ),
  AlertTriangle: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
      <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
    </svg>
  ),
  TrendingUp: () => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="23,6 13.5,15.5 8.5,10.5 1,18"/><polyline points="17,6 23,6 23,12"/>
    </svg>
  ),
  TrendingDown: () => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="23,18 13.5,8.5 8.5,13.5 1,6"/><polyline points="17,18 23,18 23,12"/>
    </svg>
  ),
  Search: () => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
    </svg>
  ),
  Refresh: () => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="23,4 23,10 17,10"/><polyline points="1,20 1,14 7,14"/>
      <path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15"/>
    </svg>
  ),
  Calendar: () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>
    </svg>
  ),
  Database: () => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/>
      <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>
    </svg>
  ),
  Download: () => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7,10 12,15 17,10"/><line x1="12" y1="15" x2="12" y2="3"/>
    </svg>
  ),
  ChevronUp: () => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="18,15 12,9 6,15"/>
    </svg>
  ),
  ChevronDown: () => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="6,9 12,15 18,9"/>
    </svg>
  ),
  ChevronLeft: () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="15,18 9,12 15,6"/>
    </svg>
  ),
  ChevronRight: () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="9,6 15,12 9,18"/>
    </svg>
  ),
}

function App() {
  const [tab, setTab] = useState('home')
  const [summary, setSummary] = useState(null)
  const [allPredictions, setAllPredictions] = useState([])
  const [predictions, setPredictions] = useState([])
  const [filters, setFilters] = useState({ carrier: '', airport: '', risk_category: '', month: '' })
  const [searchText, setSearchText] = useState('')
  const [metadata, setMetadata] = useState({ carriers: [], airports: [] })
  const [monthly, setMonthly] = useState([])
  const [globalExplain, setGlobalExplain] = useState(null)
  const [routeExplain, setRouteExplain] = useState([])
  const [route, setRoute] = useState({ carrier: '', airport: '' })
  const [monitoring, setMonitoring] = useState(null)
  const [loading, setLoading] = useState({})
  const [lastUpdate, setLastUpdate] = useState(new Date())
  
  // Pagination
  const [currentPage, setCurrentPage] = useState(1)
  const [itemsPerPage, setItemsPerPage] = useState(25)
  
  // Tri
  const [sortConfig, setSortConfig] = useState({ key: 'risk_score', direction: 'desc' })

  useEffect(() => {
    const loadInitialData = async () => {
      setLoading(l => ({ ...l, initial: true }))
      try {
        const [summaryData, metadataData, monthlyData, predictionsData, globalData, monitoringData] = await Promise.all([
          getSummary(),
          getMetadata(),
          getMonthlyStats(),
          getPredictions({}), // Précharger TOUTES les prédictions
          getGlobalExplainability(),
          getMonitoring()
        ])
        setSummary(summaryData)
        setMetadata(metadataData)
        setMonthly(monthlyData)
        setAllPredictions(predictionsData) // Stocker toutes les prédictions
        setPredictions(predictionsData) // Afficher toutes par défaut
        setGlobalExplain(globalData)
        setMonitoring(monitoringData)
        setLastUpdate(new Date())
      } catch (e) {
        console.error('Error loading initial data:', e)
      }
      setLoading(l => ({ ...l, initial: false }))
    }
    loadInitialData()
  }, [])

  const formatPercent = (value) => {
    if (value === null || value === undefined || Number.isNaN(value)) return '—'
    return `${(value * 100).toFixed(1)}%`
  }

  const formatNumber = (value) => {
    if (value === null || value === undefined || Number.isNaN(value)) return '—'
    return value.toLocaleString('fr-FR')
  }

  const formatCompact = (value) => {
    if (value === null || value === undefined || Number.isNaN(value)) return '—'
    if (value >= 1000000) return `${(value / 1000000).toFixed(1)}M`
    if (value >= 1000) return `${(value / 1000).toFixed(1)}K`
    return value.toString()
  }

  const monthNames = ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Jun', 'Jul', 'Aoû', 'Sep', 'Oct', 'Nov', 'Déc']
  const monthNamesFull = ['Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin', 'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']

  const stats = useMemo(() => {
    if (!monthly.length) return { best: null, worst: null, avgDelay: 0 }
    const sorted = [...monthly].sort((a, b) => a.avg_predicted_delay - b.avg_predicted_delay)
    return {
      best: sorted[0],
      worst: sorted[sorted.length - 1],
      avgDelay: monthly.reduce((a, b) => a + b.avg_predicted_delay, 0) / monthly.length,
      totalFlights: monthly.reduce((a, b) => a + b.total_flights, 0)
    }
  }, [monthly])

  // Filtrer les prédictions automatiquement quand les filtres changent
  useEffect(() => {
    if (!allPredictions.length) return
    
    let filtered = [...allPredictions]
    
    if (filters.carrier) {
      filtered = filtered.filter(p => p.carrier === filters.carrier)
    }
    if (filters.airport) {
      filtered = filtered.filter(p => p.origin_airport === filters.airport)
    }
    if (filters.month) {
      filtered = filtered.filter(p => p.month === parseInt(filters.month))
    }
    if (filters.risk_category) {
      filtered = filtered.filter(p => p.risk_category === filters.risk_category)
    }
    
    // Recherche textuelle
    if (searchText.trim()) {
      const search = searchText.toLowerCase().trim()
      filtered = filtered.filter(p => 
        p.carrier.toLowerCase().includes(search) ||
        p.origin_airport.toLowerCase().includes(search)
      )
    }
    
    setPredictions(filtered)
    setCurrentPage(1) // Reset page quand filtres changent
  }, [filters, allPredictions, searchText])

  // Persistance des filtres dans l'URL
  useEffect(() => {
    const params = new URLSearchParams()
    if (filters.carrier) params.set('carrier', filters.carrier)
    if (filters.airport) params.set('airport', filters.airport)
    if (filters.month) params.set('month', filters.month)
    if (filters.risk_category) params.set('risk', filters.risk_category)
    if (searchText) params.set('q', searchText)
    if (tab !== 'home') params.set('tab', tab)
    
    const newUrl = params.toString() ? `?${params.toString()}` : window.location.pathname
    window.history.replaceState({}, '', newUrl)
  }, [filters, searchText, tab])

  // Charger filtres depuis URL au démarrage
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const urlFilters = {
      carrier: params.get('carrier') || '',
      airport: params.get('airport') || '',
      month: params.get('month') || '',
      risk_category: params.get('risk') || ''
    }
    if (urlFilters.carrier || urlFilters.airport || urlFilters.month || urlFilters.risk_category) {
      setFilters(urlFilters)
    }
    if (params.get('q')) setSearchText(params.get('q'))
    if (params.get('tab')) setTab(params.get('tab'))
  }, [])

  // Options disponibles basées sur les filtres actuels (filtrage intelligent)
  const availableOptions = useMemo(() => {
    if (!allPredictions.length) return { carriers: [], airports: [], months: [], risks: [] }
    
    // Appliquer les filtres partiels pour déterminer les options restantes
    let data = [...allPredictions]
    
    // Pour carriers: filtrer par tout sauf carrier
    let forCarriers = data
    if (filters.airport) forCarriers = forCarriers.filter(p => p.origin_airport === filters.airport)
    if (filters.month) forCarriers = forCarriers.filter(p => p.month === parseInt(filters.month))
    if (filters.risk_category) forCarriers = forCarriers.filter(p => p.risk_category === filters.risk_category)
    const carriers = [...new Set(forCarriers.map(p => p.carrier))].sort()
    
    // Pour airports: filtrer par tout sauf airport
    let forAirports = data
    if (filters.carrier) forAirports = forAirports.filter(p => p.carrier === filters.carrier)
    if (filters.month) forAirports = forAirports.filter(p => p.month === parseInt(filters.month))
    if (filters.risk_category) forAirports = forAirports.filter(p => p.risk_category === filters.risk_category)
    const airports = [...new Set(forAirports.map(p => p.origin_airport))].sort()
    
    // Pour months: filtrer par tout sauf month
    let forMonths = data
    if (filters.carrier) forMonths = forMonths.filter(p => p.carrier === filters.carrier)
    if (filters.airport) forMonths = forMonths.filter(p => p.origin_airport === filters.airport)
    if (filters.risk_category) forMonths = forMonths.filter(p => p.risk_category === filters.risk_category)
    const months = [...new Set(forMonths.map(p => p.month))].sort((a, b) => a - b)
    
    // Pour risk: filtrer par tout sauf risk
    let forRisks = data
    if (filters.carrier) forRisks = forRisks.filter(p => p.carrier === filters.carrier)
    if (filters.airport) forRisks = forRisks.filter(p => p.origin_airport === filters.airport)
    if (filters.month) forRisks = forRisks.filter(p => p.month === parseInt(filters.month))
    const risks = [...new Set(forRisks.map(p => p.risk_category))]
    
    return { carriers, airports, months, risks }
  }, [allPredictions, filters])

  // Options disponibles pour la page explicabilité route
  const availableRouteOptions = useMemo(() => {
    if (!allPredictions.length) return { carriers: [], airports: [] }
    
    let data = [...allPredictions]
    
    // Pour carriers sur route
    let forCarriers = data
    if (route.airport) forCarriers = forCarriers.filter(p => p.origin_airport === route.airport)
    const carriers = [...new Set(forCarriers.map(p => p.carrier))].sort()
    
    // Pour airports sur route
    let forAirports = data
    if (route.carrier) forAirports = forAirports.filter(p => p.carrier === route.carrier)
    const airports = [...new Set(forAirports.map(p => p.origin_airport))].sort()
    
    return { carriers, airports }
  }, [allPredictions, route])

  // Données triées
  const sortedPredictions = useMemo(() => {
    if (!predictions.length) return []
    const sorted = [...predictions]
    sorted.sort((a, b) => {
      let aVal = a[sortConfig.key]
      let bVal = b[sortConfig.key]
      
      if (typeof aVal === 'string') {
        aVal = aVal.toLowerCase()
        bVal = bVal.toLowerCase()
      }
      
      if (aVal < bVal) return sortConfig.direction === 'asc' ? -1 : 1
      if (aVal > bVal) return sortConfig.direction === 'asc' ? 1 : -1
      return 0
    })
    return sorted
  }, [predictions, sortConfig])

  // Données paginées
  const paginatedPredictions = useMemo(() => {
    const start = (currentPage - 1) * itemsPerPage
    return sortedPredictions.slice(start, start + itemsPerPage)
  }, [sortedPredictions, currentPage, itemsPerPage])

  const totalPages = Math.ceil(sortedPredictions.length / itemsPerPage)

  // Fonction de tri
  const handleSort = useCallback((key) => {
    setSortConfig(prev => ({
      key,
      direction: prev.key === key && prev.direction === 'asc' ? 'desc' : 'asc'
    }))
  }, [])

  // Export CSV
  const exportToCSV = useCallback(() => {
    if (!sortedPredictions.length) return
    
    const headers = ['Compagnie', 'Aeroport', 'Annee', 'Mois', 'Taux_Retard', 'Score_Risque', 'Categorie']
    const rows = sortedPredictions.map(p => [
      p.carrier,
      p.origin_airport,
      p.year,
      p.month,
      (p.predicted_delay_rate * 100).toFixed(2),
      (p.risk_score * 100).toFixed(2),
      p.risk_category
    ])
    
    const csv = [headers.join(';'), ...rows.map(r => r.join(';'))].join('\n')
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `predictions_${new Date().toISOString().split('T')[0]}.csv`
    link.click()
    URL.revokeObjectURL(url)
  }, [sortedPredictions])

  // Advanced Area Chart Component
  const AreaChart = ({ data, yKey, color = '#6366f1', height = 320 }) => {
    if (!data || data.length < 2) return <div className="chart-empty">Données insuffisantes</div>
    
    const values = data.map(d => Number(d[yKey] || 0))
    const max = Math.max(...values) * 1.1
    const min = Math.min(...values) * 0.9
    const range = max - min || 1
    
    const padding = { top: 30, right: 30, bottom: 50, left: 70 }
    const chartWidth = 600
    const chartHeight = 300
    
    const points = values.map((v, i) => ({
      x: padding.left + (i / (values.length - 1)) * (chartWidth - padding.left - padding.right),
      y: padding.top + (1 - (v - min) / range) * (chartHeight - padding.top - padding.bottom),
      value: v,
      index: i
    }))
    
    const linePath = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x},${p.y}`).join(' ')
    const areaPath = `${linePath} L${points[points.length - 1].x},${chartHeight - padding.bottom} L${points[0].x},${chartHeight - padding.bottom} Z`
    
    const yTicks = [0, 0.25, 0.5, 0.75, 1].map(t => ({
      y: padding.top + t * (chartHeight - padding.top - padding.bottom),
      value: max - t * range
    }))

    return (
      <div className="chart-wrapper" style={{ height }}>
        <svg viewBox={`0 0 ${chartWidth} ${chartHeight}`} preserveAspectRatio="xMidYMid meet" className="area-chart">
          <defs>
            <linearGradient id={`gradient-${yKey}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity="0.35" />
              <stop offset="100%" stopColor={color} stopOpacity="0.02" />
            </linearGradient>
            <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="2" result="blur" />
              <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
            </filter>
          </defs>
          
          {/* Grid */}
          {yTicks.map((tick, i) => (
            <g key={i}>
              <line x1={padding.left} y1={tick.y} x2={chartWidth - padding.right} y2={tick.y} stroke="#e5e7eb" strokeWidth="1" strokeDasharray="5,5" />
              <text x={padding.left - 10} y={tick.y + 4} fill="#9ca3af" fontSize="12" textAnchor="end">{(tick.value * 100).toFixed(1)}%</text>
            </g>
          ))}
          
          {/* X axis labels */}
          {points.map((p, i) => (
            <text key={i} x={p.x} y={chartHeight - padding.bottom + 25} fill="#9ca3af" fontSize="13" textAnchor="middle" fontWeight="500">
              {monthNames[i]}
            </text>
          ))}
          
          {/* Area */}
          <path d={areaPath} fill={`url(#gradient-${yKey})`} />
          
          {/* Line */}
          <path d={linePath} fill="none" stroke={color} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" filter="url(#glow)" />
          
          {/* Dots */}
          {points.map((p, i) => (
            <g key={i} className="chart-dot">
              <circle cx={p.x} cy={p.y} r="8" fill="white" stroke={color} strokeWidth="3" />
              <circle cx={p.x} cy={p.y} r="3" fill={color} />
            </g>
          ))}
        </svg>
      </div>
    )
  }

  // Bar Chart Component
  const BarChart = ({ data, yKey, color = '#6366f1', height = 320 }) => {
    if (!data || data.length < 2) return <div className="chart-empty">Données insuffisantes</div>
    
    const values = data.map(d => Number(d[yKey] || 0))
    const max = Math.max(...values)
    
    return (
      <div className="bar-chart-wrapper" style={{ height }}>
        <div className="bar-chart-inner">
          {values.map((v, i) => {
            const pct = max > 0 ? (v / max) * 100 : 0
            return (
              <div key={i} className="bar-item">
                <div className="bar-tooltip">{formatCompact(v)}</div>
                <div className="bar-fill" style={{ '--height': `${pct}%`, '--color': color }}>
                  <div className="bar-highlight" />
                </div>
                <span className="bar-label">{monthNames[i]}</span>
              </div>
            )
          })}
        </div>
      </div>
    )
  }

  // Donut Chart Component
  const DonutChart = ({ value, max = 100, color = '#6366f1', size = 100, label }) => {
    const pct = Math.min(Math.max((value / max) * 100, 0), 100)
    const strokeWidth = 8
    const radius = (size - strokeWidth) / 2
    const circumference = 2 * Math.PI * radius
    const offset = circumference - (pct / 100) * circumference

    return (
      <div className="donut-wrapper">
        <svg width={size} height={size} className="donut-chart">
          <circle cx={size/2} cy={size/2} r={radius} fill="none" stroke="#e5e7eb" strokeWidth={strokeWidth} />
          <circle 
            cx={size/2} cy={size/2} r={radius} fill="none" stroke={color} strokeWidth={strokeWidth}
            strokeDasharray={circumference} strokeDashoffset={offset}
            strokeLinecap="round" transform={`rotate(-90 ${size/2} ${size/2})`}
            style={{ transition: 'stroke-dashoffset 1s ease-out' }}
          />
        </svg>
        <div className="donut-center">
          <span className="donut-value">{pct.toFixed(1)}%</span>
          {label && <span className="donut-label">{label}</span>}
        </div>
      </div>
    )
  }

  // Feature Bar Component
  const FeatureBar = ({ name, value, maxValue, color }) => {
    const pct = maxValue > 0 ? (value / maxValue) * 100 : 0
    return (
      <div className="feature-bar">
        <div className="feature-info">
          <span className="feature-name">{name}</span>
          <span className="feature-value">{(value * 100).toFixed(1)}%</span>
        </div>
        <div className="feature-track">
          <div className="feature-fill" style={{ width: `${pct}%`, background: color }} />
        </div>
      </div>
    )
  }

  const resetFilters = () => {
    setFilters({ carrier: '', airport: '', risk_category: '', month: '' })
  }

  const loadGlobalExplain = async () => {
    if (globalExplain) return // Déjà chargé
    setLoading(l => ({ ...l, global: true }))
    try {
      const data = await getGlobalExplainability()
      setGlobalExplain(data)
    } catch (e) { console.error(e) }
    setLoading(l => ({ ...l, global: false }))
  }

  const loadRouteExplain = async () => {
    if (!route.carrier || !route.airport) return
    setLoading(l => ({ ...l, route: true }))
    try {
      const data = await getRouteExplainability(route.carrier, route.airport)
      setRouteExplain(data)
    } catch (e) { console.error(e) }
    setLoading(l => ({ ...l, route: false }))
  }

  const loadMonitoring = async () => {
    setLoading(l => ({ ...l, monitoring: true }))
    try {
      const data = await getMonitoring()
      setMonitoring(data)
    } catch (e) { console.error(e) }
    setLoading(l => ({ ...l, monitoring: false }))
  }

  // Composant Loading Skeleton
  const LoadingSkeleton = () => (
    <div className="loading-skeleton">
      <div className="skeleton-header">
        <div className="skeleton-title"></div>
        <div className="skeleton-subtitle"></div>
      </div>
      <div className="skeleton-grid">
        {[1, 2, 3, 4].map(i => (
          <div key={i} className="skeleton-card">
            <div className="skeleton-icon"></div>
            <div className="skeleton-text"></div>
            <div className="skeleton-value"></div>
          </div>
        ))}
      </div>
      <div className="skeleton-charts">
        <div className="skeleton-chart-large"></div>
        <div className="skeleton-chart-small"></div>
      </div>
    </div>
  )

  const navItems = [
    { id: 'home', label: 'Vue d\'ensemble', icon: Icons.Home },
    { id: 'pred', label: 'Prédictions', icon: Icons.Chart },
    { id: 'explain', label: 'Explicabilité', icon: Icons.Brain },
    { id: 'monitor', label: 'Monitoring', icon: Icons.Activity },
  ]

  return (
    <div className="app">
      {/* Ecran de chargement initial */}
      {loading.initial && (
        <div className="loading-overlay">
          <div className="loading-content">
            <div className="loading-logo">
              <Icons.Plane />
            </div>
            <div className="loading-spinner"></div>
            <p className="loading-text">Chargement des données...</p>
          </div>
        </div>
      )}
      
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-header">
          <div className="logo">
            <div className="logo-icon"><Icons.Plane /></div>
            <div className="logo-text">
              <span className="logo-title">FlightML</span>
              <span className="logo-subtitle">Analytics</span>
            </div>
          </div>
        </div>
        
        <nav className="sidebar-nav">
          {navItems.map(item => (
            <button
              key={item.id}
              className={`nav-item ${tab === item.id ? 'active' : ''}`}
              onClick={() => setTab(item.id)}
            >
              <item.icon />
              <span>{item.label}</span>
            </button>
          ))}
        </nav>
        
        <div className="sidebar-footer">
          <div className="status-card">
            <div className="status-indicator online" />
            <div className="status-text">
              <span className="status-label">Système</span>
              <span className="status-value">Opérationnel</span>
            </div>
          </div>
          <div className="last-update">
            <Icons.Calendar />
            <span>Mis à jour: {lastUpdate.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })}</span>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="main">
        {/* Header */}
        <header className="header">
          <div className="header-left">
            <h1 className="page-title">
              {navItems.find(n => n.id === tab)?.label || 'Dashboard'}
            </h1>
            <p className="page-subtitle">Prédictions des retards aériens · 2026</p>
          </div>
          <div className="header-right">
            <div className="header-stat">
              <Icons.Database />
              <span>{formatCompact(summary?.total_predictions || 0)} prédictions</span>
            </div>
          </div>
        </header>

        {/* Content */}
        <div className="content">
          {tab === 'home' && (
            <div className="dashboard-grid">
              {/* KPI Cards */}
              <div className="kpi-section">
                <div className="kpi-card primary">
                  <div className="kpi-icon"><Icons.Chart /></div>
                  <div className="kpi-content">
                    <span className="kpi-label">Total Prédictions</span>
                    <span className="kpi-value">{formatNumber(summary?.total_predictions)}</span>
                  </div>
                  <div className="kpi-trend up"><Icons.TrendingUp /> +12.3%</div>
                </div>
                
                <div className="kpi-card critical">
                  <div className="kpi-icon"><Icons.AlertTriangle /></div>
                  <div className="kpi-content">
                    <span className="kpi-label">Routes Critiques</span>
                    <span className="kpi-value">{formatNumber(summary?.critical_risk_routes)}</span>
                  </div>
                  <div className="kpi-trend">{summary?.critical_risk_percentage?.toFixed(1) || '0'}%</div>
                </div>
                
                <div className="kpi-card danger">
                  <div className="kpi-icon"><Icons.AlertTriangle /></div>
                  <div className="kpi-content">
                    <span className="kpi-label">Routes Haut Risque</span>
                    <span className="kpi-value">{formatNumber(summary?.high_risk_routes)}</span>
                  </div>
                  <div className="kpi-trend">{summary?.high_risk_percentage?.toFixed(1) || '0'}%</div>
                </div>
                
                <div className="kpi-card info">
                  <div className="kpi-icon"><Icons.Plane /></div>
                  <div className="kpi-content">
                    <span className="kpi-label">Compagnies</span>
                    <span className="kpi-value">{formatNumber(summary?.carriers_analyzed)}</span>
                  </div>
                </div>
                
                <div className="kpi-card success">
                  <div className="kpi-icon"><Icons.Activity /></div>
                  <div className="kpi-content">
                    <span className="kpi-label">Aéroports</span>
                    <span className="kpi-value">{formatNumber(summary?.airports_analyzed)}</span>
                  </div>
                </div>
              </div>

              {/* Main Charts */}
              <div className="charts-section">
                <div className="chart-card large">
                  <div className="card-header">
                    <h3>Taux de Retard Prédit par Mois</h3>
                    <span className="card-badge">2026</span>
                  </div>
                  <AreaChart data={monthly} yKey="avg_predicted_delay" color="#6366f1" height={380} />
                </div>
                
                <div className="chart-card">
                  <div className="card-header">
                    <h3>Volume de Vols Prédit</h3>
                    <span className="card-badge">Mensuel</span>
                  </div>
                  <BarChart data={monthly} yKey="total_flights" color="#8b5cf6" height={340} />
                </div>
              </div>

              {/* Stats Row */}
              <div className="stats-section">
                <div className="stat-card">
                  <div className="stat-header">
                    <span className="stat-title">Performance Mensuelle</span>
                  </div>
                  <div className="stat-grid">
                    <div className="stat-item best">
                      <Icons.TrendingDown />
                      <div className="stat-info">
                        <span className="stat-label">Meilleur Mois</span>
                        <span className="stat-value">{stats.best ? monthNamesFull[stats.best.month - 1] : '—'}</span>
                        <span className="stat-detail">{formatPercent(stats.best?.avg_predicted_delay)}</span>
                      </div>
                    </div>
                    <div className="stat-item worst">
                      <Icons.TrendingUp />
                      <div className="stat-info">
                        <span className="stat-label">Mois Critique</span>
                        <span className="stat-value">{stats.worst ? monthNamesFull[stats.worst.month - 1] : '—'}</span>
                        <span className="stat-detail">{formatPercent(stats.worst?.avg_predicted_delay)}</span>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="stat-card">
                  <div className="stat-header">
                    <span className="stat-title">Indicateurs Clés</span>
                  </div>
                  <div className="metric-grid">
                    <div className="metric-item">
                      <span className="metric-label">Taux Retard Moyen</span>
                      <span className="metric-value">{formatPercent(summary?.avg_predicted_delay)}</span>
                    </div>
                    <div className="metric-item">
                      <span className="metric-label">Score Risque Moyen</span>
                      <span className="metric-value">{formatPercent(summary?.avg_risk_score)}</span>
                    </div>
                    <div className="metric-item">
                      <span className="metric-label">Part Haut Risque</span>
                      <span className="metric-value">{summary?.high_risk_percentage?.toFixed(1) || '—'}%</span>
                    </div>
                    <div className="metric-item">
                      <span className="metric-label">Vols Totaux</span>
                      <span className="metric-value">{formatCompact(stats.totalFlights)}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {tab === 'pred' && (
            <div className="predictions-page">
              {/* Filters */}
              <div className="filters-card">
                <div className="filters-header">
                  <h3>Filtres de Recherche</h3>
                  <span className="filters-count">{predictions.length} résultats</span>
                </div>
                
                {/* Barre de recherche */}
                <div className="search-bar">
                  <Icons.Search />
                  <input
                    type="text"
                    placeholder="Rechercher une compagnie ou un aéroport..."
                    value={searchText}
                    onChange={(e) => setSearchText(e.target.value)}
                    className="search-input"
                  />
                  {searchText && (
                    <button className="search-clear" onClick={() => setSearchText('')}>
                      ×
                    </button>
                  )}
                </div>
                
                <div className="filters-grid">
                  <div className="filter-group">
                    <label>Compagnie ({availableOptions.carriers.length})</label>
                    <select value={filters.carrier} onChange={(e) => setFilters({ ...filters, carrier: e.target.value })}>
                      <option value="">Toutes les compagnies</option>
                      {availableOptions.carriers.map(c => <option key={c} value={c}>{c}</option>)}
                    </select>
                  </div>
                  <div className="filter-group">
                    <label>Aéroport ({availableOptions.airports.length})</label>
                    <select value={filters.airport} onChange={(e) => setFilters({ ...filters, airport: e.target.value })}>
                      <option value="">Tous les aéroports</option>
                      {availableOptions.airports.map(a => <option key={a} value={a}>{a}</option>)}
                    </select>
                  </div>
                  <div className="filter-group">
                    <label>Mois ({availableOptions.months.length})</label>
                    <select value={filters.month} onChange={(e) => setFilters({ ...filters, month: e.target.value })}>
                      <option value="">Tous les mois</option>
                      {availableOptions.months.map(m => <option key={m} value={m}>{monthNamesFull[m - 1]}</option>)}
                    </select>
                  </div>
                  <div className="filter-group">
                    <label>Niveau de Risque ({availableOptions.risks.length})</label>
                    <select value={filters.risk_category} onChange={(e) => setFilters({ ...filters, risk_category: e.target.value })}>
                      <option value="">Tous les niveaux</option>
                      {availableOptions.risks.includes('critical') && <option value="critical">Critique</option>}
                      {availableOptions.risks.includes('high') && <option value="high">Élevé</option>}
                      {availableOptions.risks.includes('medium') && <option value="medium">Moyen</option>}
                      {availableOptions.risks.includes('low') && <option value="low">Faible</option>}
                    </select>
                  </div>
                </div>
                <div className="filters-actions">
                  <button className="btn btn-secondary" onClick={resetFilters}>
                    <Icons.Refresh />
                    Réinitialiser
                  </button>
                  <button className="btn btn-primary" onClick={exportToCSV} disabled={!sortedPredictions.length}>
                    <Icons.Download />
                    Exporter CSV
                  </button>
                </div>
              </div>

              {/* Results Table */}
              <div className="table-card">
                <div className="table-header">
                  <h3>Résultats des Prédictions</h3>
                  <div className="table-controls">
                    <select 
                      value={itemsPerPage} 
                      onChange={(e) => { setItemsPerPage(Number(e.target.value)); setCurrentPage(1); }}
                      className="items-per-page"
                    >
                      <option value={10}>10 par page</option>
                      <option value={25}>25 par page</option>
                      <option value={50}>50 par page</option>
                      <option value={100}>100 par page</option>
                    </select>
                  </div>
                </div>
                {paginatedPredictions.length > 0 ? (
                  <>
                    <div className="table-wrapper">
                      <table className="data-table">
                        <thead>
                          <tr>
                            <th className="sortable" onClick={() => handleSort('carrier')}>
                              Compagnie
                              {sortConfig.key === 'carrier' && (
                                <span className="sort-icon">{sortConfig.direction === 'asc' ? <Icons.ChevronUp /> : <Icons.ChevronDown />}</span>
                              )}
                            </th>
                            <th className="sortable" onClick={() => handleSort('origin_airport')}>
                              Aéroport
                              {sortConfig.key === 'origin_airport' && (
                                <span className="sort-icon">{sortConfig.direction === 'asc' ? <Icons.ChevronUp /> : <Icons.ChevronDown />}</span>
                              )}
                            </th>
                            <th className="sortable" onClick={() => handleSort('year')}>
                              Année
                              {sortConfig.key === 'year' && (
                                <span className="sort-icon">{sortConfig.direction === 'asc' ? <Icons.ChevronUp /> : <Icons.ChevronDown />}</span>
                              )}
                            </th>
                            <th className="sortable" onClick={() => handleSort('month')}>
                              Mois
                              {sortConfig.key === 'month' && (
                                <span className="sort-icon">{sortConfig.direction === 'asc' ? <Icons.ChevronUp /> : <Icons.ChevronDown />}</span>
                              )}
                            </th>
                            <th className="sortable" onClick={() => handleSort('predicted_delay_rate')}>
                              Taux Retard
                              {sortConfig.key === 'predicted_delay_rate' && (
                                <span className="sort-icon">{sortConfig.direction === 'asc' ? <Icons.ChevronUp /> : <Icons.ChevronDown />}</span>
                              )}
                            </th>
                            <th className="sortable" onClick={() => handleSort('risk_score')}>
                              Score Risque
                              {sortConfig.key === 'risk_score' && (
                                <span className="sort-icon">{sortConfig.direction === 'asc' ? <Icons.ChevronUp /> : <Icons.ChevronDown />}</span>
                              )}
                            </th>
                            <th className="sortable" onClick={() => handleSort('risk_category')}>
                              Catégorie
                              {sortConfig.key === 'risk_category' && (
                                <span className="sort-icon">{sortConfig.direction === 'asc' ? <Icons.ChevronUp /> : <Icons.ChevronDown />}</span>
                              )}
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          {paginatedPredictions.map((p, idx) => (
                            <tr key={idx} className="table-row-animated">
                              <td><span className="cell-carrier">{p.carrier}</span></td>
                              <td><span className="cell-airport">{p.origin_airport}</span></td>
                              <td>{p.year}</td>
                              <td>{monthNames[p.month - 1]}</td>
                              <td><span className="cell-percent">{formatPercent(p.predicted_delay_rate)}</span></td>
                              <td>
                                <div className="cell-risk">
                                  <div className="risk-bar" style={{ '--risk': `${p.risk_score * 100}%` }} />
                                  <span>{formatPercent(p.risk_score)}</span>
                                </div>
                              </td>
                              <td><span className={`badge badge-${p.risk_category}`}>{p.risk_category}</span></td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    
                    {/* Pagination */}
                    <div className="pagination">
                      <div className="pagination-info">
                        Affichage {((currentPage - 1) * itemsPerPage) + 1} - {Math.min(currentPage * itemsPerPage, sortedPredictions.length)} sur {sortedPredictions.length}
                      </div>
                      <div className="pagination-controls">
                        <button 
                          className="pagination-btn" 
                          onClick={() => setCurrentPage(1)} 
                          disabled={currentPage === 1}
                        >
                          <Icons.ChevronLeft /><Icons.ChevronLeft />
                        </button>
                        <button 
                          className="pagination-btn" 
                          onClick={() => setCurrentPage(p => p - 1)} 
                          disabled={currentPage === 1}
                        >
                          <Icons.ChevronLeft />
                        </button>
                        <span className="pagination-current">
                          Page {currentPage} / {totalPages}
                        </span>
                        <button 
                          className="pagination-btn" 
                          onClick={() => setCurrentPage(p => p + 1)} 
                          disabled={currentPage === totalPages}
                        >
                          <Icons.ChevronRight />
                        </button>
                        <button 
                          className="pagination-btn" 
                          onClick={() => setCurrentPage(totalPages)} 
                          disabled={currentPage === totalPages}
                        >
                          <Icons.ChevronRight /><Icons.ChevronRight />
                        </button>
                      </div>
                    </div>
                  </>
                ) : (
                  <div className="empty-state">
                    <Icons.Search />
                    <p>Aucun résultat ne correspond aux filtres sélectionnés</p>
                  </div>
                )}
              </div>
            </div>
          )}

          {tab === 'explain' && (
            <div className="explain-page">
              {/* Global Explainability */}
              <div className="explain-card">
                <div className="card-header">
                  <h3>Explicabilité Globale</h3>
                  <span className="card-badge">Préchargé</span>
                </div>
                
                {globalExplain?.features?.length ? (
                  <div className="features-grid">
                    <div className="features-list">
                      {[
                        { name: globalExplain.features[0].top_feature_1, value: globalExplain.features[0].avg_importance_1 },
                        { name: globalExplain.features[0].top_feature_2, value: globalExplain.features[0].avg_importance_2 },
                        { name: globalExplain.features[0].top_feature_3, value: globalExplain.features[0].avg_importance_3 },
                      ].map((f, i) => (
                        <FeatureBar 
                          key={i} 
                          name={f.name} 
                          value={f.value} 
                          maxValue={globalExplain.features[0].avg_importance_1}
                          color={['#6366f1', '#8b5cf6', '#a78bfa'][i]}
                        />
                      ))}
                    </div>
                    <div className="features-donut">
                      <DonutChart 
                        value={globalExplain.features[0].avg_importance_1 * 100} 
                        label="Feature #1" 
                        color="#6366f1" 
                      />
                    </div>
                  </div>
                ) : (
                  <div className="empty-state small">
                    <Icons.Brain />
                    <p>Chargement des features influentes...</p>
                  </div>
                )}
              </div>

              {/* Route Analysis */}
              <div className="explain-card">
                <div className="card-header">
                  <h3>Analyse par Route</h3>
                </div>
                
                <div className="route-filters">
                  <div className="filter-group">
                    <label>Compagnie ({availableRouteOptions.carriers.length})</label>
                    <select value={route.carrier} onChange={(e) => setRoute({ ...route, carrier: e.target.value })}>
                      <option value="">Sélectionner...</option>
                      {availableRouteOptions.carriers.map(c => <option key={c} value={c}>{c}</option>)}
                    </select>
                  </div>
                  <div className="filter-group">
                    <label>Aéroport ({availableRouteOptions.airports.length})</label>
                    <select value={route.airport} onChange={(e) => setRoute({ ...route, airport: e.target.value })}>
                      <option value="">Sélectionner...</option>
                      {availableRouteOptions.airports.map(a => <option key={a} value={a}>{a}</option>)}
                    </select>
                  </div>
                  <button className="btn btn-primary" onClick={loadRouteExplain} disabled={loading.route || !route.carrier || !route.airport}>
                    <Icons.Search />
                    {loading.route ? 'Analyse...' : 'Analyser'}
                  </button>
                </div>

                {routeExplain.length > 0 && (
                  <div className="route-results">
                    <div className="route-summary">
                      <div className="summary-stat">
                        <span className="summary-label">Taux Retard Moyen</span>
                        <span className="summary-value">{formatPercent(routeExplain.reduce((a, b) => a + b.predicted_delay_rate, 0) / routeExplain.length)}</span>
                      </div>
                      <div className="summary-stat">
                        <span className="summary-label">Score Risque Moyen</span>
                        <span className="summary-value">{formatPercent(routeExplain.reduce((a, b) => a + b.risk_score, 0) / routeExplain.length)}</span>
                      </div>
                      <div className="summary-stat">
                        <span className="summary-label">Mois Haut Risque</span>
                        <span className="summary-value">{routeExplain.filter(r => r.risk_category === 'high').length}/12</span>
                      </div>
                    </div>
                    
                    <div className="route-chart">
                      <AreaChart 
                        data={[...routeExplain].sort((a, b) => a.month - b.month)} 
                        yKey="predicted_delay_rate" 
                        color="#8b5cf6" 
                        height={200} 
                      />
                    </div>

                    <div className="route-table">
                      <table className="data-table compact">
                        <thead>
                          <tr>
                            <th>Mois</th>
                            <th>Taux Retard</th>
                            <th>Score Risque</th>
                            <th>Catégorie</th>
                          </tr>
                        </thead>
                        <tbody>
                          {[...routeExplain].sort((a, b) => a.month - b.month).map((r, idx) => (
                            <tr key={idx}>
                              <td>{monthNamesFull[r.month - 1]}</td>
                              <td>{formatPercent(r.predicted_delay_rate)}</td>
                              <td>{formatPercent(r.risk_score)}</td>
                              <td><span className={`badge badge-${r.risk_category}`}>{r.risk_category}</span></td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {tab === 'monitor' && (
            <div className="monitor-page">
              <div className="monitor-card">
                <div className="card-header">
                  <h3>État du Système</h3>
                  <button className="btn btn-secondary" onClick={loadMonitoring} disabled={loading.monitoring}>
                    <Icons.Refresh />
                    {loading.monitoring ? 'Actualisation...' : 'Actualiser'}
                  </button>
                </div>

                <div className="monitor-grid">
                  <div className="monitor-stat">
                    <div className="monitor-icon primary"><Icons.Database /></div>
                    <div className="monitor-info">
                      <span className="monitor-label">Prédictions Totales</span>
                      <span className="monitor-value">{formatNumber(monitoring?.total_predictions || summary?.total_predictions)}</span>
                    </div>
                  </div>
                  <div className="monitor-stat">
                    <div className="monitor-icon danger"><Icons.AlertTriangle /></div>
                    <div className="monitor-info">
                      <span className="monitor-label">Routes Haut Risque</span>
                      <span className="monitor-value">{formatNumber(monitoring?.high_risk_routes || summary?.high_risk_routes)}</span>
                    </div>
                  </div>
                  <div className="monitor-stat">
                    <div className="monitor-icon info"><Icons.Plane /></div>
                    <div className="monitor-info">
                      <span className="monitor-label">Compagnies Analysées</span>
                      <span className="monitor-value">{formatNumber(monitoring?.carriers_analyzed || summary?.carriers_analyzed)}</span>
                    </div>
                  </div>
                  <div className="monitor-stat">
                    <div className="monitor-icon success"><Icons.Activity /></div>
                    <div className="monitor-info">
                      <span className="monitor-label">Aéroports Analysés</span>
                      <span className="monitor-value">{formatNumber(monitoring?.airports_analyzed || summary?.airports_analyzed)}</span>
                    </div>
                  </div>
                </div>

                <div className="monitor-health">
                  <h4>Santé du Modèle</h4>
                  <div className="health-items">
                    <div className="health-item">
                      <span className="health-dot success" />
                      <span>API Backend</span>
                      <span className="health-status">Opérationnel</span>
                    </div>
                    <div className="health-item">
                      <span className="health-dot success" />
                      <span>Base de Données</span>
                      <span className="health-status">Connectée</span>
                    </div>
                    <div className="health-item">
                      <span className="health-dot success" />
                      <span>Modèle ML</span>
                      <span className="health-status">Actif</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}

export default App
