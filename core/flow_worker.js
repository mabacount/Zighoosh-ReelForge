/**
 * Zighoosh ReelForge - Native Google Flow Automation Worker
 * Uses Playwright over Chrome DevTools Protocol (CDP) on port 9222.
 * Fully supports Persian (fa-IR) and English UI, handles both Direct Mode and Agent Mode,
 * auto-detects VPN / PUBLIC_ERROR_UNUSUAL_ACTIVITY, and downloads full-resolution assets.
 */

let chromium;
try {
  chromium = require('playwright').chromium;
} catch (e) {
  try {
    const globalPath = path.join(process.env.APPDATA || '', 'npm', 'node_modules', 'playwright');
    chromium = require(globalPath).chromium;
  } catch (e2) {
    try {
      chromium = require('C:/Users/m_a_b/AppData/Roaming/npm/node_modules/playwright').chromium;
    } catch (e3) {
      throw new Error("Playwright is not installed. Please run: npm install -g playwright");
    }
  }
}
const fs = require('fs');
const path = require('path');

const CDP_PORT = 9222;
const CDP_URL = `http://127.0.0.1:${CDP_PORT}`;

// Helper: parse CLI arguments
function parseArgs() {
  const args = process.argv.slice(2);
  const options = {};
  for (let i = 0; i < args.length; i++) {
    if (args[i].startsWith('--')) {
      const key = args[i].slice(2);
      const next = args[i + 1];
      if (next && !next.startsWith('--')) {
        options[key] = next;
        i++;
      } else {
        options[key] = true;
      }
    }
  }
  return options;
}

// Connect to Chrome over CDP
async function connectToFlow(timeoutMs = 15000) {
  const browser = await chromium.connectOverCDP(CDP_URL, { timeout: timeoutMs });
  const contexts = browser.contexts();
  if (!contexts.length) throw new Error("No browser contexts found on CDP port " + CDP_PORT);
  const context = contexts[0];
  const pages = context.pages();

  let page = pages.find(p => p.url().includes('flow.google.com'));
  if (!page && pages.length > 0) {
    page = pages[0];
    await page.goto('https://flow.google.com', { waitUntil: 'domcontentloaded' });
  } else if (!page) {
    page = await context.newPage();
    await page.goto('https://flow.google.com', { waitUntil: 'domcontentloaded' });
  }

  await page.bringToFront();
  return { browser, page };
}

// Ensure active project canvas is open
async function ensureProjectCanvas(page) {
  const url = page.url();
  if (url.includes('/project/') && !url.includes('/project/create')) {
    return true;
  }

  // Look for first project card on dashboard
  const projectLink = page.locator('a[href*="/project/"], .project-card, [role="link"]').first();
  if (await projectLink.isVisible()) {
    await projectLink.click();
    await page.waitForTimeout(2000);
    return true;
  }

  return false;
}

// Ensure Direct Mode (toggle OFF Agent Mode chip if active)
async function ensureDirectMode(page) {
  const agentChip = page.locator('.agent-mode-chip');
  if (await agentChip.isVisible()) {
    const cls = (await agentChip.getAttribute('class')) || '';
    if (cls.includes('agent-mode-chip-checked')) {
      await agentChip.click();
      await page.waitForTimeout(500);
    }
  }

  // If inside agent panel settings view, close it
  const backBtn = page.locator('button[aria-label="برگشتن"], button[aria-label="Back"]').first();
  if (await backBtn.isVisible()) {
    await backBtn.click();
    await page.waitForTimeout(300);
  }
}

