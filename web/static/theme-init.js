// FOUC guard, loaded as a blocking <script src> in <head> before first paint:
// restore the stored light/dark preference before anything renders. Lives as a
// static file (not inline in app.html) so the page carries zero inline scripts
// and the CSP can license it with script-src 'self' alone.
(function () {
	try {
		var stored = localStorage.getItem('vson-mode');
		var mode = stored === 'light' || stored === 'dark' ? stored : 'dark';
		var theme = mode === 'light' ? 'paper' : 'graphite';
		document.documentElement.setAttribute('data-mode', mode);
		document.documentElement.setAttribute('data-theme', theme);
		var meta = document.querySelector('meta[name="theme-color"]');
		if (meta) meta.content = mode === 'light' ? '#fbfaf7' : '#0d0d0d';
	} catch (_e) {
		/* keep default */
	}
})();
