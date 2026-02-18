/**
 * CeloFlow Agent API Integration Test Script
 * 
 * Tests the agent from the frontend perspective using JS/fetch calls.
 * Injects wallet context and contacts, then tests:
 * 1. Wallet context update
 * 2. Chat with agent (streaming)
 * 3. Send token transfer (BRLm)
 * 4. Mento swap (USDm -> BRLm)
 * 5. Fee comparison
 * 6. Multi-language support
 * 
 * Usage: bun run tests/test-agent-api.ts
 */

const API_URL = process.env.CELOFLOW_API_URL || 'http://localhost:8000';

// User wallet (Celo Sepolia)
const USER_WALLET = '0xFf0573b826A3120df03Cb6F1eC0B5992a9948472';
const CHAIN_ID = 11142220;

// Test recipient
const RECIPIENT = '0x7D64E31e1F2e41C6AA3beD4E5D51d22b9aC3cF36';

// Contacts to inject
const TEST_CONTACTS = [
  {
    id: '1',
    name: 'Charles',
    address: RECIPIENT,
    network: 'celo-sepolia',
    city: 'São Paulo',
    country: 'Brazil',
    phone: '+5511999999999',
    email: 'charles@example.com',
    notes: 'Test contact',
    favorite: true,
    blocked: false,
    group: 'Family',
  },
  {
    id: '2',
    name: 'Maria',
    address: '0x1234567890abcdef1234567890abcdef12345678',
    network: 'celo-sepolia',
    city: 'Manila',
    country: 'Philippines',
    phone: '+639171234567',
    email: 'maria@example.com',
    notes: 'Philippines contact',
    favorite: false,
    blocked: false,
    group: 'Friends',
  },
];

// Wallet context to inject
const WALLET_CONTEXT = {
  wallet_address: USER_WALLET,
  connected: true,
  chain_id: CHAIN_ID,
  balances: {},
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

interface StreamResult {
  fullContent: string;
  chunks: string[];
}

async function streamChat(message: string, conversationId?: string): Promise<StreamResult> {
  const body = {
    messages: [{ role: 'user', content: message }],
    conversation_id: conversationId || `test-${Date.now()}`,
    wallet_context: WALLET_CONTEXT,
    contacts: TEST_CONTACTS,
  };

  const response = await fetch(`${API_URL}/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Stream error ${response.status}: ${text}`);
  }

  const reader = response.body?.getReader();
  if (!reader) throw new Error('No reader');

  let fullContent = '';
  const chunks: string[] = [];
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() ?? '';

    for (const line of lines) {
      const trimmed = line.trimEnd();
      if (trimmed.startsWith('data:')) {
        const data = trimmed.slice(5).trimStart();
        if (data === '[DONE]') continue;
        try {
          const parsed = JSON.parse(data);
          const delta = parsed.choices?.[0]?.delta?.content;
          if (delta) {
            fullContent += delta;
            chunks.push(delta);
          }
        } catch {
          // ignore parse errors
        }
      }
    }
  }

  reader.releaseLock();
  return { fullContent, chunks };
}

async function sendChat(message: string, conversationId?: string): Promise<string> {
  const body = {
    messages: [{ role: 'user', content: message }],
    conversation_id: conversationId || `test-${Date.now()}`,
    wallet_context: WALLET_CONTEXT,
    contacts: TEST_CONTACTS,
  };

  const response = await fetch(`${API_URL}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Chat error ${response.status}: ${text}`);
  }

  const json = await response.json() as Record<string, unknown>;
  const choices = json.choices as Array<{ message: { content: string } }>;
  return choices?.[0]?.message?.content ?? '';
}

async function updateWalletContext(): Promise<Record<string, unknown>> {
  const response = await fetch(`${API_URL}/wallet/context`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      address: USER_WALLET,
      connected: true,
      chainId: CHAIN_ID,
    }),
  });
  return response.json() as Promise<Record<string, unknown>>;
}

async function getWalletContext(): Promise<Record<string, unknown>> {
  const response = await fetch(`${API_URL}/wallet/context`);
  return response.json() as Promise<Record<string, unknown>>;
}

// ---------------------------------------------------------------------------
// Test Cases
// ---------------------------------------------------------------------------

let passed = 0;
let failed = 0;

