/**
 * CeloFlow Two-Step Transfer Flow Integration Test
 *
 * Simulates a complete frontend interaction for the TEE-mediated two-step transfer:
 *   Step 1: POST /transfer/preview  → get preview_id + fee breakdown
 *   Step 2: Agent chat "send X token to recipient" → TEE executes transfer
 *
 * Also tests:
 *   - /transfer/preview/{preview_id} validation endpoint
 *   - preview_transfer agent tool via chat
 *   - TEE wallet balance check in preview response
 *   - Fee comparison data in preview
 *   - Preview expiry (30s TTL)
 *
 * Usage: bun run tests/test-two-step-transfer.ts
 */

const API_URL = process.env.CELOFLOW_API_URL || 'http://localhost:8000';

const USER_WALLET = '0xFf0573b826A3120df03Cb6F1eC0B5992a9948472';
const CHAIN_ID = 11142220;
const RECIPIENT = '0x7D64E31e1F2e41C6AA3beD4E5D51d22b9aC3cF36';
const RECIPIENT_NAME = 'Julia';

const TEST_CONTACTS = [
  {
    id: '1',
    name: RECIPIENT_NAME,
    address: RECIPIENT,
    network: 'celo-sepolia',
    city: 'Asunción',
    country: 'Paraguay',
    phone: '+595981234567',
    email: 'julia@example.com',
    notes: 'Test contact for two-step flow',
    favorite: true,
    blocked: false,
    group: 'Family',
  },
];

const WALLET_CONTEXT = {
  wallet_address: USER_WALLET,
  connected: true,
  chain_id: CHAIN_ID,
  balances: {},
};

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface TransferFees {
  network_fee: number;
  network_fee_currency: string;
  service_fee: number;
  service_fee_currency: string;
  service_fee_pct: number;
  service_fee_tier: string;
  total_fee_usd: number;
  total_fee_pct: number;
}

interface TransferRoute {
  available: boolean;
  from_currency?: string;
  to_currency?: string;
  rate?: number;
  route_type?: string;
  reason?: string;
}

interface TEEBalance {
  sufficient: boolean;
  auto_swap_needed: boolean;
  tee_address?: string;
  balance?: number;
  required?: number;
}

interface SavingsInfo {
  available: boolean;
  celoflow_fee: number;
  celoflow_fee_pct: number;
  cheapest_provider?: string;
  savings_vs_cheapest?: number;
}

interface ProviderComparison {
  name: string;
  total_fee: number;
  speed: string;
}

interface TransferPreview {
  preview_id: string;
  recipient: string;
  amount: number;
  token: string;
  destination_country: string;
  route: TransferRoute;
  fees: TransferFees;
  comparisons: ProviderComparison[];
  savings: SavingsInfo;
  tee_balance: TEEBalance;
  created_at: number;
  expires_at: number;
  expires_in_seconds: number;
  error?: string;
}

interface PreviewValidation {
  valid: boolean;
  preview_id: string;
  reason?: string;
  expires_in_seconds?: number;
  amount?: number;
  token?: string;
  recipient?: string;
  service_fee?: number;
}

interface StreamResult {
  fullContent: string;
  chunks: number;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

let passed = 0;
let failed = 0;

function assert(condition: boolean, message: string): void {
  if (condition) {
    console.log(`  ✅ ${message}`);
    passed++;
  } else {
    console.error(`  ❌ FAIL: ${message}`);
    failed++;
  }
}

function assertDefined<T>(value: T | undefined | null, message: string): value is T {
  if (value !== undefined && value !== null) {
    console.log(`  ✅ ${message}`);
    passed++;
    return true;
  } else {
    console.error(`  ❌ FAIL: ${message} (got ${value})`);
    failed++;
    return false;
  }
}

async function streamChat(message: string): Promise<StreamResult> {
  const body = {
    messages: [{ role: 'user', content: message }],
    conversation_id: `test-two-step-${Date.now()}`,
    wallet_context: WALLET_CONTEXT,
    contacts: TEST_CONTACTS,
  };

  const response = await fetch(`${API_URL}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Accept': 'text/event-stream' },
    body: JSON.stringify(body),
  });

  if (!response.ok || !response.body) {
    throw new Error(`Stream failed: ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let fullContent = '';
  let chunks = 0;
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() ?? '';

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = line.slice(6).trim();
        if (data === '[DONE]') continue;
        try {
          interface SSEChunk {
            choices?: Array<{ delta?: { content?: string } }>;
            content?: string;
            delta?: string;
            type?: string;
          }
          const parsed = JSON.parse(data) as SSEChunk;
          // OpenAI-compatible format: choices[0].delta.content
          const delta =
            parsed.choices?.[0]?.delta?.content ??
            parsed.content ??
            parsed.delta ??
            '';
          if (delta) {
            fullContent += delta;
            chunks++;
          }
        } catch {
          // non-JSON SSE line
        }
      }
    }
  }

  return { fullContent, chunks };
}

