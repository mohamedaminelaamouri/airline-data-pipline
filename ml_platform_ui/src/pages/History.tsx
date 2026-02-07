import { useState, useEffect } from 'react';
import {
    Box,
    Paper,
    Typography,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Chip,
    CircularProgress,
    Button,
} from '@mui/material';
import { History as HistoryIcon, Refresh as RefreshIcon } from '@mui/icons-material';
import { getPredictionHistory } from '../services/api';

const riskColors: Record<string, 'error' | 'warning' | 'info' | 'success'> = {
    critical: 'error',
    high: 'warning',
    medium: 'info',
    low: 'success',
};

export default function History() {
    const [predictions, setPredictions] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);

    const fetchHistory = async () => {
        setLoading(true);
        try {
            const data = await getPredictionHistory(100);
            setPredictions(data.predictions || []);
        } catch (error) {
            console.error('Failed to fetch history:', error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchHistory();
    }, []);

    return (
        <Box>
            <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
                <Typography variant="h4" fontWeight="bold">
                    <HistoryIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
                    Prediction History
                </Typography>
                <Button startIcon={<RefreshIcon />} onClick={fetchHistory}>
                    Refresh
                </Button>
            </Box>

            <TableContainer component={Paper}>
                {loading ? (
                    <Box display="flex" justifyContent="center" p={4}>
                        <CircularProgress />
                    </Box>
                ) : (
                    <Table>
                        <TableHead>
                            <TableRow sx={{ backgroundColor: 'action.hover' }}>
                                <TableCell><strong>Carrier</strong></TableCell>
                                <TableCell><strong>Airport</strong></TableCell>
                                <TableCell><strong>Month</strong></TableCell>
                                <TableCell><strong>Year</strong></TableCell>
                                <TableCell><strong>Prediction</strong></TableCell>
                                <TableCell><strong>Risk</strong></TableCell>
                                <TableCell><strong>Timestamp</strong></TableCell>
                            </TableRow>
                        </TableHead>
                        <TableBody>
                            {predictions.length === 0 ? (
                                <TableRow>
                                    <TableCell colSpan={7} align="center">
                                        <Typography color="text.secondary" py={4}>
                                            No prediction history found
                                        </Typography>
                                    </TableCell>
                                </TableRow>
                            ) : (
                                predictions.map((p, i) => (
                                    <TableRow key={p.request_id || i} hover>
                                        <TableCell>{p.carrier}</TableCell>
                                        <TableCell>{p.airport}</TableCell>
                                        <TableCell>{p.month}</TableCell>
                                        <TableCell>{p.year}</TableCell>
                                        <TableCell>
                                            <Typography fontWeight="bold">
                                                {(p.prediction * 100).toFixed(1)}%
                                            </Typography>
                                        </TableCell>
                                        <TableCell>
                                            <Chip
                                                label={p.risk_category}
                                                size="small"
                                                color={riskColors[p.risk_category]}
                                            />
                                        </TableCell>
                                        <TableCell>
                                            {new Date(p.timestamp).toLocaleString()}
                                        </TableCell>
                                    </TableRow>
                                ))
                            )}
                        </TableBody>
                    </Table>
                )}
            </TableContainer>
        </Box>
    );
}
