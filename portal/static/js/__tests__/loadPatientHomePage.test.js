import "expect-puppeteer";
import puppeteer from "puppeteer";
import {testPatientEmail, testPatientPassword, homePageURL} from "./consts";

//test variables
// const homePageURL = "https://eproms-test.cirg.washington.edu";
// const testPatientEmail = atob("YWNoZW4yNDAxK3Rlc3QxMTFAZ21haWwuY29t");
// const testPatientPassword = atob("RWxlYW5vcjI=");

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
    await page.goto(homePageURL);
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
    await page.locator("#email").fill(testPatientEmail);
    await page.keyboard.down("Tab");
    await page.keyboard.up("Tab");
    await page.locator("#password").fill(testPatientPassword);
  });

  it("should click submit button", async () => {
    await page.locator("#btnLogin").click();
  });

  it("should have main body on page", async () => {
    await page.waitForSelector(".portal-main");
    await expect(page).toMatchElement(".portal-main");
  });
});
