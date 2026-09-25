import { after, before, test } from 'node:test'
import assert from 'node:assert/strict'
import { chromium } from 'playwright'
import { createServer } from 'vite'

let browser, server, baseURL
before(async () => {
  baseURL = process.env.PROGRAMME_BASE_URL
  if (!baseURL) {
    server = await createServer({ server: { host: '127.0.0.1', port: 5191, strictPort: true } })
    await server.listen(); baseURL = 'http://127.0.0.1:5191'
  }
  browser = await chromium.launch({ headless: true })
})
after(async () => { await browser?.close(); await server?.close() })

const actions = ['engineer_assessment', 'evidence_validation', 'treatment_appraisal', 'monitor', 'no_action_indicated']
const survey = { id: 1, source_filename: 'programme.csv', imported_at: '2026-09-23T10:00:00Z', network_key: 'stroud' }
const baseItem = { assessment_scope: 'section', urban_rural: null, length_basis: 'section coverage', assessed_length_m: 100,
  priority_score: 3.4, rag_band: 'Amber', evidence_status: 'adequate', queue_rank: 1, queue_size: 1, queue_total: 1,
  next_question: 'Establish the failure mechanism and depth', prerequisite_tasks: ['validate_evidence'],
  treatment_assessment: { action: 'Inspect', reason: 'Legacy action must not appear', evidence: ['Alligator cracking: 5%'],
    candidates: [{ name: 'Localised deeper repair', rationale: 'Check the observed deterioration.', prerequisites: ['Confirm repair depth.'], cautions: ['Not a structural diagnosis.'] }], evidence_gaps: ['Drainage cause is unknown.'], screening_basis: 'Provisional screening policy.' },
  review: { sequence: 0, status: 'unreviewed', client_action: null, comment: '', assignee: '' },
}

