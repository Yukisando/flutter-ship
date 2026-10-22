// App Privacy for one app, through App Store Connect's web API (the same calls fastlane's
// upload_app_privacy_details_to_app_store makes). Run with javascript_tool in a signed-in
// appstoreconnect.apple.com tab. Fill APP, DATA and TRACKING from declarations.yml (app_privacy).
// It does not publish: check the page, then click Publish.
const APP = '0000000000'; // Apple id, from the App Store Connect URL
const TRACKING = false;
const DATA = {
  // CATEGORY: [[PURPOSES], linked]
  EMAIL_ADDRESS: [['APP_FUNCTIONALITY'], true],
};

const H = { 'Content-Type': 'application/json', 'x-csrf-itc': '[asc-ui]' };
const rel = (type, id) => ({ data: { type, id } });
const out = [];
const existing = await (await fetch(`/iris/v1/apps/${APP}/dataUsages?limit=500`, { credentials: 'include' })).json();
for (const u of existing.data || []) {
  const r = await fetch(`/iris/v1/appDataUsages/${u.id}`, { method: 'DELETE', credentials: 'include', headers: H });
  out.push(`delete ${u.id}:${r.status}`);
}
const post = async (label, relationships) => {
  const body = { data: { type: 'appDataUsages', relationships: { app: rel('apps', APP), ...relationships } } };
  const r = await fetch('/iris/v1/appDataUsages', { method: 'POST', credentials: 'include', headers: H, body: JSON.stringify(body) });
  const err = r.status >= 300 ? JSON.stringify((await r.json().catch(() => ({}))).errors || '') : '';
  out.push(`${label}:${r.status}${err}`);
};
if (Object.keys(DATA).length === 0) {
  await post('not collected', { dataProtection: rel('appDataUsageDataProtections', 'DATA_NOT_COLLECTED') });
}
for (const [cat, [purposes, linked]] of Object.entries(DATA)) {
  const protection = linked ? 'DATA_LINKED_TO_YOU' : 'DATA_NOT_LINKED_TO_YOU';
  for (const p of purposes) {
    await post(`${cat}/${p}`, {
      category: rel('appDataUsageCategories', cat),
      purpose: rel('appDataUsagePurposes', p),
      dataProtection: rel('appDataUsageDataProtections', protection),
    });
  }
  if (TRACKING) {
    await post(`${cat}/tracking`, {
      category: rel('appDataUsageCategories', cat),
      dataProtection: rel('appDataUsageDataProtections', 'DATA_USED_TO_TRACK_YOU'),
    });
  }
}
out.join(' | ');
