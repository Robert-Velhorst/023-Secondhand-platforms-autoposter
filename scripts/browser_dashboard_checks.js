// Run with playwright-cli run-code --filename scripts/browser_dashboard_checks.js
// against a signed-in, isolated test app. This never publishes marketplace data.
async (page) => {
  const shell = await page.request.get(page.url());
  const directives = (shell.headers()['content-security-policy'] || '').split(';').map(value => value.trim());
  if (!directives.includes("style-src 'self'") || !directives.includes("script-src 'self'")) {
    throw new Error('Dashboard must retain strict script/style security policies');
  }
  const result = await page.evaluate(async () => {
    const violations = [];
    const listener = (event) => violations.push(event.violatedDirective);
    document.addEventListener('securitypolicyviolation', listener);
    const fixture = document.createElement('section');
    document.body.append(fixture);
    try {
      fixture.innerHTML = analyticsBarsHtml({ten: 10, five: 5, zero: 0});
      await new Promise((resolve) => setTimeout(resolve, 100));
      if (violations.length) throw new Error(`Analytics violates CSP: ${violations.join(', ')}`);
      const rows = [...fixture.querySelectorAll('.analytics-bar-row')];
      const widths = rows.map((row) => {
        const graphic = row.querySelector('svg');
        const bar = row.querySelector('rect');
        if (!graphic || !bar) throw new Error('Expected a rendered analytics bar');
        return Math.round(100 * bar.getBoundingClientRect().width / graphic.getBoundingClientRect().width);
      });
      if (JSON.stringify(widths) !== '[100,50,0]') throw new Error(`Incorrect bar ratios: ${widths}`);
      if (rows.map((row) => row.querySelector('strong').textContent).join(',') !== '10,5,0') {
        throw new Error('Displayed counts differ from the data');
      }
      fixture.innerHTML = analyticsBarsHtml({'<img src=x onerror=alert(1)>': 2});
      if (fixture.querySelector('img')) throw new Error('Analytics label was interpreted as HTML');
      fixture.innerHTML = analyticsBarsHtml({});
      if (!fixture.textContent.includes('No data')) throw new Error('Missing empty state');
      renderAnalytics();
      await new Promise((resolve) => setTimeout(resolve, 100));
      if (violations.length) throw new Error(`Dashboard violates CSP: ${violations.join(', ')}`);
      return {barPercentages: widths, cspViolations: violations.length, escapedLabels: true, emptyState: true};
    } finally {
      fixture.remove();
      document.removeEventListener('securitypolicyviolation', listener);
    }
  });
  return {status: 'passed', ...result};
}
