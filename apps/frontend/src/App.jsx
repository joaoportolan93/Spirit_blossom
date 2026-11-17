import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./hooks/useAuth";
import { Navbar } from "./components/Navbar";
import { Feed } from "./pages/Feed";
import { Login } from "./pages/Login";
import { Register } from "./pages/Register";
import { ForgotPassword } from "./pages/ForgotPassword";
import { ResetPassword } from "./pages/ResetPassword";
import { CompleteSignup } from "./pages/CompleteSignup";
import { Profile } from "./pages/Profile";
import { Explore } from "./pages/Explore";
import { Search } from "./pages/Search";
import { Bookmarks } from "./pages/Bookmarks";
import { PostPage } from "./pages/PostPage";
import { Notifications } from "./pages/Notifications";
import { Settings } from "./pages/Settings";
import { SettingsPrivacy } from "./pages/settings/SettingsPrivacy";
import { SettingsCircle } from "./pages/settings/SettingsCircle";
import { SettingsBlocked } from "./pages/settings/SettingsBlocked";
import { SettingsMuted } from "./pages/settings/SettingsMuted";
import { SettingsAccount } from "./pages/settings/SettingsAccount";
import { SettingsNotifications } from "./pages/settings/SettingsNotifications";
import { SettingsAppearance } from "./pages/settings/SettingsAppearance";

function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[50vh] text-zinc-500 text-sm">
        Carregando...
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return children;
}

export function App() {
  return (
    <Router>
      <AuthProvider>
        <div className="min-h-screen bg-zinc-950 text-zinc-100 font-sans">
          <Navbar />
          <div className="pl-60 min-h-screen flex flex-col">
          <main className="flex-1">
            <Routes>
              <Route
                path="/"
                element={
                  <ProtectedRoute>
                    <Feed />
                  </ProtectedRoute>
                }
              />
              <Route path="/login" element={<Login />} />
              <Route path="/register" element={<Register />} />
              <Route path="/forgot-password" element={<ForgotPassword />} />
              <Route path="/reset-password" element={<ResetPassword />} />
              <Route path="/complete-signup" element={<CompleteSignup />} />
              <Route
                path="/explore"
                element={
                  <ProtectedRoute>
                    <Explore />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/search"
                element={
                  <ProtectedRoute>
                    <Search />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/settings"
                element={
                  <ProtectedRoute>
                    <Settings />
                  </ProtectedRoute>
                }
              >
                <Route index element={<Navigate to="/settings/account" replace />} />
                <Route path="account" element={<SettingsAccount />} />
                <Route path="notifications" element={<SettingsNotifications />} />
                <Route path="privacy" element={<SettingsPrivacy />} />
                <Route path="appearance" element={<SettingsAppearance />} />
                <Route path="circle" element={<SettingsCircle />} />
                <Route path="blocked" element={<SettingsBlocked />} />
                <Route path="muted" element={<SettingsMuted />} />
              </Route>
              <Route
                path="/notifications"
                element={
                  <ProtectedRoute>
                    <Notifications />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/close-friends"
                element={<Navigate to="/settings/circle" replace />}
              />
              <Route
                path="/follow-requests"
                element={<Navigate to="/notifications?tab=requests" replace />}
              />
              <Route
                path="/bookmarks"
                element={
                  <ProtectedRoute>
                    <Bookmarks />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/posts/:id"
                element={
                  <ProtectedRoute>
                    <PostPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/post/:id"
                element={
                  <ProtectedRoute>
                    <PostPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/profile"
                element={
                  <ProtectedRoute>
                    <Profile />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/profile/:username"
                element={
                  <ProtectedRoute>
                    <Profile />
                  </ProtectedRoute>
                }
              />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </main>
          </div>
        </div>
      </AuthProvider>
    </Router>
  );
}

export default App;
