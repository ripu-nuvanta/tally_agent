import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { SessionProvider } from "./context/SessionContext";
import ProtectedRoute from "./components/ProtectedRoute";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import ChatApp from "./ChatApp";
import Header from "./components/Header";
import ChatWindow from "./components/ChatWindow";

function AppRoutes() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="h-screen flex items-center justify-center">
        <div className="text-gray-500">Loading...</div>
      </div>
    );
  }

  return (
    <Routes>
      <Route path="/login" element={user ? <Navigate to="/" replace /> : <LoginPage />} />
      <Route path="/register" element={user ? <Navigate to="/" replace /> : <RegisterPage />} />
      <Route path="/c/:conversationId" element={<ProtectedRoute><ChatApp /></ProtectedRoute>} />
      <Route path="/*" element={<ProtectedRoute><ChatApp /></ProtectedRoute>} />
    </Routes>
  );
}

function LegacyApp() {
  return (
    <SessionProvider>
      <div className="h-screen flex flex-col bg-white">
        <Header />
        <main className="flex-1 overflow-hidden">
          <ChatWindow />
        </main>
      </div>
    </SessionProvider>
  );
}

function App() {
  const isDbMode = import.meta.env.VITE_DB_MODE === "true";
  if (!isDbMode) {
    return <LegacyApp />;
  }
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
