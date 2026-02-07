import { useState, useEffect } from 'react';
import {
    Box,
    Paper,
    Typography,
    Grid,
    Card,
    CardContent,
    Chip,
    CircularProgress,
    List,
    ListItem,
    ListItemText,
    ListItemIcon,
    Divider,
} from '@mui/material';
import {
    Warning as WarningIcon,
    Error as ErrorIcon,
    CheckCircle as CheckIcon,
    FlightTakeoff as FlightIcon,
    Notifications as NotificationsIcon,
} from '@mui/icons-material';
import { getAlertStats, getAlerts } from '../services/api';
import type { AlertData, AlertStats } from '../services/api';

const severityColors: Record<string, 'error' | 'warning' | 'info' | 'success'> = {
    critical: 'error',
    high: 'warning',
    medium: 'info',
    low: 'success',
};

const severityIcons: Record<string, JSX.Element> = {
    critical: <ErrorIcon color="error" />,
    high: <WarningIcon color="warning" />,
    medium: <NotificationsIcon color="info" />,
    low: <CheckIcon color="success" />,
};

export default function Dashboard() {
    const [stats, setStats] = useState<AlertStats | null>(null);
    const [recentAlerts, setRecentAlerts] = useState<AlertData[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchData = async () => {
            try {
                const [statsData, alertsData] = await Promise.all([
                    getAlertStats(),
                    getAlerts({ limit: 5, status: 'active' }),
                ]);
                setStats(statsData);
                setRecentAlerts(alertsData.alerts);
            } catch (error) {
                console.error('Failed to fetch dashboard data:', error);
            } finally {
                setLoading(false);
            }
        };
        fetchData();
    }, []);

    if (loading) {
        return (
            <Box display="flex" justifyContent="center" alignItems="center" minHeight="60vh">
                <CircularProgress />
            </Box>
        );
    }

    return (
        <Box>
            <Typography variant="h4" gutterBottom fontWeight="bold">
                Dashboard
            </Typography>

            {/* KPI Cards */}
            <Grid container spacing={3} mb={4}>
                <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                    <Card sx={{ background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)', color: 'white' }}>
                        <CardContent>
                            <Typography variant="h3" fontWeight="bold">
                                {stats?.total || 0}
                            </Typography>
                            <Typography variant="body2" sx={{ opacity: 0.9 }}>
                                Total Alerts
                            </Typography>
                        </CardContent>
                    </Card>
                </Grid>
                <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                    <Card sx={{ background: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)', color: 'white' }}>
                        <CardContent>
                            <Typography variant="h3" fontWeight="bold">
                                {stats?.active || 0}
                            </Typography>
                            <Typography variant="body2" sx={{ opacity: 0.9 }}>
                                Active Alerts
                            </Typography>
                        </CardContent>
                    </Card>
                </Grid>
                <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                    <Card sx={{ background: 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)', color: 'white' }}>
                        <CardContent>
                            <Typography variant="h3" fontWeight="bold">
                                {stats?.acknowledged || 0}
                            </Typography>
                            <Typography variant="body2" sx={{ opacity: 0.9 }}>
                                Acknowledged
                            </Typography>
                        </CardContent>
                    </Card>
                </Grid>
                <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                    <Card sx={{ background: 'linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)', color: 'white' }}>
                        <CardContent>
                            <Typography variant="h3" fontWeight="bold">
                                {stats?.resolved || 0}
                            </Typography>
                            <Typography variant="body2" sx={{ opacity: 0.9 }}>
                                Resolved
                            </Typography>
                        </CardContent>
                    </Card>
                </Grid>
            </Grid>

            {/* Alerts by Severity */}
            <Grid container spacing={3}>
                <Grid size={{ xs: 12, md: 6 }}>
                    <Paper sx={{ p: 3 }}>
                        <Typography variant="h6" gutterBottom>
                            Alerts by Severity
                        </Typography>
                        <Box display="flex" gap={2} flexWrap="wrap">
                            {stats?.by_severity &&
                                Object.entries(stats.by_severity).map(([severity, count]) => (
                                    <Chip
                                        key={severity}
                                        icon={severityIcons[severity]}
                                        label={`${severity}: ${count}`}
                                        color={severityColors[severity]}
                                        variant="outlined"
                                    />
                                ))}
                        </Box>
                    </Paper>
                </Grid>

                <Grid size={{ xs: 12, md: 6 }}>
                    <Paper sx={{ p: 3 }}>
                        <Typography variant="h6" gutterBottom>
                            Alerts by Type
                        </Typography>
                        <Box display="flex" gap={2} flexWrap="wrap">
                            {stats?.by_type &&
                                Object.entries(stats.by_type).map(([type, count]) => (
                                    <Chip key={type} label={`${type}: ${count}`} variant="outlined" />
                                ))}
                        </Box>
                    </Paper>
                </Grid>
            </Grid>

            {/* Recent Active Alerts */}
            <Paper sx={{ p: 3, mt: 3 }}>
                <Typography variant="h6" gutterBottom>
                    <FlightIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
                    Recent Active Alerts
                </Typography>
                <Divider sx={{ mb: 2 }} />
                {recentAlerts.length === 0 ? (
                    <Typography color="text.secondary">No active alerts</Typography>
                ) : (
                    <List>
                        {recentAlerts.map((alert) => (
                            <ListItem key={alert.id}>
                                <ListItemIcon>{severityIcons[alert.severity]}</ListItemIcon>
                                <ListItemText
                                    primary={alert.title}
                                    secondary={`${alert.carrier}/${alert.airport} - ${new Date(alert.created_at).toLocaleString()}`}
                                />
                                <Chip
                                    label={`${(alert.prediction! * 100).toFixed(0)}%`}
                                    color={severityColors[alert.severity]}
                                    size="small"
                                />
                            </ListItem>
                        ))}
                    </List>
                )}
            </Paper>
        </Box>
    );
}
