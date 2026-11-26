import fs from "node:fs";
import path from "node:path";
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

const FIREBASE_SW_KEYS = [
  "VITE_FIREBASE_API_KEY",
  "VITE_FIREBASE_AUTH_DOMAIN",
  "VITE_FIREBASE_PROJECT_ID",
  "VITE_FIREBASE_STORAGE_BUCKET",
  "VITE_FIREBASE_MESSAGING_SENDER_ID",
  "VITE_FIREBASE_APP_ID",
];

function buildSwEnvHeader(env) {
  return FIREBASE_SW_KEYS.filter((key) => env[key])
    .map((key) => `self.${key} = ${JSON.stringify(env[key])};`)
    .join("\n");
}

function firebaseSwEnvPlugin(env) {
  const header = buildSwEnvHeader(env);
  const injectHeader = (code) => (header ? `${header}\n${code}` : code);

  return {
    name: "firebase-sw-env",
    configureServer(server) {
      server.middlewares.use("/firebase-messaging-sw.js", (_req, res, next) => {
        const swPath = path.resolve(__dirname, "public/firebase-messaging-sw.js");
        if (!fs.existsSync(swPath)) return next();
        const content = fs.readFileSync(swPath, "utf-8");
        res.setHeader("Content-Type", "application/javascript; charset=utf-8");
        res.end(injectHeader(content));
      });
    },
    writeBundle(options) {
      if (!header) return;
      const outDir = options.dir || path.resolve(__dirname, "dist");
      const swOutPath = path.join(outDir, "firebase-messaging-sw.js");
      if (fs.existsSync(swOutPath)) {
        const content = fs.readFileSync(swOutPath, "utf-8");
        fs.writeFileSync(swOutPath, injectHeader(content), "utf-8");
      }
    },
  };
}

export default defineConfig(({ mode }) => {
  const rootEnvDir = path.resolve(__dirname, "../..");
  const isTest = mode === "test";
  const env = isTest
    ? {}
    : {
        ...loadEnv(mode, rootEnvDir, "VITE_"),
        ...loadEnv(mode, __dirname, "VITE_"),
      };
  const appName = env.VITE_APP_NAME || process.env.VITE_APP_NAME || "Spirit Blossom";

  return {
    envDir: isTest ? undefined : rootEnvDir,
    plugins: [
      react(),
      firebaseSwEnvPlugin(env),
      VitePWA({
        registerType: "autoUpdate",
        includeAssets: ["favicon.ico", "apple-touch-icon.png"],
        manifest: {
          name: appName,
          short_name: appName,
          description: "Spirit Blossom 18+ Social Network",
          theme_color: "#18181b",
          background_color: "#09090b",
          display: "standalone",
          start_url: "/",
          icons: [
            {
              src: "/icon-192.png",
              sizes: "192x192",
              type: "image/png",
            },
            {
              src: "/icon-512.png",
              sizes: "512x512",
              type: "image/png",
            },
          ],
        },
      }),
    ],
    server: {
      port: 5173,
      proxy: {
        "/api": {
          target: "http://localhost:8000",
          changeOrigin: true,
        },
        "/media": {
          target: "http://localhost:8000",
          changeOrigin: true,
        },
      },
    },
    test: {
      globals: true,
      environment: "jsdom",
      setupFiles: "./src/test/setup.js",
      include: ["src/**/*.{test,spec}.{js,jsx}"],
      exclude: ["e2e/**", "node_modules/**"],
      coverage: {
        provider: "v8",
        reporter: ["text", "json"],
        include: ["src/**/*.{js,jsx}"],
        exclude: ["src/test/**", "src/main.jsx"],
        thresholds: {
          lines: 84,
          statements: 84,
          functions: 88,
          branches: 83,
        },
      },
    },
  };
});
