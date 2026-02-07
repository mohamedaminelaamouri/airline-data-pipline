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
} from '@mui/material';
import { FlightTakeoff as FlightIcon, Send as SendIcon } from '@mui/icons-material';
import { predict, getCarriers, getAirports } from '../services/api';
import type { PredictionResult } from '../services/api';

const riskColors: Record<string, 'error' | 'warning' | 'info' | 'success'> = {
    critical: 'error',
    high: 'warning',
    medium: 'info',
    low: 'success',
};

export default function Prediction() {
    const [carrier, setCarrier] = useState('');
    const [airport, setAirport] = useState('');
    const [month, setMonth] = useState(new Date().getMonth() + 1);
    const [year, setYear] = useState(new Date().getFullYear());
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

    const handleSubmit = async () => {
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
            <Typography variant="h4" gutterBottom fontWeight="bold">
                <FlightIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
                Delay Prediction
            </Typography>

            <Grid container spacing={3}>
                {/* Input Form */}
                <Grid size={{ xs: 12, md: 6 }}>
                    <Paper sx={{ p: 3 }}>
                        <Typography variant="h6" gutterBottom>
                            Enter Flight Details
                        </Typography>

                        <Grid container spacing={2}>
                            <Grid size={{ xs: 12, sm: 6 }}>
                                <FormControl fullWidth>
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
                                <FormControl fullWidth>
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
                                <FormControl fullWidth>
                                    <InputLabel>Month</InputLabel>
                                    <Select
                                        value={month}
                                        label="Month"
                                        onChange={(e) => setMonth(Number(e.target.value))}
                                    >
                                        {months.map((m, i) => (
                                            <MenuItem key={i + 1} value={i + 1}>{m}</MenuItem>
                                        ))}
                                    </Select>
                                </FormControl>
                            </Grid>
                            <Grid size={{ xs: 12, sm: 6 }}>
                                <TextField
                                    fullWidth
                                    label="Year"
                                    type="number"
                                    value={year}
                                    onChange={(e) => setYear(Number(e.target.value))}
                                    inputProps={{ min: 2020, max: 2030 }}
                                />
                            </Grid>
                        </Grid>

                        <Button
                            variant="contained"
                            fullWidth
                            size="large"
                            onClick={handleSubmit}
                            disabled={loading}
                            startIcon={loading ? <CircularProgress size={20} color="inherit" /> : <SendIcon />}
                            sx={{ mt: 3, py: 1.5 }}
                        >
                            {loading ? 'Predicting...' : 'Get Prediction'}
                        </Button>

                        {error && (
                            <Alert severity="error" sx={{ mt: 2 }}>
                                {error}
                            </Alert>
                        )}
                    </Paper>
                </Grid>

                {/* Result */}
                <Grid size={{ xs: 12, md: 6 }}>
                    {result && (
                        <Card
                            sx={{
                                background: `linear-gradient(135deg, ${result.risk_category === 'critical' ? '#f5576c, #f093fb' :
                                    result.risk_category === 'high' ? '#f093fb, #f5576c' :
                                        result.risk_category === 'medium' ? '#4facfe, #00f2fe' :
                                            '#43e97b, #38f9d7'
                                    })`,
                                color: 'white',
                                minHeight: 300,
                            }}
                        >
                            <CardContent>
                                <Typography variant="h6" sx={{ opacity: 0.9 }}>
                                    Prediction Result
                                </Typography>
                                <Box textAlign="center" py={3}>
                                    <Typography variant="h1" fontWeight="bold">
                                        {(result.prediction * 100).toFixed(1)}%
                                    </Typography>
                                    <Chip
                                        label={result.risk_category.toUpperCase()}
                                        sx={{
                                            mt: 2,
                                            fontSize: '1.2rem',
                                            py: 2,
                                            px: 3,
                                            backgroundColor: 'rgba(255,255,255,0.2)',
                                            color: 'white',
                                        }}
                                    />
                                </Box>
                                <Box mt={3}>
                                    <Typography variant="body2" sx={{ opacity: 0.8 }}>
                                        Route: {result.inputs.carrier} @ {result.inputs.airport}
                                    </Typography>
                                    <Typography variant="body2" sx={{ opacity: 0.8 }}>
                                        Period: {months[result.inputs.month - 1]} {result.inputs.year}
                                    </Typography>
                                    <Typography variant="body2" sx={{ opacity: 0.8 }}>
                                        Model: {result.model_version}
                                    </Typography>
                                </Box>
                            </CardContent>
                        </Card>
                    )}

                    {!result && (
                        <Paper sx={{ p: 4, textAlign: 'center', minHeight: 300, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                            <Box>
                                <FlightIcon sx={{ fontSize: 60, color: 'text.secondary', opacity: 0.3 }} />
                                <Typography color="text.secondary" mt={2}>
                                    Enter flight details to get a delay prediction
                                </Typography>
                            </Box>
                        </Paper>
                    )}
                </Grid>
            </Grid>
        </Box>
    );
}