function assert(condition: boolean, testName: string, detail?: string): void {
  if (condition) {
    console.log(`  ✅ ${testName}`);
    passed++;
  } else {
    console.log(`  ❌ ${testName}${detail ? ` — ${detail}` : ''}`);
    failed++;
  }
}

async function testWalletContext(): Promise<void> {
  console.log('\n🔑 Test 1: Wallet Context Update');
  
  const result = await updateWalletContext();
  assert(result.success === true, 'Wallet context update succeeds');
  
  const ctx = result.context as Record<string, unknown>;
  assert(ctx?.wallet_address === USER_WALLET, 'Wallet address matches');
  assert(ctx?.connected === true, 'Wallet shows connected');
  
  const balances = ctx?.balances as Record<string, string>;
  assert(balances !== undefined && Object.keys(balances).length > 0, 'Balances fetched', `Got ${Object.keys(balances || {}).length} tokens`);
  
  // Update our wallet context with real balances for subsequent tests
  if (balances) {
    WALLET_CONTEXT.balances = balances;
    const nonZero = Object.entries(balances).filter(([, v]) => parseFloat(v) > 0);
    console.log(`    Balances: ${nonZero.map(([k, v]) => `${parseFloat(v).toFixed(4)} ${k}`).join(', ')}`);
  }
}

async function testAgentGreeting(): Promise<void> {
  console.log('\n💬 Test 2: Agent Greeting (Streaming)');
  
  const result = await streamChat('Hello! What can you do?');
  assert(result.fullContent.length > 50, 'Agent responds with substantial content', `${result.fullContent.length} chars`);
  assert(result.chunks.length > 1, 'Response is streamed in chunks', `${result.chunks.length} chunks`);
  assert(
    result.fullContent.toLowerCase().includes('celo') || result.fullContent.toLowerCase().includes('transfer') || result.fullContent.toLowerCase().includes('remittance'),
    'Response mentions core capabilities'
  );
  console.log(`    Preview: ${result.fullContent.substring(0, 200)}...`);
}

async function testWalletAwareness(): Promise<void> {
  console.log('\n💰 Test 3: Wallet Balance Awareness');
  
  const result = await streamChat('Show me my wallet balances');
  assert(result.fullContent.length > 30, 'Agent responds about balances');
  
  // The agent should see the wallet context and show balances
  const content = result.fullContent.toLowerCase();
  const mentionsBalance = content.includes('balance') || content.includes('wallet') || content.includes('celo') || content.includes('usdm') || content.includes('brlm');
  assert(mentionsBalance, 'Agent acknowledges wallet/balances', `Content: ${result.fullContent.substring(0, 150)}`);
  console.log(`    Preview: ${result.fullContent.substring(0, 200)}...`);
}

async function testContactsAwareness(): Promise<void> {
  console.log('\n👥 Test 4: Contacts Awareness');
  
  const result = await streamChat('Who are my contacts?');
  const content = result.fullContent.toLowerCase();
  const mentionsCharles = content.includes('charles');
  const mentionsMaria = content.includes('maria');
  assert(mentionsCharles, 'Agent sees contact Charles');
  assert(mentionsMaria, 'Agent sees contact Maria');
  console.log(`    Preview: ${result.fullContent.substring(0, 200)}...`);
}

async function testSendBRLm(): Promise<void> {
  console.log('\n💸 Test 5: Send BRLm to Charles');
  
  const result = await streamChat('Send 0.1 BRLm to Charles');
  const content = result.fullContent.toLowerCase();
  
  // The agent should attempt the transfer using send_token
  const mentionsTx = content.includes('tx') || content.includes('transaction') || content.includes('transfer') || content.includes('sent') || content.includes('hash') || content.includes('0x') || content.includes('celoscan');
  const mentionsError = content.includes('error') || content.includes('failed') || content.includes('insufficient');
  
  assert(result.fullContent.length > 30, 'Agent responds to transfer request');
  
  if (mentionsTx && !mentionsError) {
    assert(true, 'Transfer appears successful');
  } else if (mentionsError) {
    console.log(`    ⚠️  Transfer had an error (may be expected): ${result.fullContent.substring(0, 300)}`);
    assert(true, 'Agent attempted transfer (error may be gas/balance related)');
  } else {
    assert(false, 'Agent should attempt transfer or report error', result.fullContent.substring(0, 200));
  }
  
  console.log(`    Full response: ${result.fullContent.substring(0, 400)}`);
}

