
import React, { useState } from 'react';
import {
    Box,
    Card,
    CardContent,
    CardHeader,
    Grid,
    TextField,
    MenuItem,
    Button,
    IconButton,
    Typography,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Paper,
    Chip,
    CircularProgress,
    Alert
} from '@mui/material';
import { Delete as DeleteIcon, Add as AddIcon, CloudUpload as UploadIcon } from '@mui/icons-material';
import { batchPredict } from '../services/api';
import type { BatchPredictResponse, PredictionRequest } from '../services/api';

interface BatchPredictionProps {
    carriers: string[];
    airports: string[];
}

const months = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
];

export default function BatchPrediction({ carriers, airports }: BatchPredictionProps) {
    const [items, setItems] = useState<PredictionRequest[]>([
        { carrier: '', airport: '', month: new Date().getMonth() + 1, year: 2026 }
    ]);
    const [loading, setLoading] = useState(false);
    const [results, setResults] = useState<BatchPredictResponse | null>(null);
    const [error, setError] = useState<string | null>(null);

    const addItem = () => {
        if (items.length >= 100) return;
        setItems([...items, { carrier: '', airport: '', month: 1, year: 2026 }]);
    };

    const removeItem = (index: number) => {
        if (items.length <= 1) return;
        setItems(items.filter((_, i) => i !== index));
    };

    const updateItem = (index: number, field: keyof PredictionRequest, value: any) => {
        const updated = [...items];
        updated[index] = { ...updated[index], [field]: value };
        setItems(updated);
    };

    const handleSubmit = async () => {
        setLoading(true);
        setError(null);
        try {
            const data = await batchPredict({ predictions: items });
            setResults(data);
        } catch (err: any) {
            setError(err.message || 'Batch prediction failed');
        } finally {
            setLoading(false);
        }
    };

    return (
        <Box>
            <Card sx={{ mb: 4 }}>
                <CardHeader
                    title="Batch Prediction"
                    subheader={`${items.length} / 100 items`}
                    action={
                        <Button startIcon={<AddIcon />} onClick={addItem} variant="outlined" size="small">
                            Add Prediction
                        </Button>
                    }
                />
                <CardContent>
                    {items.map((item, index) => (
                        <Grid container spacing={2} key={index} alignItems="center" sx={{ mb: 2 }}>
                            <Grid size={{ xs: 3 }}>
                                <TextField
                                    select
                                    fullWidth
                                    label="Carrier"
                                    value={item.carrier}
                                    onChange={(e) => updateItem(index, 'carrier', e.target.value)}
                                    size="small"
                                >
                                    {carriers.map((c) => (
                                        <MenuItem key={c} value={c}>{c}</MenuItem>
                                    ))}
                                </TextField>
                            </Grid>
                            <Grid size={{ xs: 3 }}>
                                <TextField
                                    select
                                    fullWidth
                                    label="Airport"
                                    value={item.airport}
                                    onChange={(e) => updateItem(index, 'airport', e.target.value)}
                                    size="small"
                                >
                                    {airports.map((a) => (
                                        <MenuItem key={a} value={a}>{a}</MenuItem>
                                    ))}
                                </TextField>
                            </Grid>
                            <Grid size={{ xs: 2 }}>
                                <TextField
                                    select
                                    fullWidth
                                    label="Month"
                                    value={item.month}
                                    onChange={(e) => updateItem(index, 'month', e.target.value)}
                                    size="small"
                                >
                                    {months.map((m, i) => (
                                        <MenuItem key={i} value={i + 1}>{m}</MenuItem>
                                    ))}
                                </TextField>
                            </Grid>
                            <Grid size={{ xs: 2 }}>
                                <Typography
                                    variant="body2"
                                    sx={{
                                        display: 'flex',
                                        alignItems: 'center',
                                        height: '40px',
                                        color: 'text.secondary'
                                    }}
                                >
                                    2026
                                </Typography>
                            </Grid>
                            <Grid size={{ xs: 1 }}>
                                <IconButton
                                    onClick={() => removeItem(index)}
                                    disabled={items.length <= 1}
                                    color="error"
                                >
                                    <DeleteIcon />
                                </IconButton>
                            </Grid>
                        </Grid>
                    ))}

                    {error && <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>}

                    <Button
                        variant="contained"
                        fullWidth
                        startIcon={loading ? <CircularProgress size={20} color="inherit" /> : <UploadIcon />}
                        onClick={handleSubmit}
                        disabled={loading || items.some(i => !i.carrier || !i.airport)}
                        sx={{ mt: 3 }}
                    >
                        {loading ? 'Processing...' : `Run ${items.length} Predictions`}
                    </Button>
                </CardContent>
            </Card>

            {results && (
                <Card>
                    <CardHeader title="Batch Results" />
                    <CardContent>
                        <Grid container spacing={2} sx={{ mb: 3 }}>
                            <Grid size={{ xs: 4 }}>
                                <Typography variant="h6" align="center">{results.total}</Typography>
                                <Typography variant="caption" display="block" align="center">Total</Typography>
                            </Grid>
                            <Grid size={{ xs: 4 }}>
                                <Typography variant="h6" align="center" color="success.main">{results.successful}</Typography>
                                <Typography variant="caption" display="block" align="center">Successful</Typography>
                            </Grid>
                            <Grid size={{ xs: 4 }}>
                                <Typography variant="h6" align="center" color="error.main">{results.failed}</Typography>
                                <Typography variant="caption" display="block" align="center">Failed</Typography>
                            </Grid>
                        </Grid>

                        <TableContainer component={Paper} variant="outlined">
                            <Table size="small">
                                <TableHead>
                                    <TableRow>
                                        <TableCell>Carrier</TableCell>
                                        <TableCell>Airport</TableCell>
                                        <TableCell>Date</TableCell>
                                        <TableCell>Prediction</TableCell>
                                        <TableCell>Risk</TableCell>
                                    </TableRow>
                                </TableHead>
                                <TableBody>
                                    {results.results.map((r, i) => (
                                        <TableRow key={i}>
                                            <TableCell>{r.inputs.carrier}</TableCell>
                                            <TableCell>{r.inputs.airport}</TableCell>
                                            <TableCell>{months[r.inputs.month - 1]} {r.inputs.year}</TableCell>
                                            <TableCell>{(r.prediction * 100).toFixed(1)}%</TableCell>
                                            <TableCell>
                                                <Chip
                                                    label={r.risk_category}
                                                    color={
                                                        r.risk_category === 'critical' ? 'error' :
                                                            r.risk_category === 'high' ? 'warning' :
                                                                r.risk_category === 'medium' ? 'info' : 'success'
                                                    }
                                                    size="small"
                                                />
                                            </TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </TableContainer>
                    </CardContent>
                </Card>
            )}
        </Box>
    );
}
