import { BrowserRouter, Routes, Route, Link } from "react-router-dom";

function HomePage() {
  return (
    <div style={{ padding: "2rem" }}>
      <h1>AI Interview Agent</h1>
      <nav style={{ display: "flex", gap: "1rem", marginTop: "1rem" }}>
        <Link to="/upload">Upload Resume</Link>
        <Link to="/interview">Start Interview</Link>
        <Link to="/reports">View Reports</Link>
      </nav>
    </div>
  );
}

function UploadPage() {
  return <div style={{ padding: "2rem" }}>Upload Page</div>;
}

function InterviewPage() {
  return <div style={{ padding: "2rem" }}>Interview Page</div>;
}

function ReportsPage() {
  return <div style={{ padding: "2rem" }}>Reports Page</div>;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/upload" element={<UploadPage />} />
        <Route path="/interview" element={<InterviewPage />} />
        <Route path="/reports" element={<ReportsPage />} />
      </Routes>
    </BrowserRouter>
  );
}
