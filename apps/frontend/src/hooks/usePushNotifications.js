/**
 * usePushNotifications — hook para gerenciar notificações push via FCM (Onda 7a).
 *
 * Regras de segurança:
 * - Permissão solicitada APENAS por ação explícita do usuário (nunca ao montar).
 * - Fallback gracioso em navegadores sem suporte.
 * - Token registrado/removido via API (com CSRF).
 * - Reatribuição de token ao login — backend trata automaticamente.
 */

import { useState, useEffect, useCallback } from "react";
import { api } from "../services/api";
import { getFirebaseMessaging, getVapidKey } from "../services/firebase";

export function usePushNotifications({ enabled = false } = {}) {
  const [permission, setPermission] = useState(
    typeof Notification !== "undefined" ? Notification.permission : "unsupported"
  );
  const [isSupported, setIsSupported] = useState(false);
  const [isRegistered, setIsRegistered] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    // Verifica suporte ao montar
    if (typeof Notification === "undefined" || !("serviceWorker" in navigator)) {
      setIsSupported(false);
      return;
    }
    setIsSupported(true);
  }, []);

  /**
   * requestAndRegister — solicita permissão e registra token.
   * Deve ser chamado APENAS por ação explícita do usuário (clique de botão).
   */
  const requestAndRegister = useCallback(async () => {
    if (!isSupported || !enabled) return;

    setLoading(true);
    setError(null);

    try {
      const permResult = await Notification.requestPermission();
      setPermission(permResult);

      if (permResult !== "granted") {
        setLoading(false);
        return;
      }

      const messaging = await getFirebaseMessaging();
      if (!messaging) {
        setLoading(false);
        return;
      }

      const { getToken } = await import("firebase/messaging");
      const vapidKey = getVapidKey();

      const swRegistration = await navigator.serviceWorker.register(
        "/firebase-messaging-sw.js"
      );

      const token = await getToken(messaging, {
        vapidKey: vapidKey || undefined,
        serviceWorkerRegistration: swRegistration,
      });

      if (token) {
        await api.post("/api/notifications/devices/", {
          token,
          platform: "web",
          device_name: navigator.userAgent.slice(0, 200),
        });
        setIsRegistered(true);
      }
    } catch (err) {
      console.warn("[usePushNotifications] Falha:", err);
      setError(err?.message || "Falha ao registrar notificações push.");
    } finally {
      setLoading(false);
    }
  }, [isSupported, enabled]);

  /**
   * unregister — remove token FCM ao desativar ou fazer logout.
   */
  const unregister = useCallback(async () => {
    setLoading(true);
    try {
      const messaging = await getFirebaseMessaging();
      if (messaging) {
        const { getToken, deleteToken } = await import("firebase/messaging");
        const vapidKey = getVapidKey();
        const token = await getToken(messaging, { vapidKey: vapidKey || undefined }).catch(() => null);
        if (token) {
          await api.delete("/api/notifications/devices/", { data: { token } }).catch(() => null);
          await deleteToken(messaging).catch(() => null);
        }
      }
      setIsRegistered(false);
    } catch (err) {
      console.warn("[usePushNotifications] Falha ao desregistrar:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  /**
   * listenForeground — escuta mensagens quando o app está em foreground.
   * Retorna cleanup function.
   */
  const listenForeground = useCallback((callback) => {
    if (!isSupported || permission !== "granted") return () => {};

    let unsubscribe = () => {};
    getFirebaseMessaging().then((messaging) => {
      if (!messaging) return;
      import("firebase/messaging").then(({ onMessage }) => {
        unsubscribe = onMessage(messaging, (payload) => {
          callback(payload);
        });
      });
    });

    return () => unsubscribe();
  }, [isSupported, permission]);

  return {
    permission,
    isSupported,
    isRegistered,
    loading,
    error,
    requestAndRegister,
    unregister,
    listenForeground,
  };
}

export default usePushNotifications;