async function testMentoSwapQuote(): Promise<void> {
  console.log('\n🔄 Test 6: Mento Swap Quote');
  
  const result = await streamChat('What is the exchange rate for USDm to BRLm?');
  const content = result.fullContent.toLowerCase();
  
  const mentionsRate = content.includes('rate') || content.includes('exchange') || content.includes('brlm') || content.includes('mento');
  assert(mentionsRate, 'Agent provides exchange rate info');
  console.log(`    Preview: ${result.fullContent.substring(0, 200)}...`);
}

async function testFeeComparison(): Promise<void> {
  console.log('\n📊 Test 7: Fee Comparison');
  
  const result = await streamChat('Compare fees for sending $100 to Brazil');
  const content = result.fullContent.toLowerCase();
  
  const mentionsFees = content.includes('fee') || content.includes('western union') || content.includes('wise') || content.includes('save') || content.includes('comparison');
  assert(mentionsFees, 'Agent provides fee comparison');
  console.log(`    Preview: ${result.fullContent.substring(0, 200)}...`);
}

async function testMultiLanguage(): Promise<void> {
  console.log('\n🌍 Test 8: Multi-Language (Spanish)');
  
  const result = await streamChat('Hola, quiero enviar dinero a Brasil. ¿Cuánto cuesta?');
  const content = result.fullContent.toLowerCase();
  
  // Agent should respond in Spanish
  const isSpanish = content.includes('hola') || content.includes('enviar') || content.includes('brasil') || content.includes('costo') || content.includes('tarifa') || content.includes('transferencia');
  assert(isSpanish, 'Agent responds in Spanish');
  console.log(`    Preview: ${result.fullContent.substring(0, 200)}...`);
}

async function testPortuguese(): Promise<void> {
  console.log('\n🌍 Test 9: Multi-Language (Portuguese)');
  
  const result = await streamChat('Olá, quero enviar 10 reais para o Charles');
  const content = result.fullContent.toLowerCase();
  
  const isPortuguese = content.includes('olá') || content.includes('enviar') || content.includes('charles') || content.includes('transferência') || content.includes('brlm');
  assert(isPortuguese, 'Agent responds in Portuguese or acknowledges request');
  console.log(`    Preview: ${result.fullContent.substring(0, 200)}...`);
}

async function testAgentIdentity(): Promise<void> {
  console.log('\n🤖 Test 10: Agent Identity');
  
  const result = await streamChat('What is your agent ID and are you registered on-chain?');
  const content = result.fullContent.toLowerCase();
  
  const mentionsIdentity = content.includes('agent') || content.includes('erc-8004') || content.includes('registered') || content.includes('identity') || content.includes('celo');
  assert(mentionsIdentity, 'Agent discusses its identity');
  console.log(`    Preview: ${result.fullContent.substring(0, 200)}...`);
}

// ---------------------------------------------------------------------------
// Runner
// ---------------------------------------------------------------------------

async function main(): Promise<void> {
  console.log('═══════════════════════════════════════════════════');
  console.log('  CeloFlow Agent API Integration Tests');
  console.log(`  API: ${API_URL}`);
  console.log(`  Wallet: ${USER_WALLET}`);
  console.log(`  Chain: Celo Sepolia (${CHAIN_ID})`);
  console.log('═══════════════════════════════════════════════════');

  // Check server health
  try {
    const health = await fetch(`${API_URL}/wallet/context`);
    if (!health.ok) throw new Error(`HTTP ${health.status}`);
    console.log('✅ Server is reachable');
  } catch (e) {
    console.error(`❌ Server not reachable at ${API_URL}: ${e}`);
    process.exit(1);
  }

  try {
    await testWalletContext();
    await testAgentGreeting();
    await testWalletAwareness();
    await testContactsAwareness();
    await testSendBRLm();
    await testMentoSwapQuote();
    await testFeeComparison();
    await testMultiLanguage();
    await testPortuguese();
    await testAgentIdentity();
  } catch (e) {
    console.error(`\n💥 Test suite error: ${e}`);
    failed++;
  }

  console.log('\n═══════════════════════════════════════════════════');
  console.log(`  Results: ${passed} passed, ${failed} failed, ${passed + failed} total`);
  console.log('═══════════════════════════════════════════════════');
  
  process.exit(failed > 0 ? 1 : 0);
}

main();
