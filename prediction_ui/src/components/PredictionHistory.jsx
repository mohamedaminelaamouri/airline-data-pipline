import { useState, useEffect } from 'react'

function PredictionHistory({ apiUrl, metadata }) {
    const [predictions, setPredictions] = useState([])
    const [loading, setLoading] = useState(true)
    const [total, setTotal] = useState(0)
    const [page, setPage] = useState(1)
    const [pageSize] = useState(20)
    const [filters, setFilters] = useState({
        carrier: '',
        airport: '',
        risk_category: ''
    })

    const fetchHistory = async () => {
        setLoading(true)
        try {
            const params = new URLSearchParams({
                page: page.toString(),
                page_size: pageSize.toString()
            })

            if (filters.carrier) params.append('carrier', filters.carrier)
            if (filters.airport) params.append('airport', filters.airport)
            if (filters.risk_category) params.append('risk_category', filters.risk_category)

            const response = await fetch(`${apiUrl}/predictions/history?${params}`)
            const data = await response.json()

            setPredictions(data.predictions || [])
            setTotal(data.total || 0)
        } catch (err) {
            console.error('Failed to fetch history:', err)
            setPredictions([])
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        fetchHistory()
    }, [page, filters])

    const handleFilterChange = (field, value) => {
        setFilters({ ...filters, [field]: value })
        setPage(1) // Reset to first page
    }

    const totalPages = Math.ceil(total / pageSize)

    const months = [
        'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
        'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'
    ]

    return (
        <div className="card">
            <div className="card-header">
                <h2 className="card-title">📜 Prediction History</h2>
                <span style={{ color: 'var(--text-secondary)' }}>
                    {total} total predictions
                </span>
            </div>

            <div className="filters">
                <div className="form-group">
                    <label>Carrier</label>
                    <select
                        value={filters.carrier}
                        onChange={(e) => handleFilterChange('carrier', e.target.value)}
                    >
                        <option value="">All carriers</option>
                        {metadata.carriers?.map(c => (
                            <option key={c} value={c}>{c}</option>
                        ))}
                    </select>
                </div>

                <div className="form-group">
                    <label>Airport</label>
                    <select
                        value={filters.airport}
                        onChange={(e) => handleFilterChange('airport', e.target.value)}
                    >
                        <option value="">All airports</option>
                        {metadata.airports?.map(a => (
                            <option key={a} value={a}>{a}</option>
                        ))}
                    </select>
                </div>

                <div className="form-group">
                    <label>Risk Category</label>
                    <select
                        value={filters.risk_category}
                        onChange={(e) => handleFilterChange('risk_category', e.target.value)}
                    >
                        <option value="">All risks</option>
                        <option value="low">Low</option>
                        <option value="medium">Medium</option>
                        <option value="high">High</option>
                        <option value="critical">Critical</option>
                    </select>
                </div>

                <div className="form-group" style={{ alignSelf: 'flex-end' }}>
                    <button className="btn btn-secondary" onClick={fetchHistory}>
                        🔄 Refresh
                    </button>
                </div>
            </div>

            {loading ? (
                <div className="loading">
                    <span className="spinner"></span>
                    Loading predictions...
                </div>
            ) : predictions.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-secondary)' }}>
                    No predictions found. Make some predictions first!
                </div>
            ) : (
                <>
                    <div className="table-wrapper">
                        <table>
                            <thead>
                                <tr>
                                    <th>Request ID</th>
                                    <th>Carrier</th>
                                    <th>Airport</th>
                                    <th>Period</th>
                                    <th>Prediction</th>
                                    <th>Risk</th>
                                    <th>Timestamp</th>
                                </tr>
                            </thead>
                            <tbody>
                                {predictions.map((p) => (
                                    <tr key={p.request_id}>
                                        <td style={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
                                            {p.request_id.slice(0, 8)}...
                                        </td>
                                        <td>{p.carrier}</td>
                                        <td>{p.airport}</td>
                                        <td>{months[p.month - 1]} {p.year}</td>
                                        <td>{(p.prediction * 100).toFixed(1)}%</td>
                                        <td>
                                            <span
                                                className={`risk-badge risk-${p.risk_category}`}
                                                style={{ fontSize: '0.7rem', padding: '0.2rem 0.5rem' }}
                                            >
                                                {p.risk_category}
                                            </span>
                                        </td>
                                        <td style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                                            {new Date(p.timestamp).toLocaleString()}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>

                    <div className="pagination">
                        <button onClick={() => setPage(1)} disabled={page === 1}>
                            ⏮ First
                        </button>
                        <button onClick={() => setPage(p => p - 1)} disabled={page === 1}>
                            ← Prev
                        </button>
                        <span>
                            Page {page} of {totalPages || 1}
                        </span>
                        <button onClick={() => setPage(p => p + 1)} disabled={page >= totalPages}>
                            Next →
                        </button>
                        <button onClick={() => setPage(totalPages)} disabled={page >= totalPages}>
                            Last ⏭
                        </button>
                    </div>
                </>
            )}
        </div>
    )
}

export default PredictionHistory
