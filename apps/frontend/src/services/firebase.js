/**
 * Firebase Web SDK — inicialização lazy com fallback gracioso.
 *
 * Se as variáveis VITE_FIREBASE_* estiverem vazias (dev/CI),
 * o módulo retorna null sem crashar o app.
 */

let _firebaseApp = null;
let _messaging = null;
let _initialized = false;

function getFirebaseConfig() {
  return {
    apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
    authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
    projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
    storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
    messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
    appId: import.meta.env.VITE_FIREBASE_APP_ID,
  };
}

function isFirebaseConfigured(config) {
  return !!(config.apiKey && config.projectId && config.messagingSenderId && config.appId);
}

export async function getFirebaseMessaging() {
  if (_initialized) return _messaging;
  _initialized = true;

  const config = getFirebaseConfig();
  if (!isFirebaseConfigured(config)) {
    console.info("[Firebase] Variáveis de ambiente não configuradas — push desabilitado.");
    return null;
  }

  try {
    const { initializeApp, getApps } = await import("firebase/app");
    const { getMessaging, isSupported } = await import("firebase/messaging");

    const supported = await isSupported().catch(() => false);
    if (!supported) {
      console.info("[Firebase] Messaging não suportado neste navegador.");
      return null;
    }

    if (getApps().length === 0) {
      _firebaseApp = initializeApp(config);
    } else {
      _firebaseApp = getApps()[0];
    }

    _messaging = getMessaging(_firebaseApp);
    return _messaging;
  } catch (err) {
    console.warn("[Firebase] Falha ao inicializar:", err);
    return null;
  }
}

export function getVapidKey() {
  return import.meta.env.VITE_FIREBASE_VAPID_KEY || null;
}
