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
    Button,
    FormControl,
    InputLabel,
    Select,
    MenuItem,
    CircularProgress,
    IconButton,
    Tooltip,
} from '@mui/material';
import {
    NotificationsActive as AlertIcon,
    Check as CheckIcon,
    Done as DoneIcon,
    Refresh as RefreshIcon,
} from '@mui/icons-material';
import { getAlerts, acknowledgeAlert, resolveAlert } from '../services/api';
import type { AlertData } from '../services/api';

const severityColors: Record<string, 'error' | 'warning' | 'info' | 'success'> = {
    critical: 'error',
    high: 'warning',
    medium: 'info',
    low: 'success',
};

const statusColors: Record<string, 'default' | 'primary' | 'success'> = {
    active: 'default',
    acknowledged: 'primary',
    resolved: 'success',
};

export default function Alerts() {
    const [alerts, setAlerts] = useState<AlertData[]>([]);
    const [loading, setLoading] = useState(true);
    const [statusFilter, setStatusFilter] = useState<string>('');
    const [severityFilter, setSeverityFilter] = useState<string>('');

    const fetchAlerts = async () => {
        setLoading(true);
        try {
            const params: any = { limit: 100 };
            if (statusFilter) params.status = statusFilter;
            if (severityFilter) params.severity = severityFilter;

            const data = await getAlerts(params);
            setAlerts(data.alerts);
        } catch (error) {
            console.error('Failed to fetch alerts:', error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchAlerts();
    }, [statusFilter, severityFilter]);

    const handleAcknowledge = async (alertId: string) => {
        try {
            await acknowledgeAlert(alertId);
            fetchAlerts();
        } catch (error) {
            console.error('Failed to acknowledge alert:', error);
        }
    };

    const handleResolve = async (alertId: string) => {
        try {
            await resolveAlert(alertId);
            fetchAlerts();
        } catch (error) {
            console.error('Failed to resolve alert:', error);
        }
    };

    return (
        <Box>
            <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
                <Typography variant="h4" fontWeight="bold">
                    <AlertIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
                    Alerts
                </Typography>
                <Button startIcon={<RefreshIcon />} onClick={fetchAlerts}>
                    Refresh
                </Button>
            </Box>

            {/* Filters */}
            <Paper sx={{ p: 2, mb: 3 }}>
                <Box display="flex" gap={2}>
                    <FormControl size="small" sx={{ minWidth: 150 }}>
                        <InputLabel>Status</InputLabel>
                        <Select
                            value={statusFilter}
                            label="Status"
                            onChange={(e) => setStatusFilter(e.target.value)}
                        >
                            <MenuItem value="">All</MenuItem>
                            <MenuItem value="active">Active</MenuItem>
                            <MenuItem value="acknowledged">Acknowledged</MenuItem>
                            <MenuItem value="resolved">Resolved</MenuItem>
                        </Select>
                    </FormControl>
                    <FormControl size="small" sx={{ minWidth: 150 }}>
                        <InputLabel>Severity</InputLabel>
                        <Select
                            value={severityFilter}
                            label="Severity"
                            onChange={(e) => setSeverityFilter(e.target.value)}
                        >
                            <MenuItem value="">All</MenuItem>
                            <MenuItem value="critical">Critical</MenuItem>
                            <MenuItem value="high">High</MenuItem>
                            <MenuItem value="medium">Medium</MenuItem>
                            <MenuItem value="low">Low</MenuItem>
                        </Select>
                    </FormControl>
                </Box>
            </Paper>

            {/* Alerts Table */}
            <TableContainer component={Paper}>
                {loading ? (
                    <Box display="flex" justifyContent="center" p={4}>
                        <CircularProgress />
                    </Box>
                ) : (
                    <Table>
                        <TableHead>
                            <TableRow sx={{ backgroundColor: 'action.hover' }}>
                                <TableCell><strong>Title</strong></TableCell>
                                <TableCell><strong>Type</strong></TableCell>
                                <TableCell><strong>Severity</strong></TableCell>
                                <TableCell><strong>Status</strong></TableCell>
                                <TableCell><strong>Route</strong></TableCell>
                                <TableCell><strong>Prediction</strong></TableCell>
                                <TableCell><strong>Created</strong></TableCell>
                                <TableCell><strong>Actions</strong></TableCell>
                            </TableRow>
                        </TableHead>
                        <TableBody>
                            {alerts.length === 0 ? (
                                <TableRow>
                                    <TableCell colSpan={8} align="center">
                                        <Typography color="text.secondary" py={4}>
                                            No alerts found
                                        </Typography>
                                    </TableCell>
                                </TableRow>
                            ) : (
                                alerts.map((alert) => (
                                    <TableRow key={alert.id} hover>
                                        <TableCell>
                                            <Typography variant="body2" fontWeight="medium">
                                                {alert.title}
                                            </Typography>
                                        </TableCell>
                                        <TableCell>
                                            <Chip label={alert.type} size="small" variant="outlined" />
                                        </TableCell>
                                        <TableCell>
                                            <Chip
                                                label={alert.severity}
                                                size="small"
                                                color={severityColors[alert.severity]}
                                            />
                                        </TableCell>
                                        <TableCell>
                                            <Chip
                                                label={alert.status}
                                                size="small"
                                                color={statusColors[alert.status]}
                                                variant={alert.status === 'active' ? 'filled' : 'outlined'}
                                            />
                                        </TableCell>
                                        <TableCell>
                                            {alert.carrier}/{alert.airport}
                                        </TableCell>
                                        <TableCell>
                                            {alert.prediction ? `${(alert.prediction * 100).toFixed(0)}%` : '-'}
                                        </TableCell>
                                        <TableCell>
                                            {new Date(alert.created_at).toLocaleString()}
                                        </TableCell>
                                        <TableCell>
                                            {alert.status === 'active' && (
                                                <>
                                                    <Tooltip title="Acknowledge">
                                                        <IconButton
                                                            size="small"
                                                            onClick={() => handleAcknowledge(alert.id)}
                                                        >
                                                            <CheckIcon />
                                                        </IconButton>
                                                    </Tooltip>
                                                    <Tooltip title="Resolve">
                                                        <IconButton
                                                            size="small"
                                                            onClick={() => handleResolve(alert.id)}
                                                        >
                                                            <DoneIcon />
                                                        </IconButton>
                                                    </Tooltip>
                                                </>
                                            )}
                                            {alert.status === 'acknowledged' && (
                                                <Tooltip title="Resolve">
                                                    <IconButton
                                                        size="small"
                                                        onClick={() => handleResolve(alert.id)}
                                                    >
                                                        <DoneIcon />
                                                    </IconButton>
                                                </Tooltip>
                                            )}
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