// Configure Settings (Media, Aspect, Model)
async function configureSettings(page, { media = 'image', aspect = '9:16', model = null }) {
  await ensureDirectMode(page);

  const settingsBtn = page.locator('.settings-trigger-button, button[aria-label*="تنظیمات"], button[aria-label*="Settings"]').first();
  if (await settingsBtn.isVisible()) {
    await settingsBtn.click();
    await page.waitForTimeout(400);

    // Media type (image vs video)
    const isImage = media.toLowerCase().includes('image') || media.toLowerCase().includes('عکس') || media.toLowerCase().includes('تصویر');
    const mediaSelector = isImage
      ? '.cdk-overlay-pane mat-button-toggle:has-text("تصویر"), .cdk-overlay-pane mat-button-toggle:has-text("Image") button'
      : '.cdk-overlay-pane mat-button-toggle:has-text("ویدیو"), .cdk-overlay-pane mat-button-toggle:has-text("Video") button';
    const mediaToggle = page.locator(mediaSelector).first();
    if (await mediaToggle.isVisible()) {
      await mediaToggle.click();
      await page.waitForTimeout(250);
    }

    // Aspect ratio
    const aspectClean = aspect.replace(':', '_');
    const aspectToggle = page.locator(`.cdk-overlay-pane mat-button-toggle:has-text("${aspect}"), .cdk-overlay-pane mat-button-toggle[value*="${aspectClean}"] button`).first();
    if (await aspectToggle.isVisible()) {
      await aspectToggle.click();
      await page.waitForTimeout(200);
    }

    // Batch count x1
    const batch1 = page.locator('.cdk-overlay-pane mat-button-toggle:has-text("x1"), .cdk-overlay-pane mat-button-toggle:has-text("۱") button').first();
    if (await batch1.isVisible()) {
      await batch1.click();
      await page.waitForTimeout(150);
    }

    // Close overlay
    await page.keyboard.press('Escape');
    await page.waitForTimeout(300);
  }
}

