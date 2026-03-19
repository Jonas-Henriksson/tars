/**
 * Login / Register page.
 */
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useStore } from '../store';
import { api } from '../api/client';

export default function Login() {
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState('');
  const [name, setName] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { setAuth } = useStore();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const endpoint = isRegister ? '/api/auth/register' : '/api/auth/login';
      const body = isRegister ? { email, name, password } : { email, password };
      const data = await api.post<any>(endpoint, body);
      setAuth(data.token, data.user, data.teams || []);
      navigate('/');
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: '#0f172a',
        padding: 20,
      }}
    >
      <div
        style={{
          width: 400,
          backgroundColor: '#1e293b',
          borderRadius: 16,
          padding: 40,
          boxShadow: '0 25px 50px rgba(0,0,0,0.4)',
        }}
      >
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <div
            style={{
              width: 56,
              height: 56,
              borderRadius: 12,
              background: 'linear-gradient(135deg, #3b82f6, #8b5cf6)',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontWeight: 800,
              fontSize: 24,
              color: '#fff',
              marginBottom: 16,
            }}
          >
            T
          </div>
          <h1 style={{ color: '#f1f5f9', fontSize: 24, fontWeight: 600, margin: 0 }}>
            TARS
          </h1>
          <p style={{ color: '#94a3b8', fontSize: 14, marginTop: 4 }}>
            Executive Assistant Platform
          </p>
        </div>

        <form onSubmit={handleSubmit}>
          {isRegister && (
            <div style={{ marginBottom: 16 }}>
              <label style={{ display: 'block', color: '#94a3b8', fontSize: 13, marginBottom: 6 }}>
                Name
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                style={inputStyle}
                placeholder="Your name"
              />
            </div>
          )}

          <div style={{ marginBottom: 16 }}>
            <label style={{ display: 'block', color: '#94a3b8', fontSize: 13, marginBottom: 6 }}>
              Email
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              style={inputStyle}
              placeholder="you@company.com"
            />
          </div>

          <div style={{ marginBottom: 24 }}>
            <label style={{ display: 'block', color: '#94a3b8', fontSize: 13, marginBottom: 6 }}>
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              style={inputStyle}
              placeholder="Min 6 characters"
            />
          </div>

          {error && (
            <div
              style={{
                padding: '10px 14px',
                backgroundColor: 'rgba(239,68,68,0.1)',
                border: '1px solid rgba(239,68,68,0.3)',
                borderRadius: 8,
                color: '#fca5a5',
                fontSize: 13,
                marginBottom: 16,
              }}
            >
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            style={{
              width: '100%',
              padding: '12px',
              border: 'none',
              borderRadius: 10,
              backgroundColor: '#3b82f6',
              color: '#fff',
              fontSize: 15,
              fontWeight: 600,
              cursor: loading ? 'default' : 'pointer',
              opacity: loading ? 0.7 : 1,
            }}
          >
            {loading ? 'Loading...' : isRegister ? 'Create Account' : 'Sign In'}
          </button>
        </form>

        <div style={{ textAlign: 'center', marginTop: 20 }}>
          <button
            onClick={() => { setIsRegister(!isRegister); setError(''); }}
            style={{
              background: 'none',
              border: 'none',
              color: '#60a5fa',
              fontSize: 13,
              cursor: 'pointer',
            }}
          >
            {isRegister ? 'Already have an account? Sign in' : "Don't have an account? Register"}
          </button>
        </div>
      </div>
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: '10px 14px',
  backgroundColor: 'rgba(255,255,255,0.06)',
  border: '1px solid rgba(255,255,255,0.1)',
  borderRadius: 8,
  color: '#f1f5f9',
  fontSize: 14,
  outline: 'none',
};
