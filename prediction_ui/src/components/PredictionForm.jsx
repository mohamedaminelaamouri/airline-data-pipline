import { useState } from 'react'

function PredictionForm({ apiUrl, metadata, onPrediction, lastPrediction }) {
    const [form, setForm] = useState({
        carrier: '',
        airport: '',
        month: new Date().getMonth() + 1,
        year: new Date().getFullYear()
    })
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState(null)

    const handleSubmit = async (e) => {
        e.preventDefault()
        setLoading(true)
        setError(null)

        try {
            const response = await fetch(`${apiUrl}/predict`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(form)
            })

            if (!response.ok) {
                const err = await response.json()
                throw new Error(err.detail || 'Prediction failed')
            }

            const result = await response.json()
            onPrediction(result)
        } catch (err) {
            setError(err.message)
        } finally {
            setLoading(false)
        }
    }

    const months = [
        'January', 'February', 'March', 'April', 'May', 'June',
        'July', 'August', 'September', 'October', 'November', 'December'
    ]

    return (
        <div>
            <div className="card">
                <div className="card-header">
                    <h2 className="card-title">🎯 Single Prediction</h2>
                </div>

                <form onSubmit={handleSubmit}>
                    <div className="form-grid">
                        <div className="form-group">
                            <label>Carrier</label>
                            <select
                                value={form.carrier}
                                onChange={(e) => setForm({ ...form, carrier: e.target.value })}
                                required
                            >
                                <option value="">Select carrier...</option>
                                {metadata.carriers?.map(c => (
                                    <option key={c} value={c}>{c}</option>
                                ))}
                            </select>
                        </div>

                        <div className="form-group">
                            <label>Airport</label>
                            <select
                                value={form.airport}
                                onChange={(e) => setForm({ ...form, airport: e.target.value })}
                                required
                            >
                                <option value="">Select airport...</option>
                                {metadata.airports?.map(a => (
                                    <option key={a} value={a}>{a}</option>
                                ))}
                            </select>
                        </div>

                        <div className="form-group">
                            <label>Month</label>
                            <select
                                value={form.month}
                                onChange={(e) => setForm({ ...form, month: parseInt(e.target.value) })}
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
                                value={form.year}
                                onChange={(e) => setForm({ ...form, year: parseInt(e.target.value) })}
                            />
                        </div>
                    </div>

                    {error && (
                        <div style={{ color: '#ef4444', marginTop: '1rem' }}>
                            ⚠️ {error}
                        </div>
                    )}

                    <button
                        type="submit"
                        className="btn btn-primary"
                        style={{ marginTop: '1.5rem', width: '100%' }}
                        disabled={loading || !form.carrier || !form.airport}
                    >
                        {loading ? (
                            <>
                                <span className="spinner"></span>
                                Processing...
                            </>
                        ) : (
                            '🔮 Predict Delay Risk'
                        )}
                    </button>
                </form>
            </div>

            {lastPrediction && (
                <div className="card result-card">
                    <div className="result-prediction">
                        {(lastPrediction.prediction * 100).toFixed(1)}%
                    </div>
                    <div className={`risk-badge risk-${lastPrediction.risk_category}`}>
                        {lastPrediction.risk_category} Risk
                    </div>
                    <div className="result-meta">
                        <span>📍 {lastPrediction.inputs.carrier} → {lastPrediction.inputs.airport}</span>
                        <span>📅 {months[lastPrediction.inputs.month - 1]} {lastPrediction.inputs.year}</span>
                        <span>🆔 {lastPrediction.request_id.slice(0, 8)}...</span>
                    </div>
                </div>
            )}
        </div>
    )
}

export default PredictionForm
