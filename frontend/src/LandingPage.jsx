import { useState, useEffect } from 'react';

// ============================================================
//  Talk²Books — LandingPage.jsx
//  Matches the dark editorial design mockup exactly.
//  Props: onEnter — called when "OPEN LIBRARY" is clicked.
// ============================================================

const STYLES = `
  /* ── Wrapper ──────────────────────────────────────────── */
  .lp {
    height: 100vh;
    background: #1c1b1a;
    color: #ece8df;
    font-family: 'DM Sans', system-ui, sans-serif;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  /* ── Nav ──────────────────────────────────────────────── */
  .lp-nav {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 44px;
    height: 62px;
    border-bottom: 0.5px solid rgba(236,232,223,0.07);
    flex-shrink: 0;
  }

  .lp-logo {
    font-family: 'Cormorant Garamond', Georgia, serif;
    font-size: 19px;
    font-weight: 600;
    letter-spacing: -0.01em;
    color: #ece8df;
  }
  .lp-logo sup {
    color: #c4a35a;
    font-size: 10px;
    vertical-align: super;
    font-style: normal;
  }

  .lp-nav-links {
    display: flex;
    gap: 36px;
  }
  .lp-nav-link {
    font-size: 11px;
    letter-spacing: 0.16em;
    color: #a09890;
    text-decoration: none;
    transition: color 0.15s;
  }
  .lp-nav-link:hover { color: #ece8df; }

  .lp-badge {
    font-size: 11px;
    color: #a09890;
    border: 0.5px solid rgba(236,232,223,0.12);
    border-radius: 100px;
    padding: 5px 16px;
    letter-spacing: 0.04em;
  }

  /* ── Hero ─────────────────────────────────────────────── */
  .lp-hero {
    flex: 1;
    display: flex;
    min-height: 0;
  }

  .lp-left {
    width: 56%;
    flex-shrink: 0;
    padding: 52px 0 44px 56px;
    display: flex;
    flex-direction: column;
    justify-content: center;
  }

  .lp-eyebrow {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 10px;
    letter-spacing: 0.24em;
    text-transform: uppercase;
    color: #c4a35a;
    margin-bottom: 30px;
  }
  .lp-eyebrow-rule {
    width: 38px;
    height: 0.5px;
    background: #c4a35a;
    opacity: 0.55;
    flex-shrink: 0;
  }

  /* Heading — three distinct spans */
  .lp-h1 {
    font-family: 'Cormorant Garamond', Georgia, serif;
    font-size: 90px;
    line-height: 1.0;
    margin: 0 0 30px 0;
    letter-spacing: -0.02em;
  }
  .lp-h1-line1 {
    display: block;
    font-weight: 300;
    font-style: italic;
    color: #ece8df;
  }
  .lp-h1-line2 {
    display: block;
  }
  .lp-your {
    font-weight: 700;
    font-style: normal;
    color: #ece8df;
  }
  .lp-books {
    font-weight: 300;
    font-style: italic;
    color: #c4a35a;
  }

  .lp-sub {
    font-size: 15px;
    line-height: 1.78;
    color: #b0aaa3;
    max-width: 500px;
    margin: 0 0 42px 0;
  }

  /* Buttons */
  .lp-btns {
    display: flex;
    align-items: center;
    gap: 14px;
  }
  .lp-btn-open {
    background: #c4a35a;
    color: #080909;
    border: none;
    padding: 15px 34px;
    font-family: 'DM Sans', system-ui, sans-serif;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.18em;
    cursor: pointer;
    border-radius: 2px;
    transition: opacity 0.15s;
  }
  .lp-btn-open:hover { opacity: 0.82; }

  .lp-btn-docs {
    background: none;
    color: #a09890;
    border: 0.5px solid rgba(236,232,223,0.14);
    padding: 15px 26px;
    font-family: 'DM Sans', system-ui, sans-serif;
    font-size: 11px;
    letter-spacing: 0.12em;
    cursor: pointer;
    border-radius: 2px;
    transition: color 0.15s, border-color 0.15s;
  }
  .lp-btn-docs:hover {
    color: #ece8df;
    border-color: rgba(236,232,223,0.28);
  }

  /* ── Right / Dot grid ─────────────────────────────────── */
  .lp-right {
    flex: 1;
    position: relative;
    overflow: hidden;
  }

  .lp-dots {
    position: absolute;
    inset: 0;
    background-image: radial-gradient(
      circle,
      rgba(196,163,90,0.45) 1.3px,
      transparent 1.3px
    );
    background-size: 28px 28px;
    background-position: 12px 20px;
    /* fade away toward left & bottom edges */
    mask-image: linear-gradient(
      to bottom left,
      rgba(0,0,0,0.9) 40%,
      rgba(0,0,0,0.0) 85%
    );
    -webkit-mask-image: linear-gradient(
      to bottom left,
      rgba(0,0,0,0.9) 40%,
      rgba(0,0,0,0.0) 85%
    );
  }

  .lp-vertical {
    position: absolute;
    right: -58px;
    top: 50%;
    transform: translateY(-50%) rotate(90deg);
    font-size: 12px;
    letter-spacing: 0.3em;
    color: #786f68;
    text-transform: uppercase;
    white-space: nowrap;
    user-select: none;
  }

  /* ── Ticker ───────────────────────────────────────────── */
  .lp-ticker {
    height: 42px;
    border-top: 0.5px solid rgba(236,232,223,0.07);
    display: flex;
    align-items: center;
    overflow: hidden;
    flex-shrink: 0;
  }
  .lp-ticker-track {
    display: flex;
    align-items: center;
    animation: lp-marquee 22s linear infinite;
    white-space: nowrap;
  }
  .lp-ticker-item {
    display: inline-flex;
    align-items: center;
    gap: 22px;
    font-size: 10px;
    letter-spacing: 0.22em;
    text-transform: uppercase;
    olor: #786f68;
    padding: 0 12px;
  }
  .lp-ticker-plus {
    color: #c4a35a;
    font-size: 11px;
    line-height: 1;
  }

  @keyframes lp-marquee {
    from { transform: translateX(0); }
    to   { transform: translateX(-50%); }
  }

  /* ── About Modal ──────────────────────────────────────── */
.lp-about-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.65);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 200;
}
.lp-about {
  width: 500px;
  max-width: 92vw;
  background: #232120;
  border: 0.5px solid rgba(196,163,90,0.22);
  border-radius: 12px;
  overflow: hidden;
}
.lp-about-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 22px 28px;
  border-bottom: 0.5px solid rgba(236,232,223,0.07);
}
.lp-about-title {
  font-family: 'Cormorant Garamond', Georgia, serif;
  font-size: 22px;
  font-weight: 300;
  font-style: italic;
  color: #ece8df;
}
.lp-about-close {
  background: none;
  border: none;
  color: #6e6a65;
  font-size: 16px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 4px;
  transition: color 0.15s;
}
.lp-about-close:hover { color: #ece8df; }
.lp-about-body { padding: 22px 28px 26px; }
.lp-about-desc {
  font-size: 14px;
  color: #a09890;
  line-height: 1.78;
  margin: 0 0 22px 0;
}
.lp-about-label {
  display: block;
  font-size: 9px;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: #c4a35a;
  margin-bottom: 10px;
}
.lp-about-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  margin-bottom: 22px;
}
.lp-about-chip {
  font-size: 11px;
  padding: 4px 12px;
  background: rgba(196,163,90,0.08);
  border: 0.5px solid rgba(196,163,90,0.2);
  border-radius: 100px;
  color: #c4a35a;
}
.lp-about-rows { display: flex; flex-direction: column; }
.lp-about-row {
  display: flex;
  justify-content: space-between;
  padding: 10px 0;
  border-bottom: 0.5px solid rgba(236,232,223,0.07);
  font-size: 14px;
}
.lp-about-row:last-child { border-bottom: none; }
.lp-about-row span:first-child { color: #6e6a65; }
.lp-about-row span:last-child  { color: #ece8df; font-weight: 500; }
.lp-about-footer {
  padding: 14px 28px;
  border-top: 0.5px solid rgba(236,232,223,0.07);
  text-align: center;
  font-size: 10px;
  letter-spacing: 0.2em;
  color: #3e3c38;
}
`;

