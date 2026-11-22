// Run with bb browser-automation after signing in and opening a saved report.
const page = await browser.getPage('main');
const before = await page.snapshot({interactive: true});
const evidence = before.match(/link "02 \/ Query evidence" \[ref=([^\]]+)\]/);
if (!evidence) throw new Error('Open a saved report before running the navigation regression.');
await page.click('ref/' + evidence[1]);
const after = await page.snapshot({interactive: true});
if (!after.includes('Behind the numbers') || after.includes('Loading your reports…')) {
  throw new Error('Query evidence navigated away from the report into the library.');
}
console.log(JSON.stringify({query_evidence_navigation: 'passed'}));
