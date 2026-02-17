// Fallback rates in case API fails
const FALLBACK_RATES: Record<string, number> = {
    'USD': 1,
    'cUSD': 1,
    'USDC': 1,
    'EUR': 0.92,
    'PHP': 56.40,
    'MXN': 17.05,
    'KES': 131.50,
    'BRL': 4.95,
    'JPY': 150.25
};

export const getExchangeRate = async (from: string, to: string): Promise<{ rate: number, isRealTime: boolean }> => {
    try {
        // Map Celo stablecoins to fiat counterparts for this API
        const queryFrom = (from === 'cUSD' || from === 'USDC') ? 'USD' : from;
        const queryTo = (to === 'cUSD' || to === 'USDC') ? 'USD' : to;

        // Using a free exchange rate API that supports CORS
        const response = await fetch('https://open.er-api.com/v6/latest/USD');
        
        if (!response.ok) {
            throw new Error(`API Error: ${response.statusText}`);
        }
        
        const data = await response.json();
        
        // Get rates relative to USD base
        const rateFromUSD = data.rates[queryFrom] || FALLBACK_RATES[queryFrom] || 1;
        const rateToUSD = data.rates[queryTo] || FALLBACK_RATES[queryTo] || 1;

        // Calculate cross rate: (1 USD / rateFromUSD) * rateToUSD
        // e.g. 1 EUR = (1 / 0.92) * 1.0 = 1.08 USD. Then * rateToUSD.
        // Formula: (1 / rateFrom) * rateTo
        
        const rate = (1 / rateFromUSD) * rateToUSD;
        
        // Check if we actually found the rate in the API data, otherwise it's effectively a fallback logic usage if specific keys missing
        const isRealTime = !!(data.rates[queryFrom] && data.rates[queryTo]);

        return { rate, isRealTime };

    } catch (error) {
        console.warn('Currency service unavailable, using fallback rates.', error);
        const f = FALLBACK_RATES[from === 'cUSD' ? 'USD' : from] || 1;
        const t = FALLBACK_RATES[to === 'cUSD' ? 'USD' : to] || 1;
        return { rate: (1 / f) * t, isRealTime: false };
    }
};