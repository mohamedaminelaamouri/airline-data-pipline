import { Component, ErrorInfo, ReactNode } from 'react';
import { Box, Typography, Button, Paper } from '@mui/material';
import { Refresh as RefreshIcon, ErrorOutline as ErrorIcon } from '@mui/icons-material';

interface Props {
    children: ReactNode;
}

interface State {
    hasError: boolean;
    error: Error | null;
}

class ErrorBoundary extends Component<Props, State> {
    public state: State = {
        hasError: false,
        error: null,
    };

    public static getDerivedStateFromError(error: Error): State {
        return { hasError: true, error };
    }

    public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
        console.error('Uncaught error:', error, errorInfo);
    }

    public render() {
        if (this.state.hasError) {
            return (
                <Box
                    display="flex"
                    justifyContent="center"
                    alignItems="center"
                    minHeight="100vh"
                    p={3}
                >
                    <Paper
                        elevation={3}
                        sx={{
                            p: 4,
                            textAlign: 'center',
                            maxWidth: 500,
                            borderRadius: 4,
                            backgroundColor: 'rgba(26, 26, 46, 0.95)',
                        }}
                    >
                        <ErrorIcon color="error" sx={{ fontSize: 60, mb: 2 }} />
                        <Typography variant="h5" fontWeight="bold" gutterBottom>
                            Something went wrong
                        </Typography>
                        <Typography color="text.secondary" paragraph>
                            The application encountered an unexpected error. This might be due to
                            network issues or resource constraints.
                        </Typography>
                        <Box
                            sx={{
                                bgcolor: 'rgba(0,0,0,0.2)',
                                p: 2,
                                borderRadius: 2,
                                mb: 3,
                                textAlign: 'left',
                                maxHeight: 150,
                                overflow: 'auto',
                            }}
                        >
                            <Typography variant="caption" fontFamily="monospace" color="error.light">
                                {this.state.error?.message}
                            </Typography>
                        </Box>
                        <Button
                            variant="contained"
                            startIcon={<RefreshIcon />}
                            onClick={() => window.location.reload()}
                        >
                            Reload Application
                        </Button>
                    </Paper>
                </Box>
            );
        }

        return this.props.children;
    }
}

export default ErrorBoundary;
