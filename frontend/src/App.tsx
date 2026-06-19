/**
 * App routes (react-router-dom). Each authenticated page opens its own sync session via
 * `useSync`, reading derived state from the Zustand store. Unknown paths -> Join.
 */

import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import Join from './pages/Join';
import Lobby from './pages/Lobby';
import SeekerView from './pages/SeekerView';
import HiderView from './pages/HiderView';
import Scoreboard from './pages/Scoreboard';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Join />} />
        <Route path="/lobby" element={<Lobby />} />
        <Route path="/seeker" element={<SeekerView />} />
        <Route path="/hider" element={<HiderView />} />
        <Route path="/scoreboard" element={<Scoreboard />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
