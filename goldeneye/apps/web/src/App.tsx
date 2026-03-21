import { useEffect, useState } from 'react';
import './App.css';

export function App() {
  const [status, setStatus] = useState<string>('loading...');

  useEffect(() => {
    fetch('/api')
      .then((res) => res.json())
      .then((data) => setStatus(data.status))
      .catch(() => setStatus('offline'));
  }, []);

  return (
    <div className="app">
      <h1>GoldenEye</h1>
      <p>API status: {status}</p>
    </div>
  );
}
