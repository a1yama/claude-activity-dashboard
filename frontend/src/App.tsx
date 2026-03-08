import { HashRouter, Routes, Route } from 'react-router-dom';
import { Dashboard } from './pages/Dashboard';
import { SessionDetail } from './pages/SessionDetail';

function App() {
  return (
    <HashRouter>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/sessions/:sessionId" element={<SessionDetail />} />
      </Routes>
    </HashRouter>
  );
}

export default App;
