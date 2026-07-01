import { useState, useEffect, useRef } from 'react';
import {
  getFeedsStatus,
  getSemanticStats,
  getExtractorStats,
  getCVEStats,
  getFeedsRecent,
  getRecentDocs,
} from '../api';

function pillStatus(data, key) {
  if (!data) return 'status-never_run';
  return data[key] === 'ok' ? 'status-ok' : 'status-never_run';
}

function confClass(conf) {
  if (conf >= 75) return 'status-ok';
  if (conf >= 55) return 'status-stale';
  return 'status-never_run';
}

export default function IngestMonitor() {
  const [feedsData,    setFeedsData]    = useState(null);
  const [semanticData, setSemanticData] = useState(null);
  const [extractorData,setExtractorData]= useState(null);
  const [cveData,      setCveData]      = useState(null);
  const [iocs,         setIocs]         = useState([]);
  const [docs,         setDocs]         = useState([]);
  const [error,        setError]        = useState(null);
  const iocTopRef = useRef(null);

  useEffect(() => {
    const load = () =>
      Promise.all([
        getFeedsStatus().then(d   => setFeedsData(d)),
        getSemanticStats().then(d => setSemanticData(d)),
        getExtractorStats().then(d=> setExtractorData(d)),
        getCVEStats().then(d      => setCveData(d)),
        getFeedsRecent(200).then(d=> setIocs(d.iocs || [])),
        getRecentDocs().then(d    => setDocs(d.docs || [])),
      ]).catch(() => setError('Pipeline unreachable — retry in 30s.'));

    load();
    const id = setInterval(load, 30_000);
    return () => clearInterval(id);
  }, []);

  // Auto-scroll to TOP of IOC log when new data arrives (newest entry is at top)
  // ponytail: Pitfall 4 — sentinel div is ABOVE the table, not attached to the last row
  useEffect(() => {
    iocTopRef.current?.scrollIntoView({ block: 'start' });
  }, [iocs]);

  // Derive feed health pill
  const feeds = feedsData?.feeds || [];
  const feedsStatus =
    feeds.every(f => f.status === 'ok') ? 'status-ok' :
    feeds.some(f  => f.status === 'ok') ? 'status-stale' :
    'status-never_run';

  // OpenCTI status derived from feed success (OpenCTI /health returns 401)
  const openctiStatus = feeds.some(f => f.status === 'ok') ? 'status-ok' : 'status-never_run';

  const pills = [
    { label: 'Feeds',          cls: feedsStatus },
    { label: 'OpenCTI',        cls: openctiStatus }, // derived from feed success (OpenCTI /health returns 401)
    { label: 'Semantic Index', cls: pillStatus(semanticData,  'status') },
    { label: 'Extractor',      cls: pillStatus(extractorData, 'status') },
    { label: 'CVE',            cls: pillStatus(cveData,       'status') },
  ];

  return (
    <div className="card">
      <h2 style={{ fontSize: '20px', fontWeight: 600, marginBottom: '16px' }}>Ingestion Monitor</h2>

      {error && (
        <p style={{ color: 'var(--color-destructive)', fontSize: '14px', marginBottom: '16px' }}>
          {error}
        </p>
      )}

      {/* Pipeline health strip */}
      <div style={{ display: 'flex', gap: '24px', marginBottom: '24px', flexWrap: 'wrap' }}>
        {pills.map(p => (
          <div key={p.label} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span className={`status-dot ${p.cls}`} />
            <span style={{ fontSize: '13px', fontWeight: 500 }}>{p.label}</span>
          </div>
        ))}
      </div>

      {/* IOC log */}
      <h3 style={{ fontSize: '16px', fontWeight: 600, marginBottom: '8px' }}>Live Ingestion</h3>
      {/* ponytail: sentinel div ABOVE table — scrollIntoView scrolls to newest (top), not oldest (bottom) */}
      <div ref={iocTopRef} />
      <div style={{ overflowY: 'auto', maxHeight: '400px', marginBottom: '24px' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
          <thead>
            <tr style={{ color: 'var(--color-muted)', textAlign: 'left' }}>
              <th style={{ padding: '6px 8px' }}>Time</th>
              <th style={{ padding: '6px 8px' }}>Indicator</th>
              <th style={{ padding: '6px 8px' }}>Type</th>
              <th style={{ padding: '6px 8px' }}>Feed</th>
              <th style={{ padding: '6px 8px' }}>Confidence</th>
            </tr>
          </thead>
          <tbody>
            {iocs.length === 0 ? (
              <tr>
                <td colSpan={5} style={{ padding: '12px 8px', color: 'var(--color-muted)' }}>
                  No IOCs yet — waiting for feed run
                </td>
              </tr>
            ) : (
              iocs.map((ioc, i) => (
                <tr key={i} style={{ borderTop: '1px solid var(--color-border)' }}>
                  <td style={{ padding: '6px 8px', whiteSpace: 'nowrap' }}>
                    {new Date(ioc.ts).toLocaleTimeString('en-GB', { hour12: false })}
                  </td>
                  <td style={{
                    padding: '6px 8px',
                    maxWidth: '240px',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}>
                    {ioc.value}
                  </td>
                  <td style={{ padding: '6px 8px' }}>{ioc.type}</td>
                  <td style={{ padding: '6px 8px' }}>{ioc.feed}</td>
                  <td style={{ padding: '6px 8px' }}>
                    <span className={confClass(ioc.confidence)}
                          style={{ fontSize: '12px', fontWeight: 600, padding: '1px 5px', borderRadius: '3px' }}>
                      {ioc.confidence}
                    </span>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Document pipeline */}
      <h3 style={{ fontSize: '16px', fontWeight: 600, marginBottom: '8px' }}>Document Pipeline</h3>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
        <thead>
          <tr style={{ color: 'var(--color-muted)', textAlign: 'left' }}>
            <th style={{ padding: '6px 8px' }}>Time</th>
            <th style={{ padding: '6px 8px' }}>Filename</th>
            <th style={{ padding: '6px 8px' }}>IOCs</th>
            <th style={{ padding: '6px 8px' }}>Status</th>
          </tr>
        </thead>
        <tbody>
          {docs.length === 0 ? (
            <tr>
              <td colSpan={4} style={{ padding: '12px 8px', color: 'var(--color-muted)' }}>
                No documents processed yet
              </td>
            </tr>
          ) : (
            docs.map((doc, i) => (
              <tr key={i} style={{ borderTop: '1px solid var(--color-border)' }}>
                <td style={{ padding: '6px 8px', whiteSpace: 'nowrap' }}>
                  {new Date(doc.ingested_at).toLocaleTimeString('en-GB', { hour12: false })}
                </td>
                <td style={{ padding: '6px 8px' }}>{doc.filename}</td>
                <td style={{ padding: '6px 8px' }}>{doc.ioc_count}</td>
                <td style={{ padding: '6px 8px', color: doc.status?.startsWith('error:') ? 'var(--color-warning)' : 'inherit' }}>
                  {doc.status}
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
