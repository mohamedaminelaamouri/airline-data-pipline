import { useState, useEffect } from 'react';
import {
  ThemeProvider,
  createTheme,
  CssBaseline,
  Box,
  Container,
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
  Paper,
  AppBar,
  Toolbar,
} from '@mui/material';
import { FlightTakeoff as FlightIcon, Send as SendIcon } from '@mui/icons-material';
import { predict, getCarriers, getAirports } from './services/api';
import type { PredictionResult } from './services/api';

const darkTheme = createTheme({
  palette: {
    mode: 'dark',
    primary: { main: '#667eea' },
    secondary: { main: '#f093fb' },
    background: { default: '#0f0f23', paper: '#1a1a2e' },
  },
  typography: {
    fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
  },
  components: {
    MuiCard: { styleOverrides: { root: { borderRadius: 12 } } },
    MuiPaper: { styleOverrides: { root: { borderRadius: 12 } } },
    MuiButton: { styleOverrides: { root: { borderRadius: 8, textTransform: 'none' } } },
  },
});

const riskColors: Record<string, 'error' | 'warning' | 'info' | 'success'> = {
  critical: 'error',
  high: 'warning',
  medium: 'info',
  low: 'success',
};

const months = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December'
];

function App() {
  const [carrier, setCarrier] = useState('');
  const [airport, setAirport] = useState('');
  const [month, setMonth] = useState(new Date().getMonth() + 1);
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
      const response = await predict({ carrier, airport, month, year: 2026 });
      setResult(response);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Prediction failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <ThemeProvider theme={darkTheme}>
      <CssBaseline />
      <Box sx={{ minHeight: '100vh' }}>
        <AppBar position="static" sx={{ backgroundColor: 'background.paper', borderBottom: '1px solid', borderColor: 'divider' }} elevation={0}>
          <Toolbar>
            <FlightIcon sx={{ mr: 1, color: 'primary.main' }} />
            <Typography variant="h6" fontWeight="bold" color="primary.main">
              Airline Delay Prediction
            </Typography>
          </Toolbar>
        </AppBar>

        <Container maxWidth="md" sx={{ py: 4 }}>
          <Grid container spacing={3}>
            {/* Input Form */}
            <Grid size={{ xs: 12, md: 6 }}>
              <Paper sx={{ p: 3 }}>
                <Typography variant="h6" gutterBottom>
                  Flight Details
                </Typography>

                <Grid container spacing={2}>
                  <Grid size={{ xs: 12 }}>
                    <FormControl fullWidth size="small">
                      <InputLabel>Carrier</InputLabel>
                      <Select value={carrier} label="Carrier" onChange={(e) => setCarrier(e.target.value)}>
                        {carriers.map((c) => (
                          <MenuItem key={c} value={c}>{c}</MenuItem>
                        ))}
                      </Select>
                    </FormControl>
                  </Grid>
                  <Grid size={{ xs: 12 }}>
                    <FormControl fullWidth size="small">
                      <InputLabel>Airport</InputLabel>
                      <Select value={airport} label="Airport" onChange={(e) => setAirport(e.target.value)}>
                        {airports.map((a) => (
                          <MenuItem key={a} value={a}>{a}</MenuItem>
                        ))}
                      </Select>
                    </FormControl>
                  </Grid>
                  <Grid size={{ xs: 12, sm: 6 }}>
                    <FormControl fullWidth size="small">
                      <InputLabel>Month</InputLabel>
                      <Select value={month} label="Month" onChange={(e) => setMonth(Number(e.target.value))}>
                        {months.map((m, i) => (
                          <MenuItem key={i} value={i + 1}>{m}</MenuItem>
                        ))}
                      </Select>
                    </FormControl>
                  </Grid>
                  <Grid size={{ xs: 12, sm: 6 }}>
                    <Typography variant="body2" sx={{ display: 'flex', alignItems: 'center', height: '40px', color: 'text.secondary' }}>
                      Year: 2026
                    </Typography>
                  </Grid>
                </Grid>

                {error && <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>}

                <Button
                  variant="contained"
                  fullWidth
                  size="large"
                  endIcon={loading ? <CircularProgress size={20} color="inherit" /> : <SendIcon />}
                  onClick={handleSubmit}
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
                <Card sx={{ height: '100%' }}>
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
                        Model: {result.model_version}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        Inputs: {result.inputs.carrier} @ {result.inputs.airport}, {months[result.inputs.month - 1]} 2026
                      </Typography>
                    </Box>
                  </CardContent>
                </Card>
              ) : (
                <Paper
                  sx={{
                    height: '100%',
                    minHeight: 300,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    bgcolor: 'background.default',
                    color: 'text.secondary',
                    p: 3
                  }}
                >
                  <Typography>
                    Select carrier, airport and month to predict delay risk
                  </Typography>
                </Paper>
              )}
            </Grid>
          </Grid>
        </Container>
      </Box>
    </ThemeProvider>
  );
}

export default App;
