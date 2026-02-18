"""Chain configuration for the CeloFlow Remittance Agent."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


# ERC-20 token addresses on Celo
CELO_TOKEN_ADDRESSES: Dict[str, str] = {
    "CELO": "0x471EcE3750Da237f93B8E339c536989b8978a438",
    "cUSD": "0x765DE816845861e75A25fCA122bb6898B8B1282a",
    "cEUR": "0xD8763CBa276a3738E6DE85b4b3bF5FDed6D6cA73",
    "cREAL": "0xe8537a3d056DA446677B9E9d6c5dB704EaAb4787",
    "cKES": "0x456a3D042C0DbD3db53D5489e98dFb038553B0d0",
    "cCOP": "0x8A567e2aE79CA692Bd748aB832081C45B8581B8B",
    "USDC": "0xcebA9300f2b948710d2653dD7B07f33A8B32118C",
    "USDT": "0x48065fbBE25f71C9282ddf5e1cD6D6A887483D5e",
    "eXOF": "0x73F93dcc49cB8A239e2032663e9475dd5ef29A08",
    "PUSO": "0x105d4A9306D2E55a71d2Eb95B81553AE1dC20d7B",
}

CURRENCY_DECIMALS: Dict[str, int] = {
    "CELO": 18,
    "cUSD": 18,
    "cEUR": 18,
    "cREAL": 18,
    "cKES": 18,
    "cCOP": 18,
    "USDC": 6,
    "USDT": 6,
    "eXOF": 18,
    "PUSO": 18,
}


@dataclass
class ChainConfig:
    """Configuration for a blockchain network."""

    chain_id: int
    rpc_url: str
    name: str
    explorer_url: str = ""
    is_testnet: bool = False
    token_addresses: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def celo_mainnet(cls, rpc_url: str = "https://forno.celo.org") -> ChainConfig:
        return cls(
            chain_id=42220,
            rpc_url=rpc_url,
            name="Celo Mainnet",
            explorer_url="https://celoscan.io",
            token_addresses=CELO_TOKEN_ADDRESSES,
        )

    @classmethod
    def celo_sepolia(cls, rpc_url: str = "https://celo-sepolia.g.alchemy.com/v2/E1tpzIwNYKbEADvBUW4fnAq13UCobt_3") -> ChainConfig:
        return cls(
            chain_id=11142220,
            rpc_url=rpc_url,
            name="Celo Sepolia",
            explorer_url="https://sepolia.celoscan.io",
            is_testnet=True,
            token_addresses={
                "CELO": "0x471EcE3750Da237f93B8E339c536989b8978a438",
                "cUSD": "0xdE9e4C3ce781b4bA68120d6261cbad65ce0aB00b",  # Using USDm as cUSD alias for Mento v2
                "USDm": "0xdE9e4C3ce781b4bA68120d6261cbad65ce0aB00b",
                "EURm": "0xA99dC247d6b7B2E3ab48a1fEE101b83cD6aCd82a",
                "BRLm": "0x2294298942fdc79417DE9E0D740A4957E0e7783a",
                "KESm": "0xC7e4635651E3e3Af82b61d3E23c159438daE3BbF",
                "XOFm": "0x5505b70207aE3B826c1A7607F19F3Bf73444A082",
                "PHPm": "0x0352976d940a2C3FBa0C3623198947Ee1d17869E",
                "COPm": "0x5F8d55c3627d2dc0a2B4afa798f877242F382F67",
                "GBPm": "0x85F5181Abdbf0e1814Fc4358582Ae07b8eBA3aF3",
                "CADm": "0xF151c9a13b78C84f93f50B8b3bC689fedc134F60",
                "AUDm": "0x5873Faeb42F3563dcD77F0fbbdA818E6d6DA3139",
                "ZARm": "0x10CCfB235b0E1Ed394bACE4560C3ed016697687e",
                "GHSm": "0x5e94B8C872bD47BC4255E60ECBF44D5E66e7401C",
                "NGNm": "0x3d5ae86F34E2a82771496D140daFAEf3789dF888",
                "JPYm": "0x85Bee67D435A39f7467a8a9DE34a5B73D25Df426",
                "CHFm": "0x284E9b7B623eAE866914b7FA0eB720C2Bb3C2980",
                "USDT": "0xd077A400968890Eacc75cdc901F0356c943e4fDb", 
                "axlUSDC": "0x6285De9DA7C1d329C0451628638908915002d9d1",
            },
        )

    @classmethod
    def anvil_local(cls, rpc_url: str = "http://127.0.0.1:8545") -> ChainConfig:
        return cls(
            chain_id=31337,
            rpc_url=rpc_url,
            name="Anvil Local",
            is_testnet=True,
            token_addresses=CELO_TOKEN_ADDRESSES,
        )
