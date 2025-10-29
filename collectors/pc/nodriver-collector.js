/**
 * PC Nodriver TLS+Cookie Collector
 * - nodriver로 Chrome 실행
 * - Coupang 접속하여 TLS 핑거프린트 + 쿠키 수집
 * - DB에 직접 업로드
 */

const nodriver = require('nodriver');
const TlsExtractor = require('./tls-extractor');
const DbManager = require('../../db/db-manager');
const logger = require('../../utils/logger');

class NodriverCollector {
  constructor(options = {}) {
    this.chromeVersion = options.chromeVersion || null;
    this.chromePath = options.chromePath || null;
    this.headless = options.headless !== false;
    this.dbManager = new DbManager();
  }

  /**
   * TLS + 쿠키 수집 메인 함수
   */
  async collect() {
    let browser = null;
    let page = null;

    try {
      logger.info('[NodriverCollector] Starting collection...');
      logger.info(`Chrome Version: ${this.chromeVersion || 'Latest'}`);

      // 1. Browser 실행
      browser = await this.launchBrowser();
      page = await browser.get('about:blank');

      // 2. Coupang 메인 페이지 접속
      logger.info('[NodriverCollector] Navigating to Coupang...');
      await page.get('https://www.coupang.com/');
      await page.sleep(3000); // 페이지 로드 대기

      // 3. TLS 핑거프린트 수집 (CDP)
      logger.info('[NodriverCollector] Extracting TLS fingerprint...');
      const tlsExtractor = new TlsExtractor(page);
      const tlsData = await tlsExtractor.extract();

      // 4. 쿠키 수집
      logger.info('[NodriverCollector] Collecting cookies...');
      const cookies = await page.send('Network.getAllCookies');

      // 5. User-Agent 및 헤더 수집
      const userAgent = await page.evaluate('navigator.userAgent');
      const secChUa = await page.evaluate('navigator.userAgentData?.brands?.map(b => `"${b.brand}";v="${b.version}"`).join(", ")');

      // 6. DB에 저장
      logger.info('[NodriverCollector] Saving to database...');
      const profileData = {
        platform: 'pc',
        device_name: `Chrome ${this.chromeVersion || 'Latest'}`,
        chrome_version: this.chromeVersion,
        ...tlsData,
        user_agent: userAgent,
        sec_ch_ua: secChUa,
        collection_method: 'nodriver'
      };

      const profileId = await this.dbManager.saveTlsProfile(profileData);
      logger.info(`[NodriverCollector] TLS Profile saved: ID ${profileId}`);

      const cookieData = {
        profile_id: profileId,
        cookie_json: cookies.cookies,
        cookie_count: cookies.cookies.length,
        has_akamai: this.hasAkamaiCookies(cookies.cookies),
        has_pcid: this.hasPcidCookie(cookies.cookies)
      };

      const cookieId = await this.dbManager.saveCookies(cookieData);
      logger.info(`[NodriverCollector] Cookies saved: ID ${cookieId}, Count: ${cookies.cookies.length}`);

      return {
        success: true,
        profile_id: profileId,
        cookie_id: cookieId,
        tls_data: tlsData,
        cookie_count: cookies.cookies.length
      };

    } catch (error) {
      logger.error(`[NodriverCollector] Collection failed: ${error.message}`);
      throw error;

    } finally {
      if (browser) {
        logger.info('[NodriverCollector] Closing browser...');
        await browser.stop();
      }
    }
  }

  /**
   * nodriver Browser 실행
   */
  async launchBrowser() {
    const config = {
      headless: this.headless
    };

    // Chrome 경로 지정 (특정 버전 사용 시)
    if (this.chromePath) {
      config.browser_executable_path = this.chromePath;
    }

    const browser = await nodriver.start(config);
    logger.info('[NodriverCollector] Browser launched successfully');
    return browser;
  }

  /**
   * Akamai 쿠키 존재 여부 확인
   */
  hasAkamaiCookies(cookies) {
    const akamaiNames = ['ak_bmsc', 'bm_sz', 'bm_mi', 'bm_sv'];
    return cookies.some(cookie => akamaiNames.includes(cookie.name));
  }

  /**
   * PCID 쿠키 존재 여부 확인
   */
  hasPcidCookie(cookies) {
    return cookies.some(cookie => cookie.name === 'PCID');
  }
}

module.exports = NodriverCollector;
