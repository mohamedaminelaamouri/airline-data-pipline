import { useState, useEffect } from 'react'
import PredictionForm from './components/PredictionForm'
import BatchPrediction from './components/BatchPrediction'
import PredictionHistory from './components/PredictionHistory'
import './App.css'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001'

function App() {
  const [activeTab, setActiveTab] = useState('single')
  const [metadata, setMetadata] = useState({ carriers: [], airports: [], status: 'loading' })
  const [lastPrediction, setLastPrediction] = useState(null)

  useEffect(() => {
    fetch(`${API_URL}/predict/metadata`)
      .then(res => res.json())
      .then(data => setMetadata(data))
      .catch(() => setMetadata({ carriers: [], airports: [], status: 'error' }))
  }, [])

  const tabs = [
    { id: 'single', label: '🎯 Single Prediction', icon: '🎯' },
    { id: 'batch', label: '📦 Batch Prediction', icon: '📦' },
    { id: 'history', label: '📜 History', icon: '📜' }
  ]

  return (
    <div className="app">
      <header className="header">
        <div className="header-content">
          <h1>✈️ Airline Delay Predictor</h1>
          <div className="status-badge" data-status={metadata.status}>
            {metadata.status === 'ready' ? '🟢 Ready' : metadata.status === 'loading' ? '🔄 Loading' : '🔴 Offline'}
          </div>
        </div>
        <p className="subtitle">ML-powered flight delay risk prediction</p>
      </header>

      <nav className="tabs">
        {tabs.map(tab => (
          <button
            key={tab.id}
            className={`tab ${activeTab === tab.id ? 'active' : ''}`}
            onClick={() => setActiveTab(tab.id)}
          >
            <span className="tab-icon">{tab.icon}</span>
            <span className="tab-label">{tab.label.split(' ').slice(1).join(' ')}</span>
          </button>
        ))}
      </nav>

      <main className="main-content">
        {activeTab === 'single' && (
          <PredictionForm
            apiUrl={API_URL}
            metadata={metadata}
            onPrediction={setLastPrediction}
            lastPrediction={lastPrediction}
          />
        )}
        {activeTab === 'batch' && (
          <BatchPrediction apiUrl={API_URL} metadata={metadata} />
        )}
        {activeTab === 'history' && (
          <PredictionHistory apiUrl={API_URL} metadata={metadata} />
        )}
      </main>

      <footer className="footer">
        <p>Model: {metadata.model_version || 'N/A'} | Cutoff: {metadata.cutoff || 0.5}</p>
      </footer>
    </div>
  )
}

export default App
