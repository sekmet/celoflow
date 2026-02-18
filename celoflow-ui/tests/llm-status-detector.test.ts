import { describe, test, expect } from 'bun:test';
import { LLMStatusDetector } from '../lib/llm-status-detector';
import { DEFAULT_STATUS_CONFIG } from '../types/llm-status';

describe('LLMStatusDetector', () => {
  let detector: LLMStatusDetector;

  beforeEach(() => {
    detector = new LLMStatusDetector();
  });

  test('should start with idle status', () => {
    detector.start();
    const status = detector.analyzeContent('');
    expect(status.status).toBe('idle');
  });

  test('should detect thinking status from keywords', () => {
    detector.start();
    const status = detector.analyzeContent('Let me think about this transfer');
    expect(status.status).toBe('thinking');
  });

  test('should detect routing status from keywords', () => {
    detector.start();
    const status = detector.analyzeContent('I need to route this through the best exchange');
    expect(status.status).toBe('routing');
  });

  test('should detect checking status from keywords', () => {
    detector.start();
    const status = detector.analyzeContent('Let me check your balance first');
    expect(status.status).toBe('checking');
  });

  test('should detect finding status from keywords', () => {
    detector.start();
    const status = detector.analyzeContent('Finding the best rates for you');
    expect(status.status).toBe('finding');
  });

  test('should detect loading status from keywords', () => {
    detector.start();
    const status = detector.analyzeContent('Almost done with the calculation');
    expect(status.status).toBe('loading');
  });

  test('should detect transfer operation', () => {
    detector.start();
    const status = detector.analyzeContent('I will send the transfer');
    expect(status.operation).toBe('transfer');
  });

  test('should detect swap operation', () => {
    detector.start();
    const status = detector.analyzeContent('Let me swap these tokens');
    expect(status.operation).toBe('swap');
  });

  test('should use timing heuristics when no content patterns match', () => {
    detector.start();
    
    // Simulate time passing
    const originalNow = Date.now;
    const mockTime = originalNow() + 3000; // 3 seconds later
    Date.now = () => mockTime;
    
    const status = detector.analyzeContent('Some generic text');
    expect(status.status).toBe('checking'); // Should be in checking phase by 3 seconds
    
    // Restore original Date.now
    Date.now = originalNow;
  });

  test('should maintain status history', () => {
    detector.start();
    
    detector.analyzeContent('Let me think');
    detector.analyzeContent('I will route this');
    detector.analyzeContent('Checking your balance');
    
    const history = detector.getHistory();
    expect(history.length).toBeGreaterThan(0);
    expect(history[0].status).toBe('thinking');
  });

  test('should reset properly', () => {
    detector.start();
    detector.analyzeContent('Let me think');
    
    detector.reset();
    
    const status = detector.getCurrentStatus();
    expect(status).toBe('idle');
    
    const history = detector.getHistory();
    expect(history.length).toBe(0);
  });
});