const TICKER = [
  'Semantic Search',
  'Citation Extraction',
  'Multilingual',
  'Privacy First',
  'Local Inference',
  'Vector Search',
  // duplicated so the marquee loops seamlessly
  'Semantic Search',
  'Citation Extraction',
  'Multilingual',
  'Privacy First',
  'Local Inference',
  'Vector Search',
];

export default function LandingPage({ onEnter }) {
  const [aboutOpen, setAboutOpen] = useState(false);

  useEffect(() => {
    if (!aboutOpen) return;
    const onKey = e => e.key === 'Escape' && setAboutOpen(false);
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [aboutOpen]);

  return (
    <>
      <style>{STYLES}</style>

      <div className="lp">

        {/* ── Nav ────────────────────────────────── */}
        <nav className="lp-nav">
          <div className="lp-logo">
            Talk<sup>2</sup>Books
          </div>
          <div className="lp-nav-links">
            <a href="#" className="lp-nav-link">DOCS</a>
            <a href="https://github.com/sb7r/ttb"
              className="lp-nav-link"
              target="_blank"
              rel="noopener noreferrer">
              GITHUB
            </a>
            <a href="#" className="lp-nav-link"
              onClick={e => { e.preventDefault(); setAboutOpen(true); }}>
              ABOUT
            </a>
          </div>
          <div className="lp-badge">v0.1 · local</div>
        </nav>

        {/* ── Hero ───────────────────────────────── */}
        <div className="lp-hero">

          <div className="lp-left">
            <div className="lp-eyebrow">
              <span>+</span>
              Document Intelligence System
              <span className="lp-eyebrow-rule" />
            </div>

            <h1 className="lp-h1">
              <span className="lp-h1-line1">Talk to</span>
              <span className="lp-h1-line2">
                <span className="lp-your">your </span>
                <span className="lp-books">Books.</span>
              </span>
            </h1>

            <p className="lp-sub">
              A local, multilingual RAG pipeline for semantic document
              understanding. Ask questions, extract citations — all running
              privately on your machine.
            </p>

            <div className="lp-btns">
              <button className="lp-btn-open" onClick={onEnter}>
                OPEN LIBRARY
              </button>
              <button className="lp-btn-docs">
                VIEW DOCS →
              </button>
            </div>
          </div>

          <div className="lp-right">
            <div className="lp-dots" />
            <div className="lp-vertical">LOCAL · PRIVATE · MULTILINGUAL</div>
          </div>

        </div>

        {/* ── Ticker ─────────────────────────────── */}
        <div className="lp-ticker">
          <div className="lp-ticker-track">
            {TICKER.map((label, i) => (
              <span key={i} className="lp-ticker-item">
                {label.toUpperCase()}
                <span className="lp-ticker-plus">+</span>
              </span>
            ))}
          </div>
        </div>
        {aboutOpen && (
  <div className="lp-about-overlay" onClick={() => setAboutOpen(false)}>
    <div className="lp-about" onClick={e => e.stopPropagation()}>

      <div className="lp-about-header">
        <span className="lp-about-title">About Talk<sup style={{fontSize:'12px',verticalAlign:'super'}}>2</sup>Books</span>
        <button className="lp-about-close" onClick={() => setAboutOpen(false)}>✕</button>
      </div>

      <div className="lp-about-body">
        <p className="lp-about-desc">
          Talk²Books is a fully local, multilingual document intelligence system.
          Upload any PDF, Word file, or text document and ask questions in plain
          English, Hindi, Punjabi, or Sanskrit — all running privately on your
          machine with no cloud dependency.
        </p>

        <span className="lp-about-label">Tech Stack</span>
        <div className="lp-about-chips">
          {['React 18','Quart (Python)','Qdrant','Ollama','phi4-mini',
            'HuggingFace','LangChain','langdetect'].map(t => (
            <span key={t} className="lp-about-chip">{t}</span>
          ))}
        </div>

        <span className="lp-about-label">System</span>
        <div className="lp-about-rows">
          {[
            ['Version',   'v0.1'],
            ['Phase',     'Phase 4 — Complete'],
            ['Embedding', 'all-mpnet-base-v2 · 768 dims'],
            ['Privacy',   'Fully local · No cloud · No API keys'],
          ].map(([k,v]) => (
            <div key={k} className="lp-about-row">
              <span>{k}</span><span>{v}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="lp-about-footer">
          LOCAL · PRIVATE · MULTILINGUAL · OPEN SOURCE
        </div>
      </div>
    </div>
  )}
      </div>
    </>
  );
}