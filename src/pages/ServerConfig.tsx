import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { 
  ChefHat, 
  Server, 
  Wifi, 
  WifiOff, 
  Loader2, 
  Check, 
  AlertCircle,
  Globe,
  Home,
  Cpu
} from 'lucide-react';
import { toast } from 'sonner';

export const ServerConfig = () => {
  const navigate = useNavigate();
  const [serverUrl, setServerUrl] = useState('');
  const [testing, setTesting] = useState(false);
  const [serverStatus, setServerStatus] = useState(null); // null, 'success', 'error'
  const [serverInfo, setServerInfo] = useState(null);
  
  // Preset options
  const presets = [
    { 
      label: 'Laro Cloud',
      url: process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001',
      icon: Globe,
      description: 'Use the hosted version'
    },
    { 
      label: 'Local Server', 
      url: 'http://localhost:8001',
      icon: Home,
      description: 'Running on this device'
    },
    { 
      label: 'Local Network', 
      url: 'http://192.168.1.',
      icon: Wifi,
      description: 'Another device on your network'
    },
  ];

  useEffect(() => {
    // Load saved server URL
    const saved = localStorage.getItem('laro_server_url');
    if (saved) {
      setServerUrl(saved);
      testConnection(saved);
    }
  }, []);

  const testConnection = async (url) => {
    const testUrl = url || serverUrl;
    if (!testUrl) {
      toast.error('Please enter a server URL');
      return;
    }

    // Normalize URL
    let normalizedUrl = testUrl.trim();
    if (!normalizedUrl.startsWith('http')) {
      normalizedUrl = 'http://' + normalizedUrl;
    }
    if (normalizedUrl.endsWith('/')) {
      normalizedUrl = normalizedUrl.slice(0, -1);
    }

    setTesting(true);
    setServerStatus(null);
    setServerInfo(null);

    try {
      const response = await fetch(`${normalizedUrl}/api/health`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
      });

      if (response.ok) {
        const data = await response.json();
        if (data.app === 'Laro') {
          setServerStatus('success');
          setServerInfo(data);
          setServerUrl(normalizedUrl);
          toast.success('Connected to Laro server!');
        } else {
          setServerStatus('error');
          toast.error('Server found but not a Laro instance');
        }
      } else {
        setServerStatus('error');
        toast.error('Server responded with an error');
      }
    } catch (error) {
      console.error('Connection error:', error);
      setServerStatus('error');
      toast.error('Cannot connect to server. Check the URL and ensure the server is running.');
    } finally {
      setTesting(false);
    }
  };

  const handleSave = () => {
    if (serverStatus !== 'success') {
      toast.error('Please test the connection first');
      return;
    }

    localStorage.setItem('laro_server_url', serverUrl);
    toast.success('Server saved! Redirecting...');
    
    // Force reload to apply new server URL
    window.location.href = '/';
  };

  const handlePresetClick = (preset) => {
    setServerUrl(preset.url);
    setServerStatus(null);
    setServerInfo(null);
    
    if (!preset.url.endsWith('.')) {
      testConnection(preset.url);
    }
  };

  const handleSkip = () => {
    // Use default cloud server
    const defaultUrl = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';
    localStorage.setItem('laro_server_url', defaultUrl);
    navigate('/');
  };

  return (
    <div className="min-h-screen bg-cream flex items-center justify-center p-4">
      <motion.div 
        className="w-full max-w-md"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        {/* Logo */}
        <div className="flex justify-center mb-8">
          <img
            src="/mise-banner.svg"
            alt="Laro - Bring order to your larder"
            className="h-14"
          />
        </div>

        {/* Config Card */}
        <div className="bg-white rounded-2xl shadow-card border border-border/60 p-6">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 rounded-xl bg-mise-light flex items-center justify-center">
              <Server className="w-5 h-5 text-mise" />
            </div>
            <div>
              <h1 className="font-heading text-xl font-bold">Connect to Server</h1>
              <p className="text-sm text-muted-foreground">Enter your Laro server address</p>
            </div>
          </div>

          {/* Presets */}
          <div className="space-y-2 mb-6">
            <Label className="text-xs text-muted-foreground uppercase tracking-wide">Quick Options</Label>
            <div className="grid gap-2">
              {presets.map((preset) => {
                const Icon = preset.icon;
                return (
                  <button
                    key={preset.label}
                    onClick={() => handlePresetClick(preset)}
                    className={`flex items-center gap-3 p-3 rounded-xl border transition-all text-left ${
                      serverUrl === preset.url || serverUrl.startsWith(preset.url)
                        ? 'border-mise bg-mise-light'
                        : 'border-border/60 hover:border-mise hover:bg-cream-subtle'
                    }`}
                  >
                    <Icon className="w-5 h-5 text-mise" />
                    <div className="flex-1">
                      <p className="font-medium text-sm">{preset.label}</p>
                      <p className="text-xs text-muted-foreground">{preset.description}</p>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Custom URL Input */}
          <div className="space-y-2 mb-6">
            <Label htmlFor="serverUrl">Server URL</Label>
            <div className="flex gap-2">
              <Input
                id="serverUrl"
                value={serverUrl}
                onChange={(e) => {
                  setServerUrl(e.target.value);
                  setServerStatus(null);
                }}
                placeholder="http://192.168.1.100:8001"
                className="rounded-xl"
                data-testid="server-url-input"
              />
              <Button
                onClick={() => testConnection()}
                disabled={testing || !serverUrl}
                variant="outline"
                className="rounded-xl px-4"
                data-testid="test-connection-btn"
              >
                {testing ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Test'}
              </Button>
            </div>
          </div>

          {/* Connection Status */}
          {serverStatus && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              className={`p-4 rounded-xl mb-6 ${
                serverStatus === 'success' 
                  ? 'bg-mise-light border border-mise/20' 
                  : 'bg-red-50 border border-red-200'
              }`}
            >
              <div className="flex items-center gap-2">
                {serverStatus === 'success' ? (
                  <>
                    <Check className="w-5 h-5 text-mise" />
                    <span className="font-medium text-mise">Connected!</span>
                  </>
                ) : (
                  <>
                    <AlertCircle className="w-5 h-5 text-red-500" />
                    <span className="font-medium text-red-600">Connection Failed</span>
                  </>
                )}
              </div>
              
              {serverInfo && (
                <div className="mt-3 space-y-1 text-sm">
                  <p className="text-muted-foreground">
                    Version: <span className="font-medium text-foreground">{serverInfo.version}</span>
                  </p>
                  <p className="text-muted-foreground flex items-center gap-1">
                    <Cpu className="w-4 h-4" />
                    LLM: <span className="font-medium text-foreground">
                      {serverInfo.llm_provider === 'ollama' ? `Ollama (Local)` : 'OpenAI (Cloud)'}
                    </span>
                  </p>
                </div>
              )}
            </motion.div>
          )}

          {/* Actions */}
          <div className="space-y-3">
            <Button
              onClick={handleSave}
              disabled={serverStatus !== 'success'}
              className="w-full rounded-full bg-mise hover:bg-mise-dark h-12"
              data-testid="save-server-btn"
            >
              Connect & Continue
            </Button>
            <Button
              onClick={handleSkip}
              variant="ghost"
              className="w-full rounded-full"
            >
              Use Cloud Server Instead
            </Button>
          </div>
        </div>

        {/* Help Text */}
        <p className="text-center text-xs text-muted-foreground mt-6 px-4">
          Self-hosting? Run the Laro server on your computer or home server,
          then enter its IP address above.
        </p>
      </motion.div>
    </div>
  );
};
