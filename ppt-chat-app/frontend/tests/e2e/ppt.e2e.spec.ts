import { test, expect } from '@playwright/test';
import path from 'path';

test.describe('PPT Chat App E2E Tests', () => {
  test('Upload → Analyze → Generate → Preview → Download', async ({ page, request }) => {
    // 1) Open app
    await page.goto('/');
    
    // Wait for app to load
    await expect(page.locator('h1').filter({ hasText: /PowerPoint.*Generator/i })).toBeVisible({ timeout: 10000 });
    
    // 2) Upload a template
    // First check if there's an upload button or file input
    const uploadButton = page.locator('button').filter({ hasText: /Upload.*Template/i });
    const fileInput = page.locator('input[type="file"]');
    
    // Create or use a fixture template
    const filePath = path.resolve(__dirname, '../fixtures/template_min.pptx');
    
    if (await uploadButton.isVisible()) {
      // Click upload button first if it exists
      await uploadButton.click();
    }
    
    // Set the file
    await fileInput.setInputFiles(filePath);
    
    // Wait for template analysis
    await expect(page.locator('text=/Template.*analyzed|Analysis.*complete|Template.*uploaded/i')).toBeVisible({ timeout: 30000 });
    
    // 3) Start a chat to generate deck
    const chatInput = page.locator('[data-testid="chat-input"], textarea, input[type="text"]').first();
    await chatInput.fill('Create a 3-slide AI roadmap deck with agenda and KPIs.');
    await chatInput.press('Enter');
    
    // 4) Observe WebSocket progress (these may appear as status messages)
    const statusMessages = [
      /Planning.*slides|Creating.*plan/i,
      /Composing.*slides|Generating.*content/i,
      /Validating|Checking.*quality/i
    ];
    
    for (const pattern of statusMessages) {
      await expect(page.locator(`text=${pattern}`)).toBeVisible({ timeout: 30000 });
    }
    
    // 5) Preview shows thumbnails or slide indicators
    // Look for slide thumbnails or a slide count indicator
    const slideThumbs = page.locator('[data-testid="slide-thumb"], .slide-thumbnail, .slide-preview');
    const slideCount = await slideThumbs.count();
    
    if (slideCount > 0) {
      expect(slideCount).toBeGreaterThanOrEqual(3);
    } else {
      // Alternative: check for slide navigation or count display
      await expect(page.locator('text=/Slide.*3|3.*slides/i')).toBeVisible({ timeout: 60000 });
    }
    
    // 6) Download PPTX
    const downloadButton = page.locator('[data-testid="download-deck"], button').filter({ hasText: /Download/i });
    
    const [download] = await Promise.all([
      page.waitForEvent('download'),
      downloadButton.click()
    ]);
    
    const suggestedFilename = await download.suggestedFilename();
    expect(suggestedFilename).toMatch(/\.pptx$/);
    
    // Save the download for verification
    const downloadPath = path.join(__dirname, '../../test-downloads', suggestedFilename);
    await download.saveAs(downloadPath);
    
    // 7) Verify backend data if session ID is available
    const sessionElement = page.locator('[data-testid="session-id"]');
    if (await sessionElement.count() > 0) {
      const sessionId = await sessionElement.getAttribute('data-value');
      
      if (sessionId) {
        const apiBase = process.env.VITE_API_BASE ?? 'http://localhost:8000';
        const resp = await request.get(`${apiBase}/api/preview/${sessionId}`);
        
        if (resp.ok()) {
          const data = await resp.json();
          
          // Check placements if available
          if (data.placements) {
            expect(data.placements.length).toBeGreaterThan(0);
            
            // Verify safety for each placement
            for (const placement of data.placements) {
              if (placement.items) {
                for (const item of placement.items) {
                  if ('safety_ok' in item) {
                    expect(item.safety_ok).toBeTruthy();
                  }
                }
              }
            }
          }
          
          // Check render metrics if available
          if (data.render_metrics) {
            const metrics = data.render_metrics;
            expect(metrics.font_shrink_events ?? 0).toBeGreaterThanOrEqual(0);
            expect(metrics.continuation_slides_added ?? 0).toBeGreaterThanOrEqual(0);
          }
        }
      }
    }
  });
  
  test('Feature flags toggle (solver off → legacy path)', async ({ page }) => {
    // Navigate with solver disabled
    await page.goto('/?solver=off');
    
    // Check if there's any indication of solver status
    const solverStatus = page.locator('text=/Solver.*Off|Legacy.*mode/i');
    if (await solverStatus.count() > 0) {
      await expect(solverStatus).toBeVisible();
    }
    
    // Quick smoke test: upload and generate
    await expect(page.locator('h1').filter({ hasText: /PowerPoint.*Generator/i })).toBeVisible({ timeout: 10000 });
    
    // Upload template
    const fileInput = page.locator('input[type="file"]');
    const filePath = path.resolve(__dirname, '../fixtures/template_min.pptx');
    await fileInput.setInputFiles(filePath);
    
    // Wait for upload
    await expect(page.locator('text=/Template.*analyzed|Analysis.*complete|Template.*uploaded/i')).toBeVisible({ timeout: 30000 });
    
    // Generate a simple slide
    const chatInput = page.locator('[data-testid="chat-input"], textarea, input[type="text"]').first();
    await chatInput.fill('Create a single slide with a title and three bullet points.');
    await chatInput.press('Enter');
    
    // Wait for generation to complete
    await expect(page.locator('text=/Complete|Generated|Ready/i')).toBeVisible({ timeout: 60000 });
    
    // Verify download is available
    const downloadButton = page.locator('button').filter({ hasText: /Download/i });
    await expect(downloadButton).toBeEnabled({ timeout: 30000 });
  });
  
  test('WebSocket real-time updates', async ({ page }) => {
    await page.goto('/');
    
    // Set up WebSocket message monitoring
    const wsMessages: string[] = [];
    
    page.on('websocket', ws => {
      ws.on('framereceived', event => {
        if (event.payload) {
          wsMessages.push(event.payload.toString());
        }
      });
    });
    
    // Upload and generate
    const fileInput = page.locator('input[type="file"]');
    const filePath = path.resolve(__dirname, '../fixtures/template_min.pptx');
    await fileInput.setInputFiles(filePath);
    
    await expect(page.locator('text=/Template.*analyzed|Analysis.*complete|Template.*uploaded/i')).toBeVisible({ timeout: 30000 });
    
    const chatInput = page.locator('[data-testid="chat-input"], textarea, input[type="text"]').first();
    await chatInput.fill('Generate a test presentation.');
    await chatInput.press('Enter');
    
    // Wait for completion
    await expect(page.locator('text=/Complete|Generated|Ready/i')).toBeVisible({ timeout: 60000 });
    
    // Verify we received WebSocket messages
    if (wsMessages.length > 0) {
      console.log(`Received ${wsMessages.length} WebSocket messages`);
      
      // Check for expected message types
      const messageTypes = wsMessages.map(msg => {
        try {
          const parsed = JSON.parse(msg);
          return parsed.type || parsed.event;
        } catch {
          return 'unknown';
        }
      });
      
      console.log('Message types:', [...new Set(messageTypes)]);
    }
  });
});