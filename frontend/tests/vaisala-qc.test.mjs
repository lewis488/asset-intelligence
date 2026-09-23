import { after, before, test } from 'node:test'
import assert from 'node:assert/strict'
import { chromium } from 'playwright'
import { createServer } from 'vite'

let browser, server, baseURL
before(async () => {
  baseURL = process.env.QC_BASE_URL
  if (!baseURL) {
    server = await createServer({ server: { host: '127.0.0.1', port: 5190, strictPort: true } })
    await server.listen()
    baseURL = 'http://127.0.0.1:5190'
  }
  browser = await chromium.launch({ headless: true })
})
after(async () => { await browser?.close(); await server?.close() })

for (const hasQC of [true, false]) test(hasQC ? 'QC renders whole percentages' : 'older surveys explain re-upload', async t => {
  const context = await browser.newContext()
  t.after(() => context.close())
  await context.addInitScript(() => {
    localStorage.setItem('ai_token', 'test')
    localStorage.setItem('ai_user', JSON.stringify({ id: 1, role: 'admin', email: 'test@example.com' }))
  })
  const page = await context.newPage()
  const survey = { id: 1, source_filename: 'qc.csv', section_count: 1, imported_at: '2026-09-23', network_key: 'stroud' }
  const section = { id: 1, section_ref: 'A', length_m: 10, priority_score: 0, rag_band: 'Green',
    treatment: 'Surface dressing', recommended_action: 'Inspect', assessment_scope: 'section', priority_percentile: 50,
    treatment_assessment: { action: 'Inspect', reason: 'Validate survey coverage before selection.',
      evidence: ['Dressing-related defects: 5.0% (group measure)'],
      candidates: [{ name: 'Surface dressing', rationale: 'Surface-related defects support consideration.',
        prerequisites: ['Confirm pavement support and drainage.'], cautions: ['Visual evidence alone does not establish structural capacity.'] }],
      evidence_gaps: ['Survey coverage needs validation.'], screening_basis: 'Provisional screening triggers, not national criteria.' },
    dressing_pct: 5, micro_pct: 3,
    structural_pct: 0, severity_tier_pcts: { Structural: 0, High: 0, Medium: 5, Low: 3 },
    qc_completeness_pct: hasQC ? 20 : null, qc_completeness_band: hasQC ? 'Low' : null,
    qc_reliability_pct: hasQC ? 100 : null, qc_reliability_band: hasQC ? 'High' : null }
  await page.route('**/*', route => {
    const req = route.request(), path = new URL(req.url()).pathname
    if (['xhr', 'fetch'].includes(req.resourceType()) && /^\/(assets|analysis)\//.test(path)) {
      return route.fulfill({ json: path === '/assets/' ? { assets: [], total: 0 } : path === '/assets/map-data' ? { type: 'FeatureCollection', features: [] } : {} })
    }
    if (['xhr', 'fetch'].includes(req.resourceType()) && path.startsWith('/vaisala/')) {
      const data = path.endsWith('/surveys') ? [survey] : path.endsWith('/stats') ? { ...survey, rag_counts: {}, total_length_km: 0.01 }
        : path.endsWith('/all') ? [section] : { sections: [section], total: 1 }
      return route.fulfill({ json: data })
    }
    if (new URL(req.url()).origin !== new URL(baseURL).origin) return route.abort()
    return route.continue()
  })
  await page.goto(baseURL + '/')
  await page.getByRole('link', { name: 'Vaisala DST' }).click()
  if (hasQC) {
    await page.getByRole('cell', { name: 'A', exact: true }).click()
    await page.getByText(/^20\.0%/).waitFor()
    await page.getByText(/^100\.0%/).waitFor()
    await page.getByText('Action and treatment candidates', { exact: true }).waitFor()
    await page.getByText('Next action: Inspect', { exact: true }).waitFor()
    await page.locator('summary').filter({ hasText: /^Surface dressing$/ }).click()
    await page.getByText('Confirm pavement support and drainage.', { exact: true }).waitFor()
    await page.getByText('Evidence still needed', { exact: true }).click()
    await page.getByText('Survey coverage needs validation.', { exact: true }).waitFor()
    await page.getByText('Treatment-related defect groups', { exact: true }).waitFor()
    assert.equal(await page.getByText('Treatment Suitability', { exact: true }).count(), 0)
    await page.getByText(/not the probability that a treatment is suitable/).waitFor()
    await page.getByRole('button', { name: 'Close', exact: true }).click()
    await page.getByRole('button', { name: 'Relative priority', exact: true }).click()
    await page.getByRole('columnheader', { name: 'Relative percentile', exact: true }).waitFor()
    await page.getByRole('cell', { name: 'A', exact: true }).click()
    await page.getByText('Next action: Inspect', { exact: true }).waitFor()
    await page.locator('summary').filter({ hasText: /^Surface dressing$/ }).waitFor()
    await page.getByText(/Relative rank does not determine treatment suitability/).waitFor()
    await page.getByRole('button', { name: 'Close', exact: true }).click()
  }
  await page.getByRole('button', { name: 'QC', exact: true }).click()
  if (hasQC) {
    await page.getByText('20% network avg.').waitFor()
    await page.getByText('100% network avg.').waitFor()
    assert.equal(await page.getByText('2000%').count(), 0)
    await page.getByRole('cell', { name: '20%', exact: true }).waitFor()
  } else {
    await page.getByText(/Re-upload the original XLSX\/CSV/).waitFor()
    assert.equal(await page.getByText(/separate Vaisala QC process/).count(), 0)
  }
})
