import React, { useState, useEffect } from "react";
import { View, Text, Modal, Image, Button, ActivityIndicator, StyleSheet, Pressable } from "react-native";
import { getTunnelStatus, startTunnel, getQrCodeUrl } from "../api";


interface Props {
  visible: boolean;
  onClose: () => void;
}


export default function TunnelQRModal({ visible, onClose }: Props) {
  const [tunnelUrl, setTunnelUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [qrCodeUrl, setQrCodeUrl] = useState<string | null>(null);


  useEffect(() => {
    if (visible) {
      checkTunnel();
    }
  }, [visible]);


  async function checkTunnel() {
    setLoading(true);
    setError(null);
    try {
      const status = await getTunnelStatus();
      if (status.ok && status.url) {
        setTunnelUrl(status.url);
        setQrCodeUrl(getQrCodeUrl(status.url));
      } else {
        // No tunnel active, try to start one
        const start = await startTunnel();
        if (start.ok && start.url) {
          setTunnelUrl(start.url);
          setQrCodeUrl(getQrCodeUrl(start.url));
        } else {
          setError(start.message || "Could not start tunnel. Run 'ngrok http 8001' manually.");
          // Still show QR for local URL
          setQrCodeUrl(getQrCodeUrl());
        }
      }
    } catch (e: any) {
      setError(String(e));
      setQrCodeUrl(getQrCodeUrl());
    } finally {
      setLoading(false);
    }
  }


  return (
    <Modal visible={visible} animationType="slide" transparent={true}>
      <View style={styles.overlay}>
        <View style={styles.container}>
          <View style={styles.header}>
            <Text style={styles.title}>API Connection</Text>
            <Pressable onPress={onClose} style={styles.closeButton}>
              <Text style={styles.closeText}>✕</Text>
            </Pressable>
          </View>

          {loading ? (
            <View style={styles.center}>
              <ActivityIndicator size="large" />
              <Text style={styles.loadingText}>Checking tunnel...</Text>
            </View>
          ) : error ? (
            <View style={styles.center}>
              <Text style={styles.errorText}>{error}</Text>
              <Text style={styles.hint}>
                To use from a different network, run: ngrok http 8001
              </Text>
            </View>
          ) : null}

          {tunnelUrl ? (
            <View style={styles.center}>
              <Text style={styles.urlLabel}>Tunnel URL:</Text>
              <Text style={styles.urlText} selectable>{tunnelUrl}</Text>
            </View>
          ) : null}

          {qrCodeUrl ? (
            <View style={styles.center}>
              <Text style={styles.qrLabel}>Scan to configure API URL:</Text>
              <Image source={{ uri: qrCodeUrl }} style={styles.qrCode} />
              <Text style={styles.hint}>
                Scan this QR code with another device to connect to this API
              </Text>
            </View>
          ) : null}

          <View style={styles.actions}>
            <Button title="Refresh" onPress={checkTunnel} />
            <View style={{ width: 10 }} />
            <Button title="Close" onPress={onClose} />
          </View>
        </View>
      </View>
    </Modal>
  );
}


const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.5)",
    justifyContent: "center",
    alignItems: "center",
  },
  container: {
    backgroundColor: "white",
    borderRadius: 12,
    padding: 20,
    width: "90%",
    maxWidth: 400,
    maxHeight: "80%",
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 20,
  },
  title: {
    fontSize: 20,
    fontWeight: "700",
  },
  closeButton: {
    padding: 5,
  },
  closeText: {
    fontSize: 24,
    color: "#666",
  },
  center: {
    alignItems: "center",
    marginVertical: 10,
  },
  loadingText: {
    marginTop: 10,
    color: "#666",
  },
  errorText: {
    color: "#d00",
    textAlign: "center",
    marginBottom: 10,
  },
  urlLabel: {
    fontSize: 14,
    fontWeight: "600",
    marginBottom: 5,
  },
  urlText: {
    fontSize: 12,
    color: "#0066cc",
    textAlign: "center",
    marginBottom: 15,
    padding: 8,
    backgroundColor: "#f0f0f0",
    borderRadius: 4,
  },
  qrLabel: {
    fontSize: 14,
    fontWeight: "600",
    marginBottom: 10,
  },
  qrCode: {
    width: 200,
    height: 200,
    marginVertical: 10,
  },
  hint: {
    fontSize: 12,
    color: "#666",
    textAlign: "center",
    marginTop: 10,
  },
  actions: {
    flexDirection: "row",
    justifyContent: "center",
    marginTop: 20,
  },
});