// Submit prompt and monitor generation
async function generateAndDownload(page, { prompt, outputPath, media = 'image', timeoutSec = 180 }) {
  await ensureProjectCanvas(page);
  await ensureDirectMode(page);

  // Collect initial assets
  const initialUrls = await page.evaluate(() => {
    const imgs = Array.from(document.querySelectorAll('img')).map(i => i.src).filter(s => s && s.includes('/asb/'));
    const vids = Array.from(document.querySelectorAll('video')).map(v => v.src || v.querySelector('source')?.src).filter(Boolean);
    return { imgs, vids };
  });

  // Track network for errors
  let unusualActivityError = false;
  const onResponse = async (res) => {
    if (res.url().includes('batchexecute') || res.url().includes('StreamChat')) {
      try {
        const text = await res.text();
        if (text.includes('PUBLIC_ERROR_UNUSUAL_ACTIVITY')) {
          unusualActivityError = true;
        }
      } catch (e) {}
    }
  };
  page.on('response', onResponse);

  // Type prompt
  const pm = page.locator('.ProseMirror').first();
  await pm.click();
  await page.keyboard.press('Control+A');
  await page.keyboard.press('Backspace');
  await page.waitForTimeout(150);

  // Use keyboard.type to simulate realistic typing
  await page.keyboard.type(prompt, { delay: 3 });
  await page.waitForTimeout(500);

  // Click generate
  const genBtn = page.locator('button.generate-icon-button, button[aria-label="شروع تولید"], button[aria-label="Generate"]').first();
  if (!(await genBtn.isEnabled())) {
    throw new Error("Generate button is disabled!");
  }
  await genBtn.click();

  // Poll for completion
  const startTime = Date.now();
  const maxWaitMs = timeoutSec * 1000;
  let downloadedUrl = null;

  while (Date.now() - startTime < maxWaitMs) {
    await page.waitForTimeout(3000);

    if (unusualActivityError) {
      page.off('response', onResponse);
      return {
        ok: false,
        error: "PUBLIC_ERROR_UNUSUAL_ACTIVITY",
        message: "گوگل پیام «فعالیت غیرعادی (Unusual Activity)» صادر کرده است. این خطا به دلیل استفاده از IP اشتراکی VPN رخ می‌دهد. لطفاً سرور VPN خود را تغییر دهید یا موقتاً خاموش کنید."
      };
    }

    // Check for error tile on canvas
    const errorMsg = await page.evaluate(() => {
      const err = document.querySelector('.error-tile, [class*="error-tile"]');
      return err ? err.innerText : null;
    });
    if (errorMsg && errorMsg.includes('فعالیت غیرعادی')) {
      page.off('response', onResponse);
      return {
        ok: false,
        error: "PUBLIC_ERROR_UNUSUAL_ACTIVITY",
        message: "گوگل پیام «فعالیت غیرعادی (Unusual Activity)» صادر کرده است. این خطا به دلیل استفاده از IP اشتراکی VPN رخ می‌دهد. لطفاً سرور VPN خود را تغییر دهید یا موقتاً خاموش کنید."
      };
    }

    // Check for new asset
    const currentUrls = await page.evaluate(() => {
      const imgs = Array.from(document.querySelectorAll('img')).map(i => i.src).filter(s => s && s.includes('/asb/'));
      const vids = Array.from(document.querySelectorAll('video')).map(v => v.src || v.querySelector('source')?.src).filter(Boolean);
      return { imgs, vids };
    });

    const isImage = media.toLowerCase().includes('image') || media.toLowerCase().includes('تصویر');
    if (isImage) {
      const newImgs = currentUrls.imgs.filter(u => !initialUrls.imgs.includes(u));
      if (newImgs.length > 0) {
        downloadedUrl = newImgs[newImgs.length - 1];
        break;
      }
    } else {
      const newVids = currentUrls.vids.filter(u => !initialUrls.vids.includes(u));
      if (newVids.length > 0) {
        downloadedUrl = newVids[newVids.length - 1];
        break;
      }
    }
  }

  page.off('response', onResponse);

  if (!downloadedUrl) {
    return {
      ok: false,
      error: "TIMEOUT",
      message: `زمان انتظار (${timeoutSec} ثانیه) برای تولید رسانه به پایان رسید.`
    };
  }

  // Fetch full resolution asset and save
  let highResUrl = downloadedUrl;
  if (highResUrl.includes('=s512')) {
    highResUrl = highResUrl.replace('=s512-rw', '=s0').replace('=s512', '=s0');
  }

  const base64Data = await page.evaluate(async (url) => {
    const res = await fetch(url);
    const blob = await res.blob();
    return new Promise((resolve) => {
      const reader = new FileReader();
      reader.onloadend = () => resolve(reader.result.split(',')[1]);
      reader.readAsDataURL(blob);
    });
  }, highResUrl);

  const outDir = path.dirname(outputPath);
  if (!fs.existsSync(outDir)) {
    fs.mkdirSync(outDir, { recursive: true });
  }

  fs.writeFileSync(outputPath, Buffer.from(base64Data, 'base64'));
  const fileSize = fs.statSync(outputPath).size;

  return {
    ok: true,
    url: highResUrl,
    outputPath,
    fileSize
  };
}

