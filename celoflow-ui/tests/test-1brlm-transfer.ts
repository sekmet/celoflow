/**
 * Focused test: Send 1 BRLm to Charles
 * This is the exact scenario that was failing with "reverted on-chain"
 * 
 * Usage: bun run tests/test-1brlm-transfer.ts
 */

const API_URL = process.env.CELOFLOW_API_URL || 'http://localhost:8000';
const USER_WALLET = '0xFf0573b826A3120df03Cb6F1eC0B5992a9948472';
const CHAIN_ID = 11142220;
const RECIPIENT = '0x7D64E31e1F2e41C6AA3beD4E5D51d22b9aC3cF36';

const CONTACTS = [
  {
    id: '1',
    name: 'Charles',
    address: RECIPIENT,
    network: 'celo-sepolia',
    city: 'São Paulo',
    country: 'Brazil',
    phone: '+5511999999999',
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

interface StreamResult {
  fullContent: string;
  chunks: string[];
}

async function streamChat(message: string, conversationId?: string): Promise<StreamResult> {
  const body = {
    messages: [{ role: 'user', content: message }],
    conversation_id: conversationId || `test-1brlm-${Date.now()}`,
    wallet_context: WALLET_CONTEXT,
    contacts: CONTACTS,
  };

  const response = await fetch(`${API_URL}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify(body),
  });

  if (!response.ok) throw new Error(`Stream error ${response.status}: ${await response.text()}`);

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
          if (delta) { fullContent += delta; chunks.push(delta); }
        } catch { /* ignore */ }
      }
    }
  }
  reader.releaseLock();
  return { fullContent, chunks };
}

async function main(): Promise<void> {
  console.log('═══════════════════════════════════════════════════');
  console.log('  Test: Send 1 BRLm to Charles');
  console.log(`  API: ${API_URL}`);
  console.log('═══════════════════════════════════════════════════\n');

  // First update wallet context
  const ctxRes = await fetch(`${API_URL}/wallet/context`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ address: USER_WALLET, connected: true, chainId: CHAIN_ID }),
  });
  const ctx = await ctxRes.json() as Record<string, unknown>;
  if (ctx.success) {
    const balances = (ctx.context as Record<string, unknown>)?.balances as Record<string, string>;
    if (balances) WALLET_CONTEXT.balances = balances;
    console.log('✅ Wallet context updated\n');
  }

  console.log('📤 Sending: "Send 1 BRLm to Charles"...\n');
  const startTime = Date.now();
  const result = await streamChat('Send 1 BRLm to Charles');
  const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);

  console.log(`⏱️  Response time: ${elapsed}s`);
  console.log(`📝 Response (${result.fullContent.length} chars):\n`);
  console.log(result.fullContent);

  // Analyze result
  const content = result.fullContent.toLowerCase();
  const hasSuccess = content.includes('success') || content.includes('complete') || content.includes('sent') || content.includes('✅');
  const hasTxHash = content.includes('celoscan.io/tx/') || content.includes('tx hash') || content.includes('transaction hash');
  const hasError = content.includes('reverted') || content.includes('insufficient') || content.includes('failed');
  const hasAutoSwap = content.includes('swap') || content.includes('converted') || content.includes('auto');

  console.log('\n═══════════════════════════════════════════════════');
  console.log('  Analysis:');
  console.log(`  ${hasSuccess ? '✅' : '❌'} Transfer success indicator`);
  console.log(`  ${hasTxHash ? '✅' : '❌'} Transaction hash present`);
  console.log(`  ${!hasError ? '✅' : '❌'} No error indicators`);
  if (hasAutoSwap) console.log('  ℹ️  Auto-swap was triggered');
  console.log('═══════════════════════════════════════════════════');

  process.exit(hasSuccess && !hasError ? 0 : 1);
}

main().catch(e => { console.error('Fatal:', e); process.exit(1); });
