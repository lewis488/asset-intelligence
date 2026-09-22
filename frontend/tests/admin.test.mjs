import { after, before, test } from 'node:test'
import assert from 'node:assert/strict'
import { chromium } from 'playwright'
import { createServer } from 'vite'

let server, browser, baseURL
before(async () => {
  if (process.env.ADMIN_BASE_URL) baseURL = process.env.ADMIN_BASE_URL.replace(/\/$/, '')
  else {
    server = await createServer({ server: { port: 5183, strictPort: true, host: '127.0.0.1' } })
    await server.listen()
    baseURL = `http://127.0.0.1:${server.httpServer.address().port}`
  }
  browser = await chromium.launch({ headless: true })
})
after(async () => { await browser?.close(); await server?.close() })

async function session(t, role = 'admin') {
  const context = await browser.newContext()
  t.after(() => context.close())
  await context.addInitScript(role => {
    localStorage.setItem('ai_token', 'test-token')
    localStorage.setItem('ai_user', JSON.stringify({ id: 1, email: 'admin@example.com', authority_id: 1, role, is_active: true }))
  }, role)
  const page = await context.newPage()
  page.setDefaultTimeout(15000)
  page.setDefaultNavigationTimeout(30000)
  const authorities = [{ id: 1, name: 'First Council', region: 'South' }, { id: 2, name: 'Empty Council', region: null }]
  const users = [{ id: 1, email: 'admin@example.com', authority_id: 1, role: 'admin', is_active: true },
    { id: 2, email: 'viewer@example.com', authority_id: 1, role: 'viewer', is_active: false }]
  const overview = { total_authorities: 2, authorities: [
    { authority_id: 1, authority_name: 'First Council', datasets: {
      scanner: { record_count: 1234, last_upload_date: '2026-09-20T12:00:00' },
      vaisala: { record_count: 25, last_upload_date: null },
      vaisala_network: { record_count: 4, last_upload_date: null },
      cvi: { record_count: 0, last_upload_date: null },
    } }, { authority_id: 2, authority_name: 'Empty Council', datasets: {} },
  ] }
  const requests = []
  await page.route('**/*', async route => {
    const req = route.request(), path = new URL(req.url()).pathname
    if (req.resourceType() === 'document') return route.continue()
    if (path.startsWith('/admin/')) {
      requests.push({ path, method: req.method(), body: req.postDataJSON() })
      if (req.method() === 'POST' && path === '/admin/authorities') {
        const item = { id: 3, ...req.postDataJSON() }; authorities.push(item)
        overview.authorities.push({ authority_id: 3, authority_name: item.name, datasets: {} })
        return route.fulfill({ status: 201, json: item })
      }
      if (req.method() === 'POST' && path === '/admin/users') {
        const { password, ...fields } = req.postDataJSON()
        const item = { id: 3, is_active: true, ...fields }; users.push(item)
        return route.fulfill({ status: 201, json: item })
      }
      if (req.method() === 'PATCH') {
        const index = users.findIndex(u => u.id === Number(path.split('/').at(-1)))
        users[index] = { ...users[index], ...req.postDataJSON() }
        return route.fulfill({ json: users[index] })
      }
      return route.fulfill({ json: path.endsWith('/authorities') ? authorities : path.endsWith('/users') ? users : overview })
    }
    if (['xhr', 'fetch'].includes(req.resourceType()) && /^\/(assets|analysis)\//.test(path)) return route.fulfill({ json: {} })
    if (new URL(req.url()).origin !== baseURL) return route.abort()
    return route.continue()
  })
  return { page, requests }
}

test('admin can see counts, create authorities and users, edit users and inspect grouped inventory', async t => {
  const { page, requests } = await session(t)
  await page.goto(`${baseURL}/admin`)
  await page.getByRole('heading', { name: 'Admin', exact: true }).waitFor()
  assert.equal(await page.getByRole('link', { name: 'Admin', exact: true }).count(), 1)
  const row = page.getByRole('row').filter({ hasText: 'First Council' })
  assert.deepEqual(await row.locator('td').allTextContents(), ['First Council', 'South', '2', '3'])
  await page.getByRole('button', { name: '+ New Authority' }).click()
  await page.getByLabel('Authority name', { exact: true }).fill('New Council')
  await page.getByLabel('Region', { exact: true }).fill('North')
  await page.getByRole('button', { name: 'Create authority', exact: true }).click()
  await page.getByRole('cell', { name: 'New Council', exact: true }).waitFor()
  await page.getByRole('tab', { name: 'Users', exact: true }).click()
  await page.getByRole('button', { name: '+ New User' }).click()
  await page.getByLabel('Email', { exact: true }).fill('new@example.com')
  await page.getByLabel('Password', { exact: true }).fill('new-password')
  await page.getByLabel('Authority', { exact: true }).selectOption('3')
  await page.getByLabel('Role', { exact: true }).selectOption('manager')
  await page.getByRole('button', { name: 'Create user', exact: true }).click()
  const newRow = page.getByRole('row').filter({ hasText: 'new@example.com' })
  await newRow.waitFor()
  assert.match(await newRow.innerText(), /New Council/)
  await newRow.getByRole('button', { name: /Edit/ }).click()
  await page.getByLabel('Role', { exact: true }).selectOption('viewer')
  await page.getByLabel('Active', { exact: true }).uncheck()
  await page.getByRole('button', { name: 'Save changes' }).click()
  await page.getByRole('dialog').waitFor({ state: 'hidden' })
  assert.match(await newRow.innerText(), /viewer/)
  assert.match(await newRow.innerText(), /inactive/i)
  assert.deepEqual(requests.find(r => r.method === 'PATCH').body, { authority_id: 3, role: 'viewer', is_active: false })
  await page.getByRole('tab', { name: 'Data Overview', exact: true }).click()
  const group = page.getByRole('region', { name: 'First Council', exact: true })
  await group.getByText('1,234', { exact: true }).waitFor()
  assert.equal(await group.getByText('25', { exact: true }).count(), 1)
  assert.equal(await group.getByText('Vaisala network', { exact: true }).count(), 1)
  assert.equal(await page.getByRole('region', { name: 'Empty Council' }).count(), 1)
  if (process.env.ADMIN_SCREENSHOT_DIR) {
    await page.screenshot({ path: `${process.env.ADMIN_SCREENSHOT_DIR}/admin-overview.png`, fullPage: true })
    await page.getByRole('tab', { name: 'Users', exact: true }).click()
    await page.screenshot({ path: `${process.env.ADMIN_SCREENSHOT_DIR}/admin-users.png`, fullPage: true })
    await page.getByRole('button', { name: '+ New User' }).click()
    await page.screenshot({ path: `${process.env.ADMIN_SCREENSHOT_DIR}/admin-modal.png`, fullPage: true })
    await page.keyboard.press('Escape')
    await page.setViewportSize({ width: 390, height: 844 })
    await page.screenshot({ path: `${process.env.ADMIN_SCREENSHOT_DIR}/admin-mobile.png`, fullPage: true })
  }
})

for (const role of ['manager', 'viewer', undefined]) {
  test(`${role ?? 'missing role'} cannot mount admin or issue admin requests on direct visits`, async t => {
    const { page, requests } = await session(t, role ?? null)
    await page.goto(`${baseURL}/admin`)
    await page.waitForURL('**/dashboard')
    assert.equal(await page.locator('a[href="/admin"]').count(), 0)
    assert.equal(await page.getByRole('heading', { name: 'Admin', exact: true }).count(), 0)
    assert.equal(requests.length, 0)
  })
}

test('self-demotion removes the admin page and navigation immediately', async t => {
  const { page, requests } = await session(t)
  await page.goto(`${baseURL}/admin`)
  await page.getByRole('tab', { name: 'Users', exact: true }).click()
  await page.getByRole('row').filter({ hasText: 'admin@example.com' }).getByRole('button', { name: /Edit/ }).click()
  await page.getByLabel('Role', { exact: true }).selectOption('manager')
  await page.getByRole('button', { name: 'Save changes' }).click()
  await page.waitForURL('**/dashboard')
  assert.equal(await page.locator('a[href="/admin"]').count(), 0)
  const patchIndex = requests.findIndex(r => r.method === 'PATCH')
  assert.equal(requests.slice(patchIndex + 1).length, 0)
})

test('failed loads can be retried and API validation errors stay in the modal', async t => {
  const { page } = await session(t)
  let fail = true
  await page.route('**/admin/authorities', route => {
    if (route.request().method() === 'POST') return route.fulfill({ status: 422, json: { detail: [{ loc: ['body', 'name'], msg: 'Name is required' }] } })
    if (fail) return route.fulfill({ status: 500, json: { detail: 'Inventory unavailable' } })
    return route.fallback()
  })
  await page.goto(`${baseURL}/admin`)
  await page.getByRole('alert').waitFor()
  fail = false
  await page.getByRole('button', { name: 'Retry' }).click()
  await page.getByRole('button', { name: '+ New Authority' }).click()
  await page.getByLabel('Authority name', { exact: true }).fill('Example')
  await page.getByRole('button', { name: 'Create authority', exact: true }).click()
  await page.getByRole('dialog').getByRole('alert').waitFor()
  assert.match(await page.getByRole('dialog').getByRole('alert').innerText(), /Name is required/)
  await page.keyboard.press('Escape')
  assert.equal(await page.getByRole('dialog').count(), 0)
})

test('self-deactivation signs out without further admin requests', async t => {
  const { page, requests } = await session(t)
  await page.goto(`${baseURL}/admin`)
  await page.getByRole('tab', { name: 'Users', exact: true }).click()
  await page.getByRole('row').filter({ hasText: 'admin@example.com' }).getByRole('button', { name: /Edit/ }).click()
  await page.getByLabel('Active', { exact: true }).uncheck()
  await page.getByRole('button', { name: 'Save changes' }).click()
  await page.waitForURL('**/login')
  assert.equal(await page.evaluate(() => localStorage.getItem('ai_token')), null)
  assert.equal(requests.at(-1).method, 'PATCH')
})

test('signed-out direct visits show sign-in without attempting automatic login', async t => {
  const context = await browser.newContext()
  t.after(() => context.close())
  const page = await context.newPage()
  const requests = []
  await page.route('**/*', route => {
    const request = route.request(), url = new URL(request.url())
    if (request.resourceType() === 'document') return route.continue()
    if (/^\/(admin|auth)\//.test(url.pathname)) {
      requests.push(url.pathname)
      return route.fulfill({ status: 401, json: { detail: 'Not authenticated' } })
    }
    return url.origin === baseURL ? route.continue() : route.abort()
  })
  await page.goto(`${baseURL}/admin`)
  await page.waitForURL('**/login')
  await page.getByRole('button', { name: 'Sign In', exact: true }).waitFor()
  assert.deepEqual(requests, [])
})

test('shared dataset cards retain My Data survey counts and years', async t => {
  const { page } = await session(t, 'manager')
  await page.route('**/assets/my-datasets', route => route.fulfill({ json: {
    scanner: { records: 1234, survey_years: [2025], last_updated: '2026-09-20T12:00:00' },
    vaisala: { surveys: 2, sections: 350, survey_years: [], last_updated: null },
  } }))
  await page.goto(`${baseURL}/my-data`)
  await page.getByText('1,234', { exact: true }).waitFor()
  assert.equal(await page.getByText('2025', { exact: true }).count(), 1)
  assert.equal(await page.getByText('surveys · 350 sections', { exact: true }).count(), 1)
})
