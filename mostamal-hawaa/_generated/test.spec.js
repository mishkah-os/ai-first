// Auto-generated Playwright test for mostamal-hawaa
const { test, expect } = require('@playwright/test');

test.describe('mostamal-hawaa', () => {
    test('loads main page', async ({ page }) => {
        await page.goto('http://localhost:9001/');
        await expect(page).toHaveTitle(/.+/);
    });

    test('health endpoint', async ({ request }) => {
        const response = await request.get('http://localhost:9001/health');
        expect(response.ok()).toBeTruthy();
    });
});
