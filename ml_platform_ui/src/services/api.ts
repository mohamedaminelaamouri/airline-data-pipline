import axios from 'axios';

const API_BASE_URL = 'http://localhost:8001';

const api = axios.create({
    baseURL: API_BASE_URL,
    headers: {
        'Content-Type': 'application/json',
    },
});

// Types
export interface PredictionRequest {
    carrier: string;
    airport: string;
    month: number;
    year: number;
}

export interface PredictionResult {
    request_id: string;
    prediction: number;
    risk_category: string;
    model_version: string;
    timestamp: string;
    inputs: {
        carrier: string;
        airport: string;
        month: number;
        year: number;
    };
}

export interface AlertData {
    id: string;
    type: string;
    severity: string;
    status: string;
    title: string;
    message: string;
    carrier?: string;
    airport?: string;
    year?: number;
    month?: number;
    prediction?: number;
    created_at: string;
    acknowledged_at?: string;
}

export interface AlertStats {
    total: number;
    active: number;
    acknowledged: number;
    resolved: number;
    by_severity: Record<string, number>;
    by_type: Record<string, number>;
}

// API Functions
export const predict = async (data: PredictionRequest): Promise<PredictionResult> => {
    const response = await api.post('/predict', data);
    return response.data;
};

export const getAlerts = async (params?: {
    type?: string;
    severity?: string;
    status?: string;
    limit?: number;
}): Promise<{ alerts: AlertData[]; count: number }> => {
    const response = await api.get('/alerts', { params });
    return response.data;
};

export const getAlertStats = async (): Promise<AlertStats> => {
    const response = await api.get('/alerts/stats');
    return response.data;
};

export const acknowledgeAlert = async (alertId: string): Promise<void> => {
    await api.put(`/alerts/${alertId}/acknowledge`);
};

export const resolveAlert = async (alertId: string): Promise<void> => {
    await api.put(`/alerts/${alertId}/resolve`);
};

export const getPredictionHistory = async (limit: number = 50): Promise<{ predictions: any[] }> => {
    const response = await api.get('/predictions/history', { params: { limit } });
    return response.data;
};

export const getCarriers = async (): Promise<string[]> => {
    try {
        const response = await api.get('/carriers');
        return response.data.carriers || [];
    } catch {
        return ['AA', 'DL', 'UA', 'WN', 'B6', 'AS', 'NK', 'F9'];
    }
};

export const getAirports = async (): Promise<string[]> => {
    try {
        const response = await api.get('/airports');
        return response.data.airports || [];
    } catch {
        return ['ATL', 'DFW', 'DEN', 'ORD', 'LAX', 'CLT', 'LAS', 'PHX', 'MIA', 'SEA', 'JFK'];
    }
};

export const getHealth = async (): Promise<{ status: string }> => {
    const response = await api.get('/health');
    return response.data;
};

export default api;
