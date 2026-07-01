import { useState } from 'react';
import './App.css';
import Overview from './views/Overview';
import ThreatHunt from './views/ThreatHunt';
import Briefings from './views/Briefings';
import Alerts from './views/Alerts';
import IngestMonitor from './views/IngestMonitor';

const TABS = ['Overview', 'Threat Hunt', 'Briefings', 'Alerts', 'Ingestion Monitor'];
const VIEWS = { Overview, 'Threat Hunt': ThreatHunt, Briefings, Alerts, 'Ingestion Monitor': IngestMonitor };

export default function App() {
  const [tab, setTab] = useState('Overview');
  const View = VIEWS[tab];
  return (
    <>
      <nav role="navigation">
        {TABS.map(t => (
          <button
            key={t}
            className={tab === t ? 'tab active' : 'tab'}
            onClick={() => setTab(t)}
          >
            {t}
          </button>
        ))}
      </nav>
      <main className="main-content">
        <View />
      </main>
    </>
  );
}
