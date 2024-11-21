import "expect-puppeteer";
import puppeteer from "puppeteer";

//TODO get these from environment variables?
// const homepage = "https://eproms-test.cirg.washington.edu";
// const testEmail = atob("YWNoZW4yNDAxK3Rlc3QxMTFAZ21haWwuY29t");
// const testPassword = atob("RWxlYW5vcjI=");
const testEmail = process.env.testEmail;
const testPassword = process.env.testPassword;
const homepage = process.env.homePageURL;

describe("Login in to Patient Home Page", () => {
  const TIMEOUT_DURATION = 30000;
  jest.setTimeout(TIMEOUT_DURATION);
  let browser, page;
  beforeAll(async () => {
    await jestPuppeteer.resetBrowser();
    await jestPuppeteer.resetPage();
    browser = await puppeteer.launch();
    page = await browser.newPage();
    const timeout = TIMEOUT_DURATION;
    page.setDefaultTimeout(timeout);
    await page.goto(homepage);
    await page.setViewport({
      width: 1477,
      height: 890,
    });
  });

  afterAll(async () => {
    browser.close();
  });

  it('should display "Log in" text on page', async () => {
    await expect(page).toMatchTextContent(/Log in/);
  });

  it("should fill in login form", async () => {
    await page.locator("#email").click({
      offset: {
        x: 108.5,
        y: 17.21875,
      },
    });
    await page.locator("#email").fill(testEmail);
    await page.keyboard.down("Tab");
    await page.keyboard.up("Tab");
    await page.locator("#password").fill(testPassword);
  });

  it("should click submit button", async () => {
    await page.locator("#btnLogin").click();
  });

  it("should have main body on page", async () => {
    await page.waitForSelector(".portal-main");
    await expect(page).toMatchElement(".portal-main");
  });
});
