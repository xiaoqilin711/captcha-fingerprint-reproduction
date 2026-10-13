// SpiderMonkey browser-environment driver for a major vendor's click captcha.
//
// Runs the vendor's obfuscated collector (anonymized here as `collector.js`,
// NOT vendored in this repo) inside the xiaojianbang-browser-env SpiderMonkey
// runtime, then drains the virtual event loop so the script reaches the point
// where it exports its fingerprint blob and encrypted session token.
//
// Outputs, for byte-level comparison against a real browser capture:
//   eks     — the encrypted session token emitted on startup
//   collect — the environment-fingerprint + trajectory payload
//
// The `profile` below is a minimal, internally-consistent fingerprint profile
// (screen / viewport / navigator / crypto seed). All vendor-specific origins,
// hashes and identifiers are redacted. `TDC` is the collector's global export
// name and is kept verbatim because it is the hook point this driver targets.
(function () {
  var profile = {
    location: { href: 'https://captcha.example.com/static/template/challenge.00000000.html' },
    navigator: {
      userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:152.0) Gecko/20100101 Firefox/152.0',
      platform: 'Win32',
      language: 'en-US',
      languages: ['en-US', 'en'],
      hardwareConcurrency: 32,
      deviceMemory: 8,
      webdriver: false,
      maxTouchPoints: 0
    },
    screen: { width: 1366, height: 768, availWidth: 1366, availHeight: 720, colorDepth: 24, pixelDepth: 24 },
    viewport: { innerWidth: 340, innerHeight: 250, outerWidth: 1366, outerHeight: 768, devicePixelRatio: 1 },
    features: { canvas: false, webgl: false, audio: false },
    cryptoRandom: Array.from({ length: 65536 }, function (_, i) { return (i * 131 + 17) & 255; }),
    provenance: {
      schema: 'xjb-browser-profile-v1',
      engineVersion: 'Firefox-152',
      origin: 'https://captcha.example.com',
      targetScriptSha256: '0000000000000000000000000000000000000000000000000000000000000000', // redacted
      captureRunId: 'run1-click-baseline',
      capturedAt: 'REDACTED',
      sidecarSha256: '0000000000000000000000000000000000000000000000000000000000000000',
      sections: { location: 'captured', navigator: 'captured', screen: 'captured', viewport: 'captured', features: 'disabled' }
    }
  };

  // Minimal DOM scaffold so the collector's DOM hooks resolve.
  function captchaPlugin(context) {
    var d = context.document;
    function add(tag, id, cls, width, height) {
      var el = d.createElement(tag);
      el.id = id || '';
      el.className = cls || '';
      el.style.width = width + 'px';
      el.style.height = height + 'px';
      d.body.appendChild(el);
      return el;
    }
    add('div', '', 'captcha-embed', 340, 250);
    add('div', 'headerTitle', 'header-title', 340, 40);
    add('div', '', 'challenge-stage', 340, 40);
    add('div', 'verifyBtn', 'verify-button', 100, 40);
    add('div', 'operation', 'operation', 340, 60);
  }

  var runtime = BrowserEnvSpiderMonkey.createSpiderMonkeyRuntime({
    mode: 'production',
    profile: profile,
    now: 1786550784973,
    plugins: [captchaPlugin]
  });

  var error = null;
  try {
    // `collector.js` is the vendor's obfuscated collector, fetched at runtime
    // and NOT committed to this repository. Read it from a local path.
    (function (source) { with (window) { eval(source); } }).call(window, read('collector.js'));
  } catch (caught) {
    error = (caught && caught.name ? caught.name + ': ' : '') +
            (caught && caught.message ? caught.message : String(caught)) + '\n' +
            (caught && caught.stack ? caught.stack : '');
  }

  // Drain timers / promises so the collector finishes its async init.
  for (var round = 0; round < 40; round++) {
    var drained = __drainTasks(1000, 500);
    if (!drained.pending) break;
  }

  var name = window.TDC_NAME || (typeof TDC_NAME !== 'undefined' ? TDC_NAME : null);
  var eks = name && window[name] != null ? String(window[name]) : null;

  var collect = null, collectError = null;
  try {
    if (window.TDC && typeof window.TDC.getData === 'function') {
      collect = String(window.TDC.getData(true));
    }
  } catch (caught) {
    collectError = String(caught && (caught.message || caught));
  }

  var manifest = null;
  try { manifest = runtime.manifest(); } catch (e) { manifest = { manifestError: String(e) }; }

  print(JSON.stringify({
    case: 'captcha-tdc',
    status: !error && window.TDC && typeof window.TDC.getData === 'function' &&
            eks && eks.length > 100 && collect && collect.length > 100 ? 'passed' : 'partial',
    engine: 'spidermonkey',
    sdkReady: !!window.TDC,
    getDataType: window.TDC && typeof window.TDC.getData,
    eksName: name,
    eksLength: eks && eks.length,
    collectLength: collect && collect.length,
    collectError: collectError,
    error: error,
    windowKeys: Object.keys(window).filter(function (k) { return /tdc|TDC|captcha|collect/i.test(k); }),
    manifest: manifest
  }));

  // Full values emitted separately for byte-level diffing against the capture.
  print('@EKS=' + (eks || ''));
  print('@COLLECT=' + (collect || ''));
})();