// MAIN CLI DISPATCHER
async function main() {
  const options = parseArgs();
  const action = options.action || 'diagnostics';

  try {
    const { browser, page } = await connectToFlow(15000);

    if (action === 'diagnostics') {
      const url = page.url();
      const isAuth = await page.evaluate(() => {
        return !!document.querySelector('.gb_0, .gb_X, [aria-label*="Google Account"], [aria-label*="حساب Google"]');
      });
      const projectId = url.includes('/project/') ? url.split('/project/')[1].split('/')[0].split('?')[0] : null;

      console.log(JSON.stringify({
        ok: true,
        cdpOpen: true,
        googleAuthenticated: isAuth,
        activeUrl: url,
        projectId
      }, null, 2));
    } else if (action === 'open-new-project') {
      let currentUrl = page.url();
      let created = false;

      if (!currentUrl.includes('flow.google.com')) {
        await page.goto('https://flow.google.com', { waitUntil: 'domcontentloaded' });
        await page.waitForTimeout(2000);
      }

      await page.bringToFront();

      // Look for New Project buttons (Persian and English UI support)
      const newProjectSelectors = [
        'button:has-text("پروژه جدید")',
        'button:has-text("New project")',
        'button:has-text("پروژه نو")',
        'button[aria-label*="پروژه جدید"]',
        'button[aria-label*="New project"]',
        'button[aria-label*="Create"]',
        'a[href*="/project/create"]',
        '.new-project-button',
        '.create-project-card',
        'mat-card:has-text("پروژه جدید")',
        'mat-card:has-text("New project")'
      ];

      for (const sel of newProjectSelectors) {
        try {
          const btn = page.locator(sel).first();
          if (await btn.isVisible({ timeout: 1000 })) {
            await btn.click();
            await page.waitForTimeout(2000);
            created = true;
            break;
          }
        } catch (e) {}
      }

      // If still not on a project canvas, look for first project card
      if (!page.url().includes('/project/')) {
        try {
          const firstCard = page.locator('a[href*="/project/"], .project-card').first();
          if (await firstCard.isVisible({ timeout: 1000 })) {
            await firstCard.click();
            await page.waitForTimeout(2000);
            created = true;
          }
        } catch (e) {}
      }

      try {
        await ensureDirectMode(page);
      } catch (e) {}

      await page.bringToFront();
      const finalUrl = page.url();
      const projectId = finalUrl.includes('/project/') ? finalUrl.split('/project/')[1].split('/')[0].split('?')[0] : null;

      console.log(JSON.stringify({
        ok: true,
        action: 'open-new-project',
        created,
        activeUrl: finalUrl,
        projectId,
        message: created ? "پروژه جدید با موفقیت در گوگل فلو ایجاد شد." : "صفحه گوگل فلو آماده به کار است."
      }, null, 2));
    } else if (action === 'insert-prompt') {
      let promptText = '';
      if (options['prompt-file'] && fs.existsSync(options['prompt-file'])) {
        promptText = fs.readFileSync(options['prompt-file'], 'utf8').trim();
      } else if (options.prompt) {
        promptText = options.prompt.trim();
      }

      if (!promptText) {
        throw new Error("متن پرامپت خالی است.");
      }

      await page.bringToFront();

      // Find the prompt editor in Google Flow
      const inputSelectors = [
        '.ProseMirror[contenteditable="true"]',
        '.ProseMirror',
        'div[contenteditable="true"][role="textbox"]',
        'div[contenteditable="true"]',
        'textarea.prompt-input',
        'textarea[aria-label*="prompt" i]',
        'textarea[placeholder*="prompt" i]',
        'textarea[placeholder*="پرامپت" i]',
        'textarea'
      ];

      let inputEl = null;
      for (const sel of inputSelectors) {
        try {
          const el = page.locator(sel).first();
          if (await el.isVisible({ timeout: 1000 })) {
            inputEl = el;
            break;
          }
        } catch (e) {}
      }

      if (!inputEl) {
        throw new Error("کادر متنی پرامپت در Google Flow پیدا نشد. لطفاً صفحه پروژه را در کروم باز نگه دارید.");
      }

      await inputEl.scrollIntoViewIfNeeded();
      await inputEl.click();
      await page.waitForTimeout(150);

      // Clear existing content
      await page.keyboard.press('Control+A');
      await page.keyboard.press('Backspace');
      await page.waitForTimeout(100);

      // Insert text with full Unicode / Persian support
      await page.keyboard.insertText(promptText);
      await page.waitForTimeout(300);

      await page.bringToFront();

      console.log(JSON.stringify({
        ok: true,
        action: 'insert-prompt',
        length: promptText.length,
        message: "متن پرامپت با موفقیت در کادر گوگل فلو درج شد."
      }, null, 2));
    } else if (action === 'generate-thumbnail') {
      const projectPath = options.project;
      const prompt = options.prompt;
      const aspect = options.aspect || '9:16';
      const model = options.model || 'Nano Banana 2.1';
      const timeout = parseInt(options.timeout || '180', 10);

      const outputPath = path.join(projectPath, '03_Raw_DropZone', 'Audio_BGM', 'AI_Background.png');

      await configureSettings(page, { media: 'image', aspect, model });
      const result = await generateAndDownload(page, {
        prompt,
        outputPath,
        media: 'image',
        timeoutSec: timeout
      });

      console.log(JSON.stringify(result, null, 2));
    } else if (action === 'run-pipeline') {
      const projectPath = options.project;
      const isDryRun = !!options['dry-run'];
      const flowJsonPath = path.join(projectPath, '02_AI_Brain_JSON', 'flow.json');

      if (!fs.existsSync(flowJsonPath)) {
        throw new Error(`Pipeline manifest not found at: ${flowJsonPath}`);
      }

      const flowData = JSON.parse(fs.readFileSync(flowJsonPath, 'utf8'));
      const scenes = flowData.scenes || [];

      if (isDryRun) {
        console.log(JSON.stringify({
          ok: true,
          dryRun: true,
          totalScenes: scenes.length,
          scenes: scenes.map(s => ({
            name: s.name,
            media: s.media,
            aspect: s.aspect,
            model: s.model,
            duration: s.duration,
            outputPath: s.output
          })),
          message: `آزمایش اولیه پایپلاین موفقیت‌آمیز بود: ${scenes.length} صحنه آماده تولید هستند (بدون مصرف کردیت).`
        }, null, 2));
      } else {
        const results = [];
        for (let i = 0; i < scenes.length; i++) {
          const sc = scenes[i];
          const outPath = path.resolve(projectPath, sc.output || `output_${i}.mp4`);
          await configureSettings(page, {
            media: sc.media || 'video',
            aspect: sc.aspect || '9:16',
            model: sc.model
          });
          const res = await generateAndDownload(page, {
            prompt: sc.prompt,
            outputPath: outPath,
            media: sc.media || 'video',
            timeoutSec: parseInt(options.timeout || '240', 10)
          });
          results.push({ name: sc.name, ...res });
          if (!res.ok) {
            console.log(JSON.stringify({ ok: false, sceneIndex: i, results }, null, 2));
            break;
          }
        }
        if (results.every(r => r.ok)) {
          console.log(JSON.stringify({ ok: true, completedScenes: results.length, results }, null, 2));
        }
      }
    } else if (action === 'generate-video') {
      const projectPath = options.project;
      const planNumber = parseInt(options.plan || '1', 10);
      const prompt = options.prompt;
      const aspect = options.aspect || '9:16';
      const model = options.model || 'Veo 3.1';
      const timeout = parseInt(options.timeout || '240', 10);

      const planMap = {
        1: "Plan_01_Hook_Avatar",
        2: "Plan_02_Problem",
        3: "Plan_03_Company_Intro",
        4: "Plan_04_Requirements",
        5: "Plan_05_Benefits",
        6: "Plan_06_CTA_Avatar",
        7: "Plan_07_Outro"
      };
      const folderName = planMap[planNumber] || `Plan_0${planNumber}`;
      const outputPath = path.join(projectPath, '03_Raw_DropZone', folderName, `V_Plan_0${planNumber}.mp4`);

      await configureSettings(page, { media: 'video', aspect, model });
      const result = await generateAndDownload(page, {
        prompt,
        outputPath,
        media: 'video',
        timeoutSec: timeout
      });

      console.log(JSON.stringify(result, null, 2));
    }

    await browser.close();
  } catch (err) {
    console.error(JSON.stringify({
      ok: false,
      error: err.name || 'ERROR',
      message: err.message
    }));
    process.exit(1);
  }
}

main();
