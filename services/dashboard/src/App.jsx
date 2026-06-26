import { useState } from 'react';
import './App.css';

const TABS = ['Overview', 'Threat Hunt', 'Briefings'];

export default function App() {
  const [tab, setTab] = useState('Overview');
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
      <main>
        <div className="tab-content">{tab}</div>
      </main>
    </>
  );
}