async function setup(t, role = 'manager', extraCount = 0, proportionate = false) {
  const context = await browser.newContext({ acceptDownloads: true }); t.after(() => context.close())
  await context.addInitScript(role => {
    localStorage.setItem('ai_token', 'test')
    localStorage.setItem('ai_user', JSON.stringify({ id: 1, role, email: 'test@example.com' }))
  }, role)
  const page = await context.newPage(), requests = [], saved = []
  page.setDefaultTimeout(15000)
  let failReview = false
  const items = [
    { ...baseItem, item_key: 'structural', section_ref: 'STRUCTURAL', recommended_action: 'engineer_assessment', brief: 'Review cracking on this extent. Establish the failure mechanism and depth.', priority_explanation: 'Joint condition rank 1 of 1 scored lengths in Engineer assessment, section view; score 3.4.' },
    { ...baseItem, item_key: 'unknown', section_ref: 'UNKNOWN', recommended_action: 'evidence_validation', brief: 'Check the original export and imagery before targeted verification.', priority_score: null, rag_band: null, evidence_status: 'limited', queue_rank: null, validation_order: 1, queue_size: 0, assessed_length_m: null, length_basis: 'unresolved', assessment_scope: '10m' },
    { ...baseItem, item_key: 'surface', section_ref: 'SURFACE', recommended_action: 'treatment_appraisal', brief: 'Compare conditional surfacing options.' },
    { ...baseItem, item_key: 'clear', section_ref: 'CLEAR', recommended_action: 'no_action_indicated', brief: 'Continue existing inspections.', priority_score: 0, rag_band: 'Green', queue_rank: null },
  ]
  for (let n = 0; n < extraCount; n++) items.push({ ...baseItem, item_key: `extra-${n}`, section_ref: `EXTRA-${n}`, recommended_action: 'engineer_assessment', brief: 'Review recorded defects.' })
  if (proportionate) items.push({ ...baseItem, item_key: 'watch', section_ref: 'WATCH',
    recommended_action: 'monitor', queue_rank: null, brief: 'Arrange a documented review under authority inspection policy.',
    treatment_assessment: { ...baseItem.treatment_assessment, action: 'Monitor observed deterioration', candidates: [] } })
  const summary = { total_items: items.length, known_length_m: 300 + extraCount * 100, unresolved_extents: 1, action_counts: Object.fromEntries(actions.map(a => [a, items.filter(i => i.recommended_action === a).length])), action_lengths_m: { engineer_assessment: 100 + extraCount * 100, evidence_validation: 0, treatment_appraisal: 100, monitor: 0, no_action_indicated: 100 } }
  if (proportionate) summary.action_diagnostics = { model_version: 'vaisala-programme-v2', total_items: 5,
    reason_counts: { minor_acceptable: 1, limited_deterioration: 1, candidate_trigger: 1, significant_observation: 1, evidence_limited: 1 },
    incomplete_readings_count: 1, limited_qc_count: 0 }
  function payload(url, snapshot = false) {
    let filtered = items.filter(i => (!url.searchParams.get('action') || (i.review.client_action || i.recommended_action) === url.searchParams.get('action')) && (!url.searchParams.get('search') || i.section_ref.toLowerCase().includes(url.searchParams.get('search').toLowerCase())) && (!url.searchParams.get('scale') || i.assessment_scope === url.searchParams.get('scale')) && (!url.searchParams.get('evidence_status') || i.evidence_status === url.searchParams.get('evidence_status')) && (!url.searchParams.get('review_status') || i.review.status === url.searchParams.get('review_status')))
    const currentSummary = { ...summary, current_action_counts: Object.fromEntries(actions.map(a => [a, items.filter(i => (i.review.client_action || i.recommended_action) === a).length])) }
    const pageNumber = Number(url.searchParams.get('page') || 1)
    return { ...(snapshot ? { id: 7 } : {}), survey_id: 1, merge_scale: 'section', split: 'combined', model_version: 'programme-v1', policy_version: 'policy-v1', generated_at: '2026-09-24T09:00:00Z', summary: currentSummary, total: items.length, filtered_total: filtered.length, page: pageNumber, page_size: 50, items: filtered.slice((pageNumber - 1) * 50, pageNumber * 50),
      cohorts: [{ assessment_scope: 'section', action: 'engineer_assessment', total_items: 1, scored_items: 1, known_length_m: 100, unresolved_extents: 0 }, { assessment_scope: '10m', action: 'evidence_validation', total_items: 1, scored_items: 0, known_length_m: 0, unresolved_extents: 1 }] }
  }
  await page.route('**/*', async route => {
    const req = route.request(), url = new URL(req.url()), path = url.pathname
    if (['xhr', 'fetch'].includes(req.resourceType())) {
      requests.push({ path, search: url.search, method: req.method(), body: req.postDataJSON() })
      if (path.endsWith('/reviews')) {
        if (failReview) { failReview = false; return route.fulfill({ status: 409, json: { detail: 'Stale review' } }) }
        const body = req.postDataJSON(), item = items.find(i => path.includes(`/items/${i.item_key}/`))
        const review = { ...body, sequence: item.review.sequence + 1, reviewer_name: 'Engineer', created_at: '2026-09-24T10:00:00Z' }
        item.review = review; item.review_history = [review]
        return route.fulfill({ json: review })
      }
      if (path.endsWith('/export')) return route.fulfill({ contentType: 'text/csv', body: 'item_key,recommended_action\nstructural,engineer_assessment\n' })
      if (/\/items\//.test(path)) return route.fulfill({ json: items.find(i => path.endsWith('/' + i.item_key)) })
      if (path.endsWith('/programmes')) {
        if (req.method() === 'POST') { saved.push({ id: 7, generated_at: '2026-09-24T09:00:00Z', merge_scale: 'section', split: 'combined' }); return route.fulfill({ json: payload(url, true) }) }
        return route.fulfill({ json: saved })
      }
      if (path.endsWith('/programme') || /\/programmes\/7$/.test(path)) return route.fulfill({ json: payload(url, path.endsWith('/7')) })
      if (path === '/vaisala/surveys') return route.fulfill({ json: [survey] })
      if (path === '/vaisala/network-geometry/current') return route.fulfill({ json: { active: true, id: 1, source_filename: 'network.geojson', section_field: 'section_ref', feature_count: 1 } })
      if (path === '/vaisala/network-geometry/features') return route.fulfill({ json: { type: 'FeatureCollection', network_active: true, matched_features: 0, total_features: 1, features: [{ type: 'Feature', geometry: { type: 'LineString', coordinates: [[-2.2, 51.5], [-2.19, 51.5]] }, properties: { section_key: 'RECOVERED', matched: false, programme_geometry_scope: 'Section locator geometry; programme intervals are not clipped.', programme_items: [
        { ...items[0], chunk_label: '0–10m', assessment_scope: 'section' }, { ...items[1], chunk_label: '10–20m', assessment_scope: 'section' },
      ] } }] } })
      if (path.endsWith('/stats')) return route.fulfill({ json: { total_length_km: 0.3, section_count: 4, rag_counts: {}, has_urban_rural: true } })
      if (path.startsWith('/vaisala/')) return route.fulfill({ json: { sections: [], total: 0 } })
      return route.fulfill({ json: path === '/assets/' ? { assets: [], total: 0 } : path === '/assets/map-data' ? { type: 'FeatureCollection', features: [] } : {} })
    }
    if (url.origin !== new URL(baseURL).origin) return route.abort()
    return route.continue()
  })
  await page.goto(baseURL + '/')
  await page.getByRole('link', { name: 'Vaisala DST' }).click()
  await page.getByRole('button', { name: 'Action programme', exact: true }).click()
  await page.getByRole('button', { name: 'STRUCTURAL', exact: true }).waitFor()
  return { page, requests, failNextReview: () => { failReview = true } }
}

test('queues reconcile, unknown scores stay visible, filters preserve programme totals', async t => {
  const { page, requests } = await setup(t)
  await page.getByText('4 assessed records').waitFor()
  await page.getByText('1 unresolved extents', { exact: true }).waitFor()
  await page.getByRole('button', { name: /^Monitor observed deterioration \(0\)/ }).click()
  await page.getByText(/Record who will review the observed deterioration/).waitFor()
  await page.getByText(/No records match these filters/).waitFor()
  await page.getByRole('button', { name: /^Validate evidence/ }).click()
  await page.getByRole('button', { name: 'UNKNOWN', exact: true }).waitFor()
  await page.getByRole('cell', { name: /Unknown score/ }).waitFor()
  await page.getByText('4 assessed records').waitFor()
  await page.getByLabel('Find location').fill('UNKNOWN')
  await page.getByLabel('Scale cohort').selectOption('10m')
  await page.getByRole('button', { name: 'UNKNOWN', exact: true }).waitFor()
  assert.equal(await page.getByLabel('Find location').inputValue(), 'UNKNOWN')
  assert.ok(requests.some(r => r.search.includes('scale=10m') && r.search.includes('search=UNKNOWN')))
  assert.ok(!requests.some(r => /[?&](action|scale|rag_band|evidence_status|review_status)=(&|$)/.test(r.search)))
  await page.getByRole('button', { name: 'Clear filters', exact: true }).click()
  await page.getByRole('button', { name: 'STRUCTURAL', exact: true }).click()
  const detail = page.getByRole('region', { name: 'Programme item detail' })
  await detail.getByText('Model recommendation: Engineer assessment').waitFor()
  await detail.getByText('Question to resolve:', { exact: false }).waitFor()
  assert.equal(await detail.getByText('Next action: Inspect', { exact: true }).count(), 0)
  await detail.getByText('Localised deeper repair', { exact: true }).click()
  await detail.getByText('Confirm repair depth.', { exact: true }).waitFor()
})

test('proportionate diagnostics explain minor acceptance and automatic monitoring', async t => {
  const { page } = await setup(t, 'manager', 0, true)
  await page.getByText('Why these actions?', { exact: true }).click()
  await page.getByText(/Minor observations within the policy acceptable extent/).waitFor()
  await page.getByText(/Thresholds are provisional authority screening choices/).waitFor()
  assert.equal(await page.getByText(/No automatic monitoring rule is enabled/).count(), 0)
  await page.getByRole('button', { name: /^Monitor observed deterioration \(1\)/ }).click()
  await page.getByRole('button', { name: 'WATCH', exact: true }).click()
  const detail = page.getByRole('region', { name: 'Programme item detail' })
  await detail.getByText('Model recommendation: Monitor observed deterioration').waitFor()
  assert.equal(await detail.getByText('Localised deeper repair', { exact: true }).count(), 0)
})

test('saved review workflow retains model action, handles conflicts, exports correct scope', async t => {
  const { page, requests, failNextReview } = await setup(t)
  await page.getByRole('button', { name: 'Save programme', exact: true }).click()
  await page.getByText(/Programme saved\. Recommendations are frozen/).waitFor()
  await page.getByRole('button', { name: 'STRUCTURAL', exact: true }).click()
  await page.getByLabel('Review status', { exact: true }).selectOption('deferred')
  assert.equal(await page.getByRole('button', { name: 'Save review', exact: true }).isDisabled(), true)
  await page.getByLabel('Client action', { exact: true }).selectOption('monitor')
  await page.getByLabel('Review comment').fill('Client will revisit the observed cracking under its inspection policy.')
  failNextReview()
  await page.getByRole('button', { name: 'Save review', exact: true }).click()
  await page.getByText(/Another reviewer changed this item/).waitFor()
  assert.match(await page.getByLabel('Review comment').inputValue(), /Client will revisit/)
  await page.getByRole('button', { name: 'Load latest review', exact: true }).click()
  // Explicit refresh loads the latest server state before applying a revised decision.
  await page.getByLabel('Review status', { exact: true }).selectOption('assigned')
  await page.getByLabel('Client action', { exact: true }).selectOption('')
  await page.getByLabel('Assignee label').fill('Area engineer')
  await page.getByLabel('Review comment').fill('Inspect mechanism before selecting repair.')
  await page.getByRole('button', { name: 'Save review', exact: true }).click()
  await page.getByText('Review saved. Model recommendation remains unchanged.').waitFor()
  assert.ok(requests.some(r => r.path.endsWith('/reviews') && r.body.expected_sequence === 0 && r.body.assignee === 'Area engineer'))
  await page.getByText('Model recommendation: Engineer assessment').waitFor()
  await page.getByRole('button', { name: /^Engineer assessment \(1\)/ }).click()
  const download = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Export whole programme CSV', exact: true }).click()
  await download
  assert.ok(requests.some(r => r.path.endsWith('/programmes/7/export') && r.search.includes('filtered=false') && !r.search.includes('action=')))
  const filteredDownload = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Export filtered XLSX', exact: true }).click()
  await filteredDownload
  assert.ok(requests.some(r => r.path.endsWith('/export') && r.search.includes('filtered=true') && r.search.includes('action=engineer_assessment')))
  await page.getByRole('button', { name: '100m', exact: true }).click()
  await page.getByRole('button', { name: 'STRUCTURAL', exact: true }).waitFor()
  assert.equal(await page.getByLabel('Programme version').inputValue(), '')
  await page.getByRole('button', { name: 'STRUCTURAL', exact: true }).click()
  await page.getByText('Save programme to record reviews against a fixed snapshot.').waitFor()
  assert.ok(requests.some(r => r.path.endsWith('/programme/items/structural') && r.search.includes('merge_scale=100m') && r.search.includes('policy_version=policy-v1')))
})

test('viewers can inspect and export without mutation controls', async t => {
  const { page, requests } = await setup(t, 'viewer')
  assert.equal(await page.getByRole('button', { name: 'Save programme', exact: true }).count(), 0)
  await page.getByRole('button', { name: 'STRUCTURAL', exact: true }).click()
  await page.getByText('Read-only access: reviews can be viewed and exported.').waitFor()
  assert.equal(await page.getByRole('button', { name: 'Save review', exact: true }).count(), 0)
  assert.ok(!requests.some(r => r.method === 'POST'))
})

test('client monitoring decision moves the worklist without inventing a new rank', async t => {
  const { page } = await setup(t)
  await page.getByRole('button', { name: 'Save programme', exact: true }).click()
  await page.getByText(/Programme saved\. Recommendations are frozen/).waitFor()
  await page.getByRole('button', { name: 'STRUCTURAL', exact: true }).click()
  await page.getByLabel('Review status', { exact: true }).selectOption('accepted')
  await page.getByLabel('Client action', { exact: true }).selectOption('monitor')
  await page.getByLabel('Review comment').fill('Engineer reviewed imagery and will revisit recorded cracking through the existing inspection policy.')
  await page.getByRole('button', { name: 'Save review', exact: true }).click()
  await page.getByRole('button', { name: /^Monitor observed deterioration \(1\)/ }).click()
  await page.getByRole('cell', { name: /Client decision · unranked/ }).waitFor()
  await page.getByRole('button', { name: 'STRUCTURAL', exact: true }).click()
  await page.getByText('Model recommendation: Engineer assessment').waitFor()
  await page.getByLabel('Review status', { exact: true }).selectOption('completed')
  await page.getByRole('button', { name: 'Save review', exact: true }).click()
  await page.getByText('Review saved. Model recommendation remains unchanged.').waitFor()
  await page.getByLabel('Review status', { exact: true }).selectOption('deferred')
  await page.getByLabel('Review comment').fill('Awaiting authority inspection review.')
  await page.getByRole('button', { name: 'Save review', exact: true }).click()
  await page.getByText('Current status:', { exact: false }).filter({ hasText: 'deferred' }).waitFor()
})

test('pagination preserves programme totals and location filtering resets to the first page', async t => {
  const { page } = await setup(t, 'manager', 51)
  await page.getByText('55 assessed records').waitFor()
  await page.getByRole('button', { name: 'Next page', exact: true }).click()
  await page.getByRole('button', { name: 'EXTRA-50', exact: true }).waitFor()
  await page.getByText(/Showing 51–55 of 55 filtered records/).waitFor()
  await page.getByLabel('Find location').fill('UNKNOWN')
  await page.getByRole('button', { name: 'UNKNOWN', exact: true }).waitFor()
  await page.getByText(/Showing 1–1 of 1 filtered records; 55 in the whole programme/).waitFor()
})

test('map keeps recovered programme items visible without a legacy section match', async t => {
  const { page } = await setup(t)
  await page.getByRole('button', { name: 'Map', exact: true }).click()
  const canvas = page.locator('#vaisala-map canvas')
  await canvas.waitFor()
  await page.locator('#vaisala-map').click()
  await page.getByText('Programme items (2)', { exact: true }).waitFor()
  await page.locator('summary').filter({ hasText: '0–10m' }).click()
  await page.getByText('Review cracking on this extent. Establish the failure mechanism and depth.', { exact: true }).waitFor()
  await page.locator('summary').filter({ hasText: '10–20m' }).click()
  await page.getByText('Check the original export and imagery before targeted verification.', { exact: true }).waitFor()
  assert.equal(await page.getByText(/No scored data joined for this section/).count(), 0)
})
