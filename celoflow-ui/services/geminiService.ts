import { GoogleGenAI, Type } from "@google/genai";
import { TransactionIntent } from "../types";
import { getExchangeRate } from "./currencyService";

// Initialize Gemini
// NOTE: In a real production app, ensure this is handled securely.
const ai = new GoogleGenAI({ apiKey: process.env.API_KEY });

const SYSTEM_INSTRUCTION = `
You are CeloFlow, an AI remittance agent on the Celo blockchain.
Your goal is to parse user messages to detect if they want to send money.
If the user wants to send money, extract the amount, currency (default to cUSD if ambiguous), and recipient.
Check if the user specified a frequency for recurring payments (e.g., "monthly", "weekly", "every friday"). If not specified, default to "one-time".

You are multilingual. You must understand and respond fluently in the following languages:
- English
- Spanish
- Portuguese
- French
- German
- Japanese

Always respond in the same language the user initiated the conversation in.

The currencies supported are: cUSD, EUR, PHP, MXN, KES, BRL, JPY.

If a transaction is detected, you MUST return a specific JSON structure.
If no transaction is detected, return null for the transaction fields and a friendly text response.

Assume the base currency the user sends is usually cUSD or USDC unless specified.
`;

export const parseUserMessage = async (message: string): Promise<{ text: string; transaction?: TransactionIntent; error?: string }> => {
  try {
    const responseSchema = {
      type: Type.OBJECT,
      properties: {
        isTransaction: { type: Type.BOOLEAN },
        responseText: { type: Type.STRING },
        amount: { type: Type.NUMBER, nullable: true },
        currency: { type: Type.STRING, nullable: true },
        recipient: { type: Type.STRING, nullable: true },
        targetCurrency: { type: Type.STRING, nullable: true },
        frequency: { type: Type.STRING, nullable: true, description: "one-time, weekly, monthly, etc." }
      }
    };

    const response = await ai.models.generateContent({
      model: "gemini-3-flash-preview",
      contents: message,
      config: {
        systemInstruction: SYSTEM_INSTRUCTION,
        responseMimeType: "application/json",
        responseSchema: responseSchema,
      },
    });

    const parsed = JSON.parse(response.text || "{}");

    if (parsed.isTransaction && parsed.amount) {
        const sourceCurrency = parsed.currency || 'cUSD';
        
        // Inference Logic for Target Currency
        let targetCurrency = parsed.targetCurrency;
        if (!targetCurrency) {
            const lowerMsg = message.toLowerCase();
            if (lowerMsg.includes('philippines') || lowerMsg.includes('peso')) targetCurrency = 'PHP';
            else if (lowerMsg.includes('mexico')) targetCurrency = 'MXN';
            else if (lowerMsg.includes('kenya') || lowerMsg.includes('m-pesa')) targetCurrency = 'KES';
            else if (lowerMsg.includes('brazil') || lowerMsg.includes('real')) targetCurrency = 'BRL';
            else if (lowerMsg.includes('germany') || lowerMsg.includes('france') || lowerMsg.includes('euro')) targetCurrency = 'EUR';
            else if (lowerMsg.includes('japan') || lowerMsg.includes('yen')) targetCurrency = 'JPY';
            else targetCurrency = 'cUSD'; 
        }

        // Fetch Real Rate
        let rateData;
        try {
            rateData = await getExchangeRate(sourceCurrency, targetCurrency);
        } catch (e) {
            console.error("Rate fetch error", e);
            return {
                text: "I understood your request, but I'm having trouble fetching the latest exchange rates. Please try again in a moment.",
                error: "RATE_FETCH_ERROR"
            };
        }

        const converted = parsed.amount * rateData.rate;
        
        // Calculate Fees
        const networkFee = 0.001; // Base Celo gas fee (very low)
        const mentoFee = parsed.amount * 0.002; // 0.2% Mento swap fee
        const securityFee = 0.01; // TEE operation fee
        const totalFees = networkFee + mentoFee + securityFee;

        const bankFee = 15 + (parsed.amount * 0.03); // Mock traditional bank fee (flat + %)
        const savings = bankFee - totalFees;

        return {
            text: parsed.responseText,
            transaction: {
                amount: parsed.amount,
                currency: sourceCurrency,
                recipient: parsed.recipient || "Unknown Recipient",
                recipientCurrency: targetCurrency,
                convertedAmount: parseFloat(converted.toFixed(2)),
                fees: parseFloat(totalFees.toFixed(4)),
                feeBreakdown: {
                    mentoFee: parseFloat(mentoFee.toFixed(4)),
                    networkFee: parseFloat(networkFee.toFixed(4)),
                    securityFee: parseFloat(securityFee.toFixed(4))
                },
                savings: parseFloat(savings.toFixed(2)),
                route: [sourceCurrency, 'Uniswap Pool', 'Mento Protocol', targetCurrency],
                frequency: parsed.frequency || 'one-time',
                exchangeRate: parseFloat(rateData.rate.toFixed(4)),
                isRealTimeRate: rateData.isRealTime,
                startDate: new Date().toISOString().split('T')[0]
            }
        };
    }

    return {
        text: parsed.responseText || "I didn't catch that. Could you rephrase?",
    };

  } catch (error: any) {
    console.error("Gemini/Service Error:", error);
    
    // Detailed Error Handling
    const errorMessage = error.message || '';
    
    if (errorMessage.includes('API key')) {
        return { text: "System Error: Invalid API Key configuration. Please contact support." };
    }
    
    if (errorMessage.includes('429') || errorMessage.includes('Resource has been exhausted')) {
        return { text: "I'm receiving too many requests right now. Please wait a minute and try again." };
    }

    if (errorMessage.includes('400') || errorMessage.includes('InvalidArgument')) {
        return { text: "I couldn't quite understand that request structure. Could you try rephrasing it simply? (e.g., 'Send 10 USD to John')" };
    }

    if (errorMessage.includes('503') || errorMessage.includes('Service Unavailable')) {
        return { text: "My brain is a bit overloaded at the moment. Please give me a few seconds to cool down." };
    }

    if (errorMessage.includes('fetch') || errorMessage.includes('network')) {
        return { text: "I'm having trouble connecting to the network. Please check your internet connection." };
    }
    
    return {
        text: "I encountered an unexpected issue. Please try again later."
    };
  }
};