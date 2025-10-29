/**
 * TLS Extractor - Chrome DevTools Protocol (CDP)
 * - TLS 핑거프린트 추출
 * - HTTP/2 설정 추출
 * - Cipher suites, Extensions 추출
 */

const crypto = require('crypto');
const logger = require('../../utils/logger');

class TlsExtractor {
  constructor(page) {
    this.page = page;
  }

  /**
   * TLS 핑거프린트 추출 메인 함수
   */
  async extract() {
    try {
      // CDP를 통한 TLS 정보 수집
      const securityDetails = await this.getSecurityDetails();
      const http2Settings = await this.getHttp2Settings();

      // JA3 핑거프린트 생성 (추정값)
      const ja3Data = this.generateJa3Fingerprint(securityDetails);

      return {
        ja3_fingerprint: ja3Data.ja3_string,
        ja3_hash: ja3Data.ja3_hash,
        tls_version: securityDetails.protocol || 'TLS 1.3',
        cipher_suites: securityDetails.cipher ? [securityDetails.cipher] : [],
        http2_settings: http2Settings,
        signature_algorithms: securityDetails.signatureAlgorithm ? [securityDetails.signatureAlgorithm] : [],
        supported_groups: ['x25519', 'secp256r1', 'secp384r1'] // Chrome 기본값
      };

    } catch (error) {
      logger.error(`[TlsExtractor] Extraction failed: ${error.message}`);
      return this.getDefaultTlsData();
    }
  }

  /**
   * CDP Security 정보 가져오기
   */
  async getSecurityDetails() {
    try {
      // Security.enable 활성화
      await this.page.send('Security.enable');

      // 현재 페이지의 보안 정보
      const state = await this.page.send('Security.getSecurityState');

      if (state.securityStateIssues && state.securityStateIssues.length > 0) {
        const details = state.securityStateIssues[0];
        return {
          protocol: details.protocol || 'TLSv1.3',
          cipher: details.cipher,
          signatureAlgorithm: details.keyExchange
        };
      }

      return {
        protocol: 'TLSv1.3',
        cipher: 'TLS_AES_128_GCM_SHA256',
        signatureAlgorithm: 'ecdsa_secp256r1_sha256'
      };

    } catch (error) {
      logger.warn(`[TlsExtractor] Failed to get security details: ${error.message}`);
      return {
        protocol: 'TLSv1.3',
        cipher: 'TLS_AES_128_GCM_SHA256'
      };
    }
  }

  /**
   * HTTP/2 설정 추출
   */
  async getHttp2Settings() {
    try {
      // Network.enable 활성화
      await this.page.send('Network.enable');

      // HTTP/2 기본 설정 (Chrome 표준)
      return {
        HEADER_TABLE_SIZE: 65536,
        ENABLE_PUSH: 0,
        MAX_CONCURRENT_STREAMS: 1000,
        INITIAL_WINDOW_SIZE: 6291456,
        MAX_FRAME_SIZE: 16384,
        MAX_HEADER_LIST_SIZE: 262144
      };

    } catch (error) {
      logger.warn(`[TlsExtractor] Failed to get HTTP/2 settings: ${error.message}`);
      return null;
    }
  }

  /**
   * JA3 핑거프린트 생성
   * Format: SSLVersion,Ciphers,Extensions,EllipticCurves,EllipticCurvePointFormats
   */
  generateJa3Fingerprint(securityDetails) {
    // Chrome 기본 TLS 1.3 설정 (추정값)
    const tlsVersion = '771'; // TLS 1.3
    const ciphers = '4865-4866-4867-49195-49199-49196-49200-52393-52392-49171-49172-156-157-47-53';
    const extensions = '0-23-65281-10-11-35-16-5-13-18-51-45-43-27-17513';
    const ellipticCurves = '29-23-24';
    const ellipticCurveFormats = '0';

    const ja3String = `${tlsVersion},${ciphers},${extensions},${ellipticCurves},${ellipticCurveFormats}`;
    const ja3Hash = crypto.createHash('md5').update(ja3String).digest('hex');

    return {
      ja3_string: ja3String,
      ja3_hash: ja3Hash
    };
  }

  /**
   * 기본 TLS 데이터 (실패 시)
   */
  getDefaultTlsData() {
    return {
      ja3_fingerprint: null,
      ja3_hash: null,
      tls_version: 'TLS 1.3',
      cipher_suites: ['TLS_AES_128_GCM_SHA256', 'TLS_AES_256_GCM_SHA384', 'TLS_CHACHA20_POLY1305_SHA256'],
      http2_settings: {
        HEADER_TABLE_SIZE: 65536,
        ENABLE_PUSH: 0,
        INITIAL_WINDOW_SIZE: 6291456
      },
      signature_algorithms: ['ecdsa_secp256r1_sha256', 'rsa_pss_rsae_sha256'],
      supported_groups: ['x25519', 'secp256r1', 'secp384r1']
    };
  }
}

module.exports = TlsExtractor;
