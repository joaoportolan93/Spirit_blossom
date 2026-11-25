// Firebase Messaging Service Worker — Onda 7a
// Recebe mensagens em background e exibe notificações.
// Mantém payloads genéricos — sem conteúdo privado de posts (ADR-N21/N24).

importScripts("https://www.gstatic.com/firebasejs/10.12.2/firebase-app-compat.js");
importScripts("https://www.gstatic.com/firebasejs/10.12.2/firebase-messaging-compat.js");

// Config injetada em tempo de build ou lida do SW scope
const firebaseConfig = {
  apiKey: self.VITE_FIREBASE_API_KEY || "",
  authDomain: self.VITE_FIREBASE_AUTH_DOMAIN || "",
  projectId: self.VITE_FIREBASE_PROJECT_ID || "",
  storageBucket: self.VITE_FIREBASE_STORAGE_BUCKET || "",
  messagingSenderId: self.VITE_FIREBASE_MESSAGING_SENDER_ID || "",
  appId: self.VITE_FIREBASE_APP_ID || "",
};

if (firebaseConfig.apiKey && firebaseConfig.projectId) {
  firebase.initializeApp(firebaseConfig);
  const messaging = firebase.messaging();

  messaging.onBackgroundMessage((payload) => {
    const { title, body } = payload.notification || {};
    const data = payload.data || {};

    self.registration.showNotification(title || "Nova notificação", {
      body: body || "Você tem uma nova notificação.",
      icon: "/icon-192.png",
      badge: "/badge-72.png",
      data,
      tag: data.notification_id || "default",
    });
  });
}

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const data = event.notification.data || {};
  const url = data.url || "/notifications";

  event.waitUntil(
    clients
      .matchAll({ type: "window", includeUncontrolled: true })
      .then((windowClients) => {
        for (const client of windowClients) {
          if (client.url.includes(self.location.origin) && "focus" in client) {
            client.navigate(url);
            return client.focus();
          }
        }
        if (clients.openWindow) {
          return clients.openWindow(url);
        }
      })
  );
});