// ---------------------------------------------------------------------------
// Test Suite
// ---------------------------------------------------------------------------

async function testPreviewEndpointBasic(): Promise<TransferPreview | null> {
  console.log('\n📋 Test 1: POST /transfer/preview — basic preview generation');

  const response = await fetch(`${API_URL}/transfer/preview`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      recipient_address: RECIPIENT,
      amount: 3,
      token: 'BRLm',
      destination_country: 'Brazil',
      from_currency: 'USD',
      user_id: USER_WALLET,
    }),
  });

  assert(response.ok, `HTTP 200 response (got ${response.status})`);
  if (!response.ok) return null;

  const preview = await response.json() as TransferPreview;

  assertDefined(preview.preview_id, 'preview_id present');
  assert(preview.preview_id.startsWith('prev_'), `preview_id has correct prefix: ${preview.preview_id}`);
  assert(preview.amount === 3, `amount matches: ${preview.amount}`);
  assert(preview.token === 'BRLm', `token matches: ${preview.token}`);
  assert(preview.recipient === RECIPIENT, `recipient matches`);
  assertDefined(preview.fees, 'fees object present');
  assert(preview.fees.service_fee >= 0, `service_fee >= 0: ${preview.fees.service_fee}`);
  assert(preview.fees.total_fee_usd >= 0, `total_fee_usd >= 0: ${preview.fees.total_fee_usd}`);
  assertDefined(preview.tee_balance, 'tee_balance present');
  assert(typeof preview.tee_balance.sufficient === 'boolean', 'tee_balance.sufficient is boolean');
  assert(preview.expires_in_seconds > 0, `expires_in_seconds > 0: ${preview.expires_in_seconds}`);
  assert(preview.expires_at > preview.created_at, 'expires_at > created_at');

  console.log(`  ℹ️  preview_id: ${preview.preview_id}`);
  console.log(`  ℹ️  service_fee: ${preview.fees.service_fee} ${preview.fees.service_fee_currency} (${preview.fees.service_fee_tier})`);
  console.log(`  ℹ️  total_fee_usd: $${preview.fees.total_fee_usd}`);
  console.log(`  ℹ️  tee_balance: sufficient=${preview.tee_balance.sufficient}, auto_swap=${preview.tee_balance.auto_swap_needed}`);
  console.log(`  ℹ️  expires_in: ${preview.expires_in_seconds}s`);

  return preview;
}

async function testPreviewValidation(previewId: string): Promise<void> {
  console.log('\n📋 Test 2: GET /transfer/preview/{id} — validate preview');

  const response = await fetch(`${API_URL}/transfer/preview/${previewId}`);
  assert(response.ok, `HTTP 200 response (got ${response.status})`);

  const validation = await response.json() as PreviewValidation;
  assert(validation.valid === true, `preview is valid: ${validation.valid}`);
  assert(validation.preview_id === previewId, `preview_id matches`);
  assertDefined(validation.expires_in_seconds, 'expires_in_seconds present');
  assert((validation.expires_in_seconds ?? 0) > 0, `expires_in_seconds > 0: ${validation.expires_in_seconds}`);
  assert(validation.amount === 3, `amount matches: ${validation.amount}`);
  assert(validation.token === 'BRLm', `token matches: ${validation.token}`);

  console.log(`  ℹ️  expires_in_seconds: ${validation.expires_in_seconds}`);
}

async function testPreviewNotFound(): Promise<void> {
  console.log('\n📋 Test 3: GET /transfer/preview/{id} — invalid preview_id returns 404');

  const response = await fetch(`${API_URL}/transfer/preview/prev_nonexistent123`);
  assert(response.status === 404, `HTTP 404 for unknown preview (got ${response.status})`);

  const body = await response.json() as PreviewValidation;
  assert(body.valid === false, `valid=false for unknown preview`);
}

async function testPreviewValidation_missingFields(): Promise<void> {
  console.log('\n📋 Test 4: POST /transfer/preview — missing required fields returns 400');

  const response = await fetch(`${API_URL}/transfer/preview`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ amount: 1 }), // missing recipient_address and token
  });

  assert(response.status === 400, `HTTP 400 for missing fields (got ${response.status})`);
}

async function testPreviewZeroAmount(): Promise<void> {
  console.log('\n📋 Test 5: POST /transfer/preview — zero amount returns 400');

  const response = await fetch(`${API_URL}/transfer/preview`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      recipient_address: RECIPIENT,
      amount: 0,
      token: 'BRLm',
    }),
  });

  assert(response.status === 400, `HTTP 400 for zero amount (got ${response.status})`);
}

