import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "./contexts/AuthContext";
import { UploadProvider } from "./contexts/UploadContext";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { Toaster } from "./components/ui/sonner";
import LandingPage from "./pages/LandingPage";
import Login from "./pages/Login";
import Register from "./pages/Register";
import DashboardLayout from "./pages/DashboardLayout";
import Dashboard from "./pages/Dashboard";
import VideoManager from "./pages/VideoManager";
import LiveSlot from "./pages/LiveSlot";
import Billings from "./pages/Billings";
import Support from "./pages/Support";

function App() {
  return (
    <div className="App">
      <AuthProvider>
        <UploadProvider>
          <BrowserRouter>
            <Routes>
              <Route path="/" element={<LandingPage />} />
              <Route path="/login" element={<Login />} />
              <Route path="/register" element={<Register />} />
              <Route path="/dashboard" element={<ProtectedRoute><DashboardLayout /></ProtectedRoute>}>
                <Route index element={<Dashboard />} />
                <Route path="videos" element={<VideoManager />} />
                <Route path="live-slot" element={<LiveSlot />} />
                <Route path="billings" element={<Billings />} />
                <Route path="support" element={<Support />} />
              </Route>
            </Routes>
            <Toaster position="bottom-right" />
          </BrowserRouter>
        </UploadProvider>
      </AuthProvider>
    </div>
  );
}

export default App;
