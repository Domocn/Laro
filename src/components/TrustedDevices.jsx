import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Button } from './ui/button';
import { trustedDevicesApi } from '../lib/api';
import {
  Smartphone,
  Monitor,
  Tablet,
  Trash2,
  Loader2,
  Shield,
  Plus,
  Clock,
  Wifi
} from 'lucide-react';
import { toast } from 'sonner';
import { format } from 'date-fns';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from './ui/alert-dialog';

const getDeviceIcon = (deviceName) => {
  const name = deviceName?.toLowerCase() || '';
  if (name.includes('iphone') || name.includes('android') || name.includes('mobile')) {
    return Smartphone;
  }
  if (name.includes('ipad') || name.includes('tablet')) {
    return Tablet;
  }
  return Monitor;
};

export const TrustedDevices = () => {
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [trusting, setTrusting] = useState(false);
  const [revoking, setRevoking] = useState(null);
  const [showRevokeAll, setShowRevokeAll] = useState(false);
  const [trustToken, setTrustToken] = useState(null);

  useEffect(() => {
    loadDevices();
    // Check for existing trust token
    const token = localStorage.getItem('laro_device_trust_token');
    if (token) setTrustToken(token);
  }, []);

  const loadDevices = async () => {
    try {
      const res = await trustedDevicesApi.list();
      setDevices(res.data.devices || []);
    } catch (err) {
      console.error('Failed to load devices:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleTrustDevice = async () => {
    setTrusting(true);
    try {
      const res = await trustedDevicesApi.trustDevice();
      const newToken = res.data.trust_token;
      
      // Save token to localStorage
      localStorage.setItem('laro_device_trust_token', newToken);
      setTrustToken(newToken);
      
      toast.success('This device is now trusted for 2FA bypass');
      loadDevices();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Couldn\'t trust this device. Please try again. (E-TD001)');
    } finally {
      setTrusting(false);
    }
  };

  const handleRevoke = async (deviceId) => {
    setRevoking(deviceId);
    try {
      await trustedDevicesApi.revoke(deviceId);
      toast.success('Device trust revoked');
      
      // If it was the current device, clear the token
      const device = devices.find(d => d.id === deviceId);
      if (device && trustToken) {
        localStorage.removeItem('laro_device_trust_token');
        setTrustToken(null);
      }
      
      loadDevices();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Couldn\'t revoke that device. Please try again. (E-TD002)');
    } finally {
      setRevoking(null);
    }
  };

  const handleRevokeAll = async () => {
    try {
      await trustedDevicesApi.revokeAll();
      localStorage.removeItem('laro_device_trust_token');
      setTrustToken(null);
      toast.success('All device trusts revoked');
      loadDevices();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Couldn\'t revoke all devices. Please try again. (E-TD003)');
    } finally {
      setShowRevokeAll(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="w-6 h-6 animate-spin text-laro" />
      </div>
    );
  }

  return (
    <div className="space-y-4" data-testid="trusted-devices">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-medium flex items-center gap-2">
            <Shield className="w-5 h-5 text-laro" />
            Trusted Devices
          </h3>
          <p className="text-sm text-muted-foreground mt-1">
            Trusted devices can skip 2FA verification for 30 days
          </p>
        </div>
        <Button
          onClick={handleTrustDevice}
          disabled={trusting}
          className="rounded-full bg-laro hover:bg-laro-dark"
          size="sm"
        >
          {trusting ? (
            <Loader2 className="w-4 h-4 animate-spin mr-2" />
          ) : (
            <Plus className="w-4 h-4 mr-2" />
          )}
          Trust This Device
        </Button>
      </div>

      {/* Current Device Status */}
      {trustToken && (
        <div className="p-3 bg-teal-light rounded-xl flex items-center gap-3">
          <Wifi className="w-5 h-5 text-teal" />
          <div className="flex-1">
            <p className="text-sm font-medium text-teal-dark">This device is trusted</p>
            <p className="text-xs text-teal-dark/70">2FA verification is bypassed</p>
          </div>
        </div>
      )}

      {/* Device List */}
      {devices.length === 0 ? (
        <div className="text-center py-8 text-muted-foreground">
          <Monitor className="w-12 h-12 mx-auto mb-2 opacity-50" />
          <p>No trusted devices</p>
          <p className="text-sm">Trust this device to skip 2FA next time</p>
        </div>
      ) : (
        <div className="space-y-2">
          {devices.map((device) => {
            const Icon = getDeviceIcon(device.device_name);
            return (
              <motion.div
                key={device.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="flex items-center justify-between p-3 bg-muted/50 rounded-xl"
              >
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-laro-light flex items-center justify-center">
                    <Icon className="w-5 h-5 text-laro" />
                  </div>
                  <div>
                    <p className="font-medium text-sm">{device.device_name}</p>
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {device.days_remaining} days remaining
                      </span>
                      <span>•</span>
                      <span>Last used {format(new Date(device.last_used), 'MMM d')}</span>
                    </div>
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleRevoke(device.id)}
                  disabled={revoking === device.id}
                  className="text-destructive hover:text-destructive hover:bg-destructive/10"
                >
                  {revoking === device.id ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Trash2 className="w-4 h-4" />
                  )}
                </Button>
              </motion.div>
            );
          })}
        </div>
      )}

      {/* Revoke All */}
      {devices.length > 0 && (
        <div className="pt-4 border-t border-border/60">
          <Button
            variant="outline"
            onClick={() => setShowRevokeAll(true)}
            className="w-full rounded-full text-destructive border-destructive/30 hover:bg-destructive/10"
          >
            <Trash2 className="w-4 h-4 mr-2" />
            Revoke All Trusted Devices
          </Button>
        </div>
      )}

      {/* Revoke All Confirmation */}
      <AlertDialog open={showRevokeAll} onOpenChange={setShowRevokeAll}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Revoke All Trusted Devices?</AlertDialogTitle>
            <AlertDialogDescription>
              This will require 2FA verification on all your devices again. 
              You cannot undo this action.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="rounded-full">Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleRevokeAll}
              className="rounded-full bg-destructive hover:bg-destructive/90"
            >
              Revoke All
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};