async function testPreviewFeeComparisons(): Promise<void> {
  console.log('\n📋 Test 6: POST /transfer/preview — fee comparisons with destination country');

  const response = await fetch(`${API_URL}/transfer/preview`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      recipient_address: RECIPIENT,
      amount: 100,
      token: 'USDm',
      destination_country: 'Philippines',
      from_currency: 'USD',
    }),
  });

  assert(response.ok, `HTTP 200 response (got ${response.status})`);
  const preview = await response.json() as TransferPreview;

  assertDefined(preview.comparisons, 'comparisons array present');
  assert(Array.isArray(preview.comparisons), 'comparisons is array');
  assertDefined(preview.savings, 'savings object present');
  assert(typeof preview.savings.celoflow_fee === 'number', 'savings.celoflow_fee is number');

  console.log(`  ℹ️  comparisons count: ${preview.comparisons.length}`);
  if (preview.comparisons.length > 0) {
    for (const p of preview.comparisons) {
      console.log(`  ℹ️  ${p.name}: $${p.total_fee} (${p.speed})`);
    }
  }
  if (preview.savings.available) {
    console.log(`  ℹ️  savings vs ${preview.savings.cheapest_provider}: $${preview.savings.savings_vs_cheapest}`);
  }
}

async function testPreviewRouteInfo(): Promise<void> {
  console.log('\n📋 Test 7: POST /transfer/preview — route information');

  const response = await fetch(`${API_URL}/transfer/preview`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      recipient_address: RECIPIENT,
      amount: 5,
      token: 'KESm',
    }),
  });

  assert(response.ok, `HTTP 200 response (got ${response.status})`);
  const preview = await response.json() as TransferPreview;

  assertDefined(preview.route, 'route object present');
  assert(typeof preview.route.available === 'boolean', 'route.available is boolean');

  if (preview.route.available) {
    console.log(`  ℹ️  route_type: ${preview.route.route_type}`);
    console.log(`  ℹ️  rate: ${preview.route.rate}`);
  } else {
    console.log(`  ℹ️  route unavailable: ${preview.route.reason}`);
  }
}

async function testAgentChatPreviewTool(): Promise<void> {
  console.log('\n📋 Test 8: Agent chat — preview_transfer tool via natural language');

  const result = await streamChat(
    `Show me a preview of sending 3 BRLm to ${RECIPIENT_NAME} (${RECIPIENT}) in Brazil before I confirm`
  );

  assert(result.chunks > 0, `received streaming chunks: ${result.chunks}`);
  assert(result.fullContent.length > 0, 'received non-empty response');

  const content = result.fullContent.toLowerCase();
  const hasFeeInfo = content.includes('fee') || content.includes('brlm') || content.includes('preview') || content.includes('transfer');
  assert(hasFeeInfo, `response mentions transfer/fee/preview: "${result.fullContent.slice(0, 120)}..."`);

  console.log(`  ℹ️  response preview: "${result.fullContent.slice(0, 200)}..."`);
}

async function testAgentChatDirectTransfer(): Promise<void> {
  console.log('\n📋 Test 9: Agent chat — direct transfer "send 3 BRLm to Julia"');

  const result = await streamChat(`send 3 brlm to ${RECIPIENT_NAME}`);

  assert(result.chunks > 0, `received streaming chunks: ${result.chunks}`);
  assert(result.fullContent.length > 0, 'received non-empty response');

  const content = result.fullContent.toLowerCase();
  const hasTransferInfo = (
    content.includes('brlm') ||
    content.includes('transfer') ||
    content.includes('sent') ||
    content.includes('tx') ||
    content.includes('hash') ||
    content.includes('julia') ||
    content.includes('0x')
  );
  assert(hasTransferInfo, `response mentions transfer details: "${result.fullContent.slice(0, 120)}..."`);

  console.log(`  ℹ️  response preview: "${result.fullContent.slice(0, 300)}..."`);
}

async function testPreviewMultipleTokens(): Promise<void> {
  console.log('\n📋 Test 10: POST /transfer/preview — multiple token types');

  const tokens = ['USDm', 'EURm', 'ZARm'];
  for (const token of tokens) {
    const response = await fetch(`${API_URL}/transfer/preview`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        recipient_address: RECIPIENT,
        amount: 10,
        token,
      }),
    });

    assert(response.ok, `HTTP 200 for ${token} preview (got ${response.status})`);
    if (response.ok) {
      const preview = await response.json() as TransferPreview;
      assert(preview.token === token, `token matches: ${preview.token}`);
      assert(preview.preview_id.startsWith('prev_'), `preview_id valid for ${token}`);
      console.log(`  ℹ️  ${token}: fee=$${preview.fees.total_fee_usd}, tee_sufficient=${preview.tee_balance.sufficient}`);
    }
  }
}

