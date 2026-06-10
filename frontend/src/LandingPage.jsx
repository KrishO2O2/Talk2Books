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
      rgba(196,163,90,0.22) 1.3px,
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
            <a href="#" className="lp-nav-link">GITHUB</a>
            <a href="#" className="lp-nav-link">ABOUT</a>
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

      </div>
    </>
  );
}