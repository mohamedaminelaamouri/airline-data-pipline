
import { useState, useEffect } from 'react';
import {
    Box,
    Paper,
    Typography,
    TextField,
    Button,
    Select,
    MenuItem,
    FormControl,
    InputLabel,
    Grid,
    Card,
    CardContent,
    Alert,
    CircularProgress,
    Chip,
    Tabs,
    Tab
} from '@mui/material';
import { FlightTakeoff as FlightIcon, Send as SendIcon } from '@mui/icons-material';
import { predict, getCarriers, getAirports } from '../services/api';
import type { PredictionResult } from '../services/api';
import BatchPrediction from '../components/BatchPrediction';

const riskColors: Record<string, 'error' | 'warning' | 'info' | 'success'> = {
    critical: 'error',
    high: 'warning',
    medium: 'info',
    low: 'success',
};

export default function Prediction() {
    const [tab, setTab] = useState(0);
    const [carrier, setCarrier] = useState('');
    const [airport, setAirport] = useState('');
    const [month, setMonth] = useState(new Date().getMonth() + 1);
    const [year] = useState(2026);
    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState<PredictionResult | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [carriers, setCarriers] = useState<string[]>([]);
    const [airports, setAirports] = useState<string[]>([]);

    useEffect(() => {
        const loadOptions = async () => {
            const [c, a] = await Promise.all([getCarriers(), getAirports()]);
            setCarriers(c);
            setAirports(a);
        };
        loadOptions();
    }, []);

    const handleSingleSubmit = async () => {
        if (!carrier || !airport) {
            setError('Please select carrier and airport');
            return;
        }

        setLoading(true);
        setError(null);
        try {
            const response = await predict({ carrier, airport, month, year });
            setResult(response);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Prediction failed');
        } finally {
            setLoading(false);
        }
    };

    const months = [
        'January', 'February', 'March', 'April', 'May', 'June',
        'July', 'August', 'September', 'October', 'November', 'December'
    ];

    return (
        <Box>
            <Typography variant="h4" gutterBottom fontWeight="bold" sx={{ mb: 3 }}>
                <FlightIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
                Delay Prediction
            </Typography>

            <Paper sx={{ mb: 3 }}>
                <Tabs
                    value={tab}
                    onChange={(_, v) => setTab(v)}
                    variant="fullWidth"
                    textColor="secondary"
                    indicatorColor="secondary"
                >
                    <Tab label="🎯 Single Prediction" />
                    <Tab label="📦 Batch Prediction" />
                </Tabs>
            </Paper>

            {tab === 0 && (
                <Grid container spacing={3}>
                    {/* Input Form */}
                    <Grid size={{ xs: 12, md: 6 }}>
                        <Paper sx={{ p: 3 }}>
                            <Typography variant="h6" gutterBottom>
                                Enter Flight Details
                            </Typography>

                            <Grid container spacing={2}>
                                <Grid size={{ xs: 12, sm: 6 }}>
                                    <FormControl fullWidth size="small">
                                        <InputLabel>Carrier</InputLabel>
                                        <Select
                                            value={carrier}
                                            label="Carrier"
                                            onChange={(e) => setCarrier(e.target.value)}
                                        >
                                            {carriers.map((c) => (
                                                <MenuItem key={c} value={c}>{c}</MenuItem>
                                            ))}
                                        </Select>
                                    </FormControl>
                                </Grid>
                                <Grid size={{ xs: 12, sm: 6 }}>
                                    <FormControl fullWidth size="small">
                                        <InputLabel>Airport</InputLabel>
                                        <Select
                                            value={airport}
                                            label="Airport"
                                            onChange={(e) => setAirport(e.target.value)}
                                        >
                                            {airports.map((a) => (
                                                <MenuItem key={a} value={a}>{a}</MenuItem>
                                            ))}
                                        </Select>
                                    </FormControl>
                                </Grid>
                                <Grid size={{ xs: 12, sm: 6 }}>
                                    <FormControl fullWidth size="small">
                                        <InputLabel>Month</InputLabel>
                                        <Select
                                            value={month}
                                            label="Month"
                                            onChange={(e) => setMonth(Number(e.target.value))}
                                        >
                                            {months.map((m, i) => (
                                                <MenuItem key={i} value={i + 1}>{m}</MenuItem>
                                            ))}
                                        </Select>
                                    </FormControl>
                                </Grid>
                                <Grid size={{ xs: 12, sm: 6 }}>
                                    <Typography
                                        variant="body2"
                                        sx={{
                                            display: 'flex',
                                            alignItems: 'center',
                                            height: '40px',
                                            color: 'text.secondary'
                                        }}
                                    >
                                        Year: 2026 (fixed)
                                    </Typography>
                                </Grid>
                            </Grid>

                            {error && (
                                <Alert severity="error" sx={{ mt: 2 }}>
                                    {error}
                                </Alert>
                            )}

                            <Button
                                variant="contained"
                                fullWidth
                                size="large"
                                endIcon={loading ? <CircularProgress size={20} color="inherit" /> : <SendIcon />}
                                onClick={handleSingleSubmit}
                                disabled={loading}
                                sx={{ mt: 3 }}
                            >
                                {loading ? 'Processing...' : 'Predict Delay Risk'}
                            </Button>
                        </Paper>
                    </Grid>

                    {/* Result Card */}
                    <Grid size={{ xs: 12, md: 6 }}>
                        {result ? (
                            <Card sx={{ height: '100%', position: 'relative', overflow: 'visible' }}>
                                <CardContent sx={{ textAlign: 'center', py: 5 }}>
                                    <Typography variant="overline" color="text.secondary">
                                        Probability of Delay
                                    </Typography>
                                    <Typography
                                        variant="h1"
                                        component="div"
                                        color={`${riskColors[result.risk_category]}.main`}
                                        sx={{ fontWeight: 'bold', mb: 2 }}
                                    >
                                        {(result.prediction * 100).toFixed(1)}%
                                    </Typography>

                                    <Chip
                                        label={`${result.risk_category.toUpperCase()} RISK`}
                                        color={riskColors[result.risk_category]}
                                        sx={{ px: 2, py: 1, fontWeight: 'bold' }}
                                    />

                                    <Box sx={{ mt: 4, textAlign: 'left', bgcolor: 'background.default', p: 2, borderRadius: 1 }}>
                                        <Typography variant="body2" color="text.secondary">
                                            Request ID: {result.request_id}
                                        </Typography>
                                        <Typography variant="body2" color="text.secondary">
                                            Model: {result.model_version}
                                        </Typography>
                                        <Typography variant="body2" color="text.secondary">
                                            Timestamp: {new Date(result.timestamp).toLocaleString()}
                                        </Typography>
                                    </Box>
                                </CardContent>
                            </Card>
                        ) : (
                            <Paper
                                sx={{
                                    height: '100%',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    bgcolor: 'background.default',
                                    color: 'text.secondary',
                                    p: 3
                                }}
                            >
                                <Typography>
                                    Submit the form to see prediction result
                                </Typography>
                            </Paper>
                        )}
                    </Grid>
                </Grid>
            )}

            {tab === 1 && (
                <BatchPrediction carriers={carriers} airports={airports} />
            )}
        </Box>
    );
}