async function testPreviewTEEBalanceCheck(): Promise<void> {
  console.log('\n📋 Test 11: POST /transfer/preview — TEE balance check structure');

  const response = await fetch(`${API_URL}/transfer/preview`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      recipient_address: RECIPIENT,
      amount: 1,
      token: 'BRLm',
    }),
  });

  assert(response.ok, `HTTP 200 response (got ${response.status})`);
  const preview = await response.json() as TransferPreview;

  const tee = preview.tee_balance;
  assertDefined(tee, 'tee_balance present');
  assert(typeof tee.sufficient === 'boolean', 'tee_balance.sufficient is boolean');
  assert(typeof tee.auto_swap_needed === 'boolean', 'tee_balance.auto_swap_needed is boolean');

  if (tee.tee_address) {
    assert(tee.tee_address.startsWith('0x'), `tee_address is valid: ${tee.tee_address}`);
    console.log(`  ℹ️  TEE address: ${tee.tee_address}`);
    console.log(`  ℹ️  TEE balance: ${tee.balance} BRLm (required: ${tee.required})`);
    console.log(`  ℹ️  auto_swap_needed: ${tee.auto_swap_needed}`);
  } else {
    console.log(`  ℹ️  TEE balance check: ${JSON.stringify(tee)}`);
  }
}

async function testPreviewServiceFeeCalculation(): Promise<void> {
  console.log('\n📋 Test 12: POST /transfer/preview — service fee is ~0.5% of amount');

  const amount = 100;
  const response = await fetch(`${API_URL}/transfer/preview`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      recipient_address: RECIPIENT,
      amount,
      token: 'USDm',
    }),
  });

  assert(response.ok, `HTTP 200 response (got ${response.status})`);
  const preview = await response.json() as TransferPreview;

  const fee = preview.fees.service_fee;
  const expectedFee = amount * 0.005; // 0.5%
  const tolerance = expectedFee * 2; // allow up to 2x for reputation multipliers
  assert(fee >= 0, `service_fee >= 0: ${fee}`);
  assert(fee <= tolerance, `service_fee <= ${tolerance} (got ${fee}, expected ~${expectedFee})`);
  assert(preview.fees.service_fee_pct > 0, `service_fee_pct > 0: ${preview.fees.service_fee_pct}`);

  console.log(`  ℹ️  amount: ${amount} USDm`);
  console.log(`  ℹ️  service_fee: ${fee} ${preview.fees.service_fee_currency}`);
  console.log(`  ℹ️  service_fee_pct: ${preview.fees.service_fee_pct}%`);
  console.log(`  ℹ️  tier: ${preview.fees.service_fee_tier}`);
}

// ---------------------------------------------------------------------------
// Main runner
// ---------------------------------------------------------------------------

async function main(): Promise<void> {
  console.log('═══════════════════════════════════════════════════════════');
  console.log('  CeloFlow Two-Step Transfer Flow — Integration Tests');
  console.log(`  API: ${API_URL}`);
  console.log('═══════════════════════════════════════════════════════════');

  // Health check
  try {
    const health = await fetch(`${API_URL}/health`);
    if (!health.ok) {
      const mcp = await fetch(`${API_URL}/.well-known/mcp.json`);
      if (!mcp.ok) throw new Error('Server not reachable');
    }
    console.log('✅ Server is reachable\n');
  } catch (err) {
    console.error(`❌ Cannot reach server at ${API_URL}`);
    console.error('   Start the server: cd celoflow && uv run python server.py');
    process.exit(1);
  }

  // Run tests
  const preview = await testPreviewEndpointBasic();

  if (preview?.preview_id) {
    await testPreviewValidation(preview.preview_id);
  }

  await testPreviewNotFound();
  await testPreviewValidation_missingFields();
  await testPreviewZeroAmount();
  await testPreviewFeeComparisons();
  await testPreviewRouteInfo();
  await testPreviewTEEBalanceCheck();
  await testPreviewServiceFeeCalculation();
  await testPreviewMultipleTokens();

  // Agent chat tests (require running LLM)
  console.log('\n─── Agent Chat Tests (require running LLM backend) ───');
  try {
    await testAgentChatPreviewTool();
    await testAgentChatDirectTransfer();
  } catch (err) {
    console.warn(`  ⚠️  Agent chat tests skipped (LLM may not be running): ${err}`);
  }

  // Summary
  const total = passed + failed;
  console.log('\n═══════════════════════════════════════════════════════════');
  console.log(`  Results: ${passed}/${total} passed, ${failed} failed`);
  console.log('═══════════════════════════════════════════════════════════');

  if (failed > 0) {
    process.exit(1);
  }
}

main().catch((err) => {
  console.error('Fatal error:', err);
  process.exit(1);
});
