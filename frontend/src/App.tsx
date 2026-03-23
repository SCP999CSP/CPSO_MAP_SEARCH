import { BrowserRouter, Routes, Route } from "react-router-dom";
import MapPage from "./pages/MapPage";
import DoctorPage from "./pages/DoctorPage";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<MapPage />} />
        <Route path="/doctor/:cpso_number" element={<DoctorPage />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
