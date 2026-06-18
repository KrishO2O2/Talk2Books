// ============================================================
//  Talk²Books (TTB) — App.jsx
//  Phase 4 · Day 8  : API connection + core shell
//            Day 9  : Chat UI, useState hooks  (built in)
//            Day 10 : Source references        (built in)
// ============================================================

import { useState, useRef, useEffect, useCallback } from 'react';
import LandingPage from './LandingPage.jsx';
import ReactMarkdown from 'react-markdown';

// All /api/* requests are proxied to localhost:5000 by vite.config.js
const API_BASE = '/api';

// ── Utility ──────────────────────────────────────────────────
function now() {
  return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

// Normalize backend chunk shape → what SourceCard expects
function normalizeChunk(chunk) {
  return {
    content:  chunk.text ?? chunk.content ?? '',
    score:    chunk.score ?? 0,
    metadata: {
      source:  chunk.file_name ?? chunk.source ?? '',
      section: chunk.file_name ?? chunk.source ?? '',
      page:    chunk.metadata?.page ?? null,
    },
  };
}

// ── Sub-components ────────────────────────────────────────────

/** Single chat bubble */
function Message({ msg, onCitationClick }) {
  const isUser  = msg.role === 'user';
  const isError = msg.role === 'error';
  const cls = isUser ? 'user' : isError ? 'error' : 'ai';

  return (
    <div className={`msg msg--${cls}`}>
      <div className="msg__bubble">
      {isUser || isError ? (
        msg.content
      ) : (
        <ReactMarkdown>{msg.content}</ReactMarkdown>
      )}

        {/* Day 10 – inline citation refs */}
        {!isUser && msg.sources?.length > 0 && (
          <span className="msg__refs">
            {msg.sources.slice(0, 3).map((_, i) => (
              <span
              key={i}
              className="msg__ref"
              onClick={() => onCitationClick?.(i)}
            >
              {i + 1}
            </span>
            ))}
          </span>
        )}
      </div>
      <div className="msg__meta">
        {isUser ? 'You' : isError ? '⚠ Error' : 'TTB · RAG'}
        {!isUser && msg.sources?.length > 0 && ` · ${msg.sources.length} sources`}
        {' · '}{msg.time}
      </div>
    </div>
  );
}

/** Animated "thinking" indicator */
function ThinkingBubble({ label }) {
  return (
    <div className="msg msg--ai">
      <div className="msg__bubble msg__bubble--thinking">
        <span className="dot" /><span className="dot" /><span className="dot" />
      </div>
      <div className="msg__meta">{label}</div>
    </div>
  );
}

/** Document row in the left sidebar */
function DocItem({ doc, active, onClick, onDelete }) {
  return (
    <div
      className={`doc-item${active ? ' doc-item--active' : ''}`}
      onClick={onClick}
      role="button"
      aria-pressed={active}
      tabIndex={0}
      onKeyDown={e => e.key === 'Enter' && onClick()}
    >
      <div className="doc-item__icon">
        <i className="ti ti-file-type-pdf" />
      </div>
      <div className="doc-item__info">
        <div className="doc-item__name">{doc.name || doc.id}</div>
        <div className="doc-item__meta">
          {doc.language?.toUpperCase() || 'EN'}
          {doc.pages ? ` · ${doc.pages}p` : ''}
        </div>
      </div>
      <button
        className="doc-item__delete"
        onClick={e => { e.stopPropagation(); onDelete(doc); }}
        title="Delete document"
        aria-label={`Delete ${doc.name || doc.id}`}
      >
        <i className="ti ti-trash" />
      </button>
    </div>
  );
}

/** Single source card in the right sidebar */
function SourceCard({ source, index, active }) {
  const score   = +(source.score ?? source.relevance_score ?? 0).toFixed(2);
  const pct     = Math.round(score * 100);
  const page    = source.metadata?.page;
  const section = source.metadata?.section || source.metadata?.source || '';
  const snippet = source.content?.trim().slice(0, 150) ?? '';

  return (
      <div 
        id={`source-card-${index}`}
        className={`source-card${active ? ' source-card--active' : ''}`}
      >
      <div className="source-card__header">
        <span className="source-card__num">Source {String(index + 1).padStart(2, '0')}</span>
        <span className="source-card__score">{score}</span>
      </div>
      <div className="source-card__text">"{snippet}..."</div>
      <div className="source-card__footer">
        <span>{section}</span>
        {page && <span>p.{page}</span>}
      </div>
      <div className="source-card__bar">
        <div className="source-card__fill" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

// ── Main App ──────────────────────────────────────────────────
export default function App() {
  const [uploading,    setUploading]    = useState(false);
  const fileInputRef = useRef(null);
  const [language, setLanguage] = useState('auto');
  const [showApp, setShowApp] = useState(false);
  const [messages,   setMessages]   = useState([]);
  const [input,      setInput]      = useState('');
  const [loading,    setLoading]    = useState(false);
  const [sources,    setSources]    = useState([]);
  const [docs,       setDocs]       = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [activeDoc,  setActiveDoc]  = useState(null);
  const [backendStatus, setBackendStatus] = useState('connecting');
  const [activeSource, setActiveSource] = useState(null);
  const [showSettings, setShowSettings] = useState(false);
  // 'connecting' | 'online' | 'offline'

  const messagesEndRef = useRef(null);
  const inputRef       = useRef(null);

  // ── Auto-scroll ──
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  // ── Day 18: Close settings modal on Escape key ──
  useEffect(() => {
    if (!showSettings) return;
    const onKey = e => e.key === 'Escape' && setShowSettings(false);
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [showSettings]);

  // ── Auto-resize textarea ──
  useEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 120)}px`;
  }, [input]);

  // ── On mount: health check + fetch docs ──
  useEffect(() => {
    checkBackend();
    fetchDocs();
  }, []);

  // ── Day 17: Load saved chat history whenever the active document changes ──
  useEffect(() => {
    if (!activeDoc?.id) {
      setMessages([]);
      return;
    }
    try {
      const saved = localStorage.getItem(`ttb_chat_${activeDoc.id}`);
      setMessages(saved ? JSON.parse(saved) : []);
    } catch {
      setMessages([]);
    }
    setSources([]);
    setActiveSource(null);
  }, [activeDoc?.id]);

  // ── Day 17: Persist chat history to localStorage whenever it changes ──
  useEffect(() => {
    if (!activeDoc?.id) return;
    try {
      if (messages.length > 0) {
        localStorage.setItem(`ttb_chat_${activeDoc.id}`, JSON.stringify(messages));
      } else {
        localStorage.removeItem(`ttb_chat_${activeDoc.id}`);
      }
    } catch {
      // localStorage unavailable or full — fail silently
    }
  }, [messages, activeDoc?.id]);

  // ── Day 8: Check if backend is alive ──
  const checkBackend = async () => {
    try {
      const res = await fetch(`${API_BASE}/health`);
      setBackendStatus(res.ok ? 'online' : 'offline');
    } catch {
      setBackendStatus('offline');
    }
  };

  // ── Fetch document list ──
  const fetchDocs = async () => {
    try {
      const res = await fetch(`${API_BASE}/documents`);
      if (!res.ok) return;
      const data = await res.json();
      const list = data.documents ?? data.docs ?? [];
      setDocs(list);
      if (list.length > 0 && !activeDoc) setActiveDoc(list[0]);
    } catch {
      // backend may not have /api/documents yet — graceful no-op
    }
  };

  const handleCitationClick = useCallback((index) => {
    setActiveSource(index);
    setTimeout(() => {
      document.getElementById(`source-card-${index}`)
        ?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }, 50);
  }, []);

  // ── Day 8: Core POST to /api/query ──
  const sendQuestion = useCallback(async () => {
    const question = input.trim();
    if (!question || loading) return;

    setInput('');
    setSources([]);
    setActiveSource(null);

    setMessages(prev => [...prev, {
      role: 'user',
      content: question,
      time: now(),
    }]);
    setLoading(true);

    try {
      const body = { question };
      if (language !== 'auto') body.language = language;
      if (activeDoc?.id) body.doc_id = activeDoc.id;

      const res = await fetch(`${API_BASE}/query`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify(body),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error ?? `HTTP ${res.status}`);
      }

      const data = await res.json();
      // ── Flexible response handling ──
      const answer  = data.answer ?? data.response ?? data.result ?? 'No answer returned.';
      const srcs = (data.chunks ?? data.context ?? []).map(normalizeChunk);

      setMessages(prev => [...prev, {
        role:    'ai',
        content: answer,
        sources: srcs,
        time:    now(),
      }]);
      setSources(srcs);

    } catch (err) {
      setMessages(prev => [...prev, {
        role:    'error',
        content: `${err.message}. Is the backend running on port 5000?`,
        time:    now(),
      }]);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  }, [input, loading, activeDoc]);

  const handleFileChange = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
  
    setUploading(true);
    const form = new FormData();
    form.append('file', file);
  
    try {
      const res = await fetch(`${API_BASE}/upload`, {
        method: 'POST',
        body: form,
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error ?? `HTTP ${res.status}`);
      }
      const data = await res.json();
      await fetchDocs();
      setActiveDoc(data.document);
      setSources([]);
      setMessages([]);
    } catch (err) {
      setMessages(prev => [...prev, {
        role: 'error',
        content: `Upload failed: ${err.message}`,
        time: now(),
      }]);
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleDeleteDoc = useCallback(async (doc) => {
    const name = doc.name || doc.id;
    if (!window.confirm(`Delete "${name}"? This removes it from the library and search index permanently.`)) {
      return;
    }
  
    try {
      const res = await fetch(`${API_BASE}/documents/${encodeURIComponent(doc.id)}`, {
        method: 'DELETE',
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error ?? `HTTP ${res.status}`);
      }
  
      setDocs(prev => prev.filter(d => d.id !== doc.id));
      try { localStorage.removeItem(`ttb_chat_${doc.id}`); } catch {}
  
      if (activeDoc?.id === doc.id) {
        setActiveDoc(null);
        setMessages([]);
        setSources([]);
        setActiveSource(null);
      }
    } catch (err) {
      setMessages(prev => [...prev, {
        role: 'error',
        content: `Delete failed: ${err.message}`,
        time: now(),
      }]);
    }
  }, [activeDoc]);

  const handleKeyDown = e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendQuestion();
    }
  };

  // Filter library by search query (case-insensitive, matches name or id)
  const filteredDocs = docs.filter(doc =>
    (doc.name || doc.id || '').toLowerCase().includes(searchQuery.trim().toLowerCase())
  );

  // Sources to display: current query OR last AI message that had sources
  const displaySources = sources.length > 0
    ? sources
    : [...messages].reverse().find(m => m.role === 'ai' && m.sources?.length)?.sources ?? [];

  // ── Status badge text ──
  const statusText = {
    online:     'Ollama · phi4-mini · local',
    offline:    'Backend offline — run app.py',
    connecting: 'Connecting to backend...',
  }[backendStatus];

  // ────────────────────────────────────────────────────────────
  if (!showApp) return <LandingPage onEnter={() => {
    try { localStorage.setItem('ttb_entered', 'true'); } catch {}
    setShowApp(true);
  }} />;
  
  return (
    <div className="ttb">

      {/* ── Top Bar ──────────────────────────────────── */}
      <header className="topbar">
      <div
        className="topbar__logo"
        onClick={() => setShowApp(false)}
        role="button"
        tabIndex={0}
        onKeyDown={e => e.key === 'Enter' && setShowApp(false)}
        title="Back to home"
      >
        TTB<sup className="topbar__sup">✦</sup>
      </div>

        <div className="topbar__status">
          <span className={`status-dot status-dot--${backendStatus}`} />
          {statusText}
        </div>

        <div className="topbar__actions">
          <button
            className="icon-btn"
            title="Refresh document list"
            onClick={fetchDocs}
          >
            <i className="ti ti-refresh" />
          </button>
          <button className="icon-btn" title="Clear chat" onClick={() => { setMessages([]); setSources([]); }}>
            <i className="ti ti-trash" />
          </button>
          <button className="icon-btn" title="Settings" onClick={() => setShowSettings(true)}>
            <i className="ti ti-settings" />
          </button>
        </div>
      </header>

      {/* ── Day 18: Settings / System Info Modal ──────────── */}
      {showSettings && (
        <div className="modal-overlay" onClick={() => setShowSettings(false)}>
          <div
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-label="System information"
            onClick={e => e.stopPropagation()}
          >
            <div className="modal__header">
              <span className="modal__title">System Info</span>
              <button className="icon-btn" onClick={() => setShowSettings(false)} aria-label="Close">
                <i className="ti ti-x" />
              </button>
            </div>

            <div className="modal__body">

              <div className="modal__section">
                <span className="modal__label">Connection</span>
                <div className="modal__row">
                  <span>Status</span>
                  <span className="modal__status">
                    <span className={`status-dot status-dot--${backendStatus}`} />
                    {statusText}
                  </span>
                </div>
              </div>

              <div className="modal__section">
                <span className="modal__label">Language Model</span>
                <div className="modal__row">
                  <span>Model</span><span>phi4-mini</span>
                </div>
                <div className="modal__row">
                  <span>Runtime</span><span>Ollama (local)</span>
                </div>
              </div>

              <div className="modal__section">
                <span className="modal__label">Retrieval</span>
                <div className="modal__row">
                  <span>Embedding model</span><span>all-mpnet-base-v2</span>
                </div>
                <div className="modal__row">
                  <span>Vector dimensions</span><span>768</span>
                </div>
                <div className="modal__row">
                  <span>Top-K results</span><span>3</span>
                </div>
                <div className="modal__row">
                  <span>Vector store</span><span>Qdrant (local)</span>
                </div>
              </div>

              <div className="modal__section">
                <span className="modal__label">Document Processing</span>
                <div className="modal__row">
                  <span>Chunk size</span><span>500 chars</span>
                </div>
                <div className="modal__row">
                  <span>Chunk overlap</span><span>50 chars</span>
                </div>
              </div>

            </div>

            <div className="modal__footer">
              Talk²Books · v0.1 · Fully local · Private
            </div>
          </div>
        </div>
      )}

      {/* ── Body ─────────────────────────────────────── */}
      <div className="body">

        {/* ── LEFT: Library Panel ──────────────────── */}
        <aside className="library">
          <div className="panel-header">
            <span className="panel-label">Library</span>
            <div className="search-box">
              <i className="ti ti-search" />
              <input
              type="text"
              className="search-input"
              placeholder="Search docs..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              />
            </div>
          </div>

          <div className="doc-list">
            {filteredDocs.length === 0 ? (
              <div className="empty-state">
                <i className="ti ti-books" />
                <p>{docs.length === 0 ? 'No documents found' : 'No matches'}</p>
                <small>{docs.length === 0 ? 'Run ingest.py first, then refresh' : 'Try a different search term'}</small>
              </div>
            ) : (
              filteredDocs.map(doc => (
                <DocItem
                  key={doc.id}
                  doc={doc}
                  active={activeDoc?.id === doc.id}
                  onClick={() => {
                    setActiveDoc(doc);
                    setSources([]);
                  }}
                  onDelete={handleDeleteDoc}
                />
              ))
            )}
          </div>

          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.docx,.txt,.csv"
            style={{ display: 'none' }}
            onChange={handleFileChange}
          />
          <button
            className="upload-btn"
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
          >
            <i className={`ti ${uploading ? 'ti-loader-2' : 'ti-upload'}`} />
            {uploading ? 'Processing...' : 'Upload document'}
          </button>
        </aside>

        {/* ── CENTER: Chat Panel ───────────────────── */}
        <main className="chat">

          {/* Active doc context bar */}
          {activeDoc && (
            <div className="context-bar">
              <span className="context-badge">Active</span>
              <span className="context-label">
                {activeDoc.name || activeDoc.id}
              </span>
            </div>
          )}

          {/* Messages area */}
          <div className="messages" role="log" aria-live="polite">
            {messages.length === 0 && !loading && (
              <div className="welcome">
                <div className="welcome__title">Talk to your Books.</div>
                <div className="welcome__sub">
                  {activeDoc
                    ? `Ask anything about "${activeDoc.name || activeDoc.id}"`
                    : 'Select a document from the library to begin.'}
                </div>
                {backendStatus === 'offline' && (
                  <div className="backend-warning">
                    <i className="ti ti-alert-triangle" />
                    Backend offline — run <code>python app.py</code>
                  </div>
                )}
              </div>
            )}

            {messages.map((msg, i) => (
              <Message key={i} msg={msg} onCitationClick={handleCitationClick} />
            ))}

            {loading && (
              <ThinkingBubble
                label={`Searching ${activeDoc?.name ?? 'document'}...`}
              />
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Input area */}
          <div className="input-area">
            <div className="input-wrap">
              <textarea
                ref={inputRef}
                className="input-field"
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask anything about this document..."
                rows={1}
                disabled={loading}
                aria-label="Question input"
              />
              <div className="input-actions">

                {/* Day 11 – language selector */}
                <select
                  className="lang-select"
                  aria-label="Language"
                  value={language}
                  onChange={e => setLanguage(e.target.value)}
                >
                  <option value="auto">Auto</option>
                  <option value="en">English</option>
                  <option value="hi">Hindi</option>
                  <option value="pa">Punjabi</option>
                  <option value="sa">Sanskrit</option>
                </select>

                <button
                  className={`send-btn${(!input.trim() || loading) ? ' send-btn--disabled' : ''}`}
                  onClick={sendQuestion}
                  disabled={!input.trim() || loading}
                  aria-label="Send question"
                >
                  <i className="ti ti-arrow-up" />
                </button>
              </div>
            </div>
            <p className="input-hint">
              Grounded answers · No hallucinations · Runs locally
            </p>
          </div>
        </main>

        {/* ── RIGHT: Sources Panel ─────────────────── */}
        <aside className="sources">
          <div className="panel-header">
            <span className="panel-label">Sources</span>
            {displaySources.length > 0 && (
              <span className="sources-count">
                {displaySources.length} retrieved
              </span>
            )}
          </div>

          <div className="source-list">
            {displaySources.length === 0 ? (
              <div className="empty-state">
                <i className="ti ti-file-search" />
                <p>No sources yet</p>
                <small>Ask a question to see retrieved passages</small>
              </div>
            ) : (
              displaySources.slice(0, 3).map((src, i) => (
                <SourceCard
                  key={i}
                  source={src}
                  index={i}
                  active={i === activeSource}
                />
              ))
            )}
          </div>
        </aside>

      </div>
    </div>
  );
}