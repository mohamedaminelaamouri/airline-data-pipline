import { useState } from 'react'

function BatchPrediction({ apiUrl, metadata }) {
    const [items, setItems] = useState([
        { carrier: '', airport: '', month: 1, year: 2026 }
    ])
    const [loading, setLoading] = useState(false)
    const [results, setResults] = useState(null)
    const [error, setError] = useState(null)

    const addItem = () => {
        if (items.length >= 100) return
        setItems([...items, { carrier: '', airport: '', month: 1, year: 2026 }])
    }

    const removeItem = (index) => {
        if (items.length <= 1) return
        setItems(items.filter((_, i) => i !== index))
    }

    const updateItem = (index, field, value) => {
        const updated = [...items]
        updated[index][field] = field === 'month' || field === 'year' ? parseInt(value) : value
        setItems(updated)
    }

    const handleSubmit = async () => {
        setLoading(true)
        setError(null)

        try {
            const response = await fetch(`${apiUrl}/predict/batch`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ predictions: items })
            })

            if (!response.ok) {
                const err = await response.json()
                throw new Error(err.detail || 'Batch prediction failed')
            }

            const data = await response.json()
            setResults(data)
        } catch (err) {
            setError(err.message)
        } finally {
            setLoading(false)
        }
    }

    const months = [
        'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
        'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'
    ]

    return (
        <div>
            <div className="card">
                <div className="card-header">
                    <h2 className="card-title">📦 Batch Prediction</h2>
                    <span style={{ color: 'var(--text-secondary)' }}>
                        {items.length} / 100 items
                    </span>
                </div>

                <div className="batch-items">
                    {items.map((item, index) => (
                        <div key={index} className="batch-item">
                            <div className="form-group">
                                <label>Carrier</label>
                                <select
                                    value={item.carrier}
                                    onChange={(e) => updateItem(index, 'carrier', e.target.value)}
                                >
                                    <option value="">Select...</option>
                                    {metadata.carriers?.map(c => (
                                        <option key={c} value={c}>{c}</option>
                                    ))}
                                </select>
                            </div>

                            <div className="form-group">
                                <label>Airport</label>
                                <select
                                    value={item.airport}
                                    onChange={(e) => updateItem(index, 'airport', e.target.value)}
                                >
                                    <option value="">Select...</option>
                                    {metadata.airports?.map(a => (
                                        <option key={a} value={a}>{a}</option>
                                    ))}
                                </select>
                            </div>

                            <div className="form-group">
                                <label>Month</label>
                                <select
                                    value={item.month}
                                    onChange={(e) => updateItem(index, 'month', e.target.value)}
                                >
                                    {months.map((m, i) => (
                                        <option key={i} value={i + 1}>{m}</option>
                                    ))}
                                </select>
                            </div>

                            <div className="form-group">
                                <label>Year</label>
                                <input
                                    type="number"
                                    min="2020"
                                    max="2030"
                                    value={item.year}
                                    onChange={(e) => updateItem(index, 'year', e.target.value)}
                                />
                            </div>

                            <button
                                type="button"
                                className="remove-btn"
                                onClick={() => removeItem(index)}
                                disabled={items.length <= 1}
                            >
                                ✕
                            </button>
                        </div>
                    ))}
                </div>

                <button type="button" className="add-btn" onClick={addItem}>
                    + Add another prediction
                </button>

                {error && (
                    <div style={{ color: '#ef4444', marginTop: '1rem' }}>
                        ⚠️ {error}
                    </div>
                )}

                <button
                    type="button"
                    className="btn btn-primary"
                    style={{ marginTop: '1.5rem', width: '100%' }}
                    onClick={handleSubmit}
                    disabled={loading || items.some(i => !i.carrier || !i.airport)}
                >
                    {loading ? (
                        <>
                            <span className="spinner"></span>
                            Processing {items.length} predictions...
                        </>
                    ) : (
                        `🚀 Run ${items.length} Predictions`
                    )}
                </button>
            </div>

            {results && (
                <div className="card">
                    <h3 className="card-title" style={{ marginBottom: '1rem' }}>Results</h3>

                    <div className="batch-summary">
                        <div className="summary-stat">
                            <div className="value">{results.total}</div>
                            <div className="label">Total</div>
                        </div>
                        <div className="summary-stat" style={{ color: 'var(--success)' }}>
                            <div className="value">{results.successful}</div>
                            <div className="label">Successful</div>
                        </div>
                        <div className="summary-stat" style={{ color: 'var(--danger)' }}>
                            <div className="value">{results.failed}</div>
                            <div className="label">Failed</div>
                        </div>
                    </div>

                    <div className="table-wrapper">
                        <table>
                            <thead>
                                <tr>
                                    <th>Carrier</th>
                                    <th>Airport</th>
                                    <th>Month</th>
                                    <th>Year</th>
                                    <th>Prediction</th>
                                    <th>Risk</th>
                                </tr>
                            </thead>
                            <tbody>
                                {results.results.map((r, i) => (
                                    <tr key={i}>
                                        <td>{r.inputs.carrier}</td>
                                        <td>{r.inputs.airport}</td>
                                        <td>{months[r.inputs.month - 1]}</td>
                                        <td>{r.inputs.year}</td>
                                        <td>{(r.prediction * 100).toFixed(1)}%</td>
                                        <td>
                                            <span className={`risk-badge risk-${r.risk_category}`} style={{ fontSize: '0.75rem', padding: '0.25rem 0.5rem' }}>
                                                {r.risk_category}
                                            </span>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}
        </div>
    )
}

export default BatchPrediction
