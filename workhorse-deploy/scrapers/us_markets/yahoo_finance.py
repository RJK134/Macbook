"""Yahoo Finance market data via yfinance.

Free, no API key. Provides stock quotes, earnings, fundamentals
for a watchlist of companies relevant to EdTech + wealth advisory.

Requires: pip install yfinance
"""

from __future__ import annotations

from ..common.logging_setup import get_logger
from ..common.usb import write_raw_json

LOGGER = get_logger("us_markets.yahoo_finance")

# Watchlist: EdTech public companies + major market ETFs for advisory context
WATCHLIST = {
    # EdTech
    "COUR": "Coursera",
    "DUOL": "Duolingo",
    "CHGG": "Chegg",
    "INST": "Instructure (Thoma Bravo)",
    "LOPE": "Grand Canyon Education",
    "STRA": "Strategic Education (Strayer)",
    "LRN": "Stride Inc (K12)",
    "UDMY": "Udemy",
    # Major indices / ETFs for wealth advisory
    "SPY": "S&P 500 ETF",
    "QQQ": "Nasdaq 100 ETF",
    "IWM": "Russell 2000 ETF",
    "TLT": "20+ Year Treasury Bond ETF",
    "GLD": "Gold ETF",
    "VGK": "Vanguard FTSE Europe ETF",
    "EWL": "iShares MSCI Switzerland ETF",
}


def scrape() -> list[dict]:
    try:
        import yfinance as yf
    except ImportError:
        LOGGER.warning("yfinance not installed — run: pip install yfinance")
        return []

    out: list[dict] = []
    tickers = list(WATCHLIST.keys())
    LOGGER.info("Yahoo Finance: downloading %d tickers", len(tickers))
    try:
        data = yf.download(tickers, period="5d", group_by="ticker", progress=False)
        for symbol, label in WATCHLIST.items():
            try:
                if len(tickers) > 1:
                    df = data[symbol] if symbol in data.columns.get_level_values(0) else None
                else:
                    df = data
                if df is None or df.empty:
                    continue
                latest = df.iloc[-1]
                prev = df.iloc[-2] if len(df) > 1 else latest
                close = float(latest.get("Close", 0))
                prev_close = float(prev.get("Close", 0))
                change_pct = ((close - prev_close) / prev_close * 100) if prev_close else 0
                out.append({
                    "signal_type": "market-data",
                    "title": f"{label} ({symbol}): ${close:.2f} ({change_pct:+.1f}%)",
                    "company": label,
                    "source": "yahoo_finance",
                    "url": f"https://finance.yahoo.com/quote/{symbol}",
                    "region": "US",
                    "country": "US",
                    "description": f"{label} last close ${close:.2f}, change {change_pct:+.1f}%",
                    "raw_data": {
                        "symbol": symbol,
                        "close": close,
                        "change_pct": round(change_pct, 2),
                        "volume": int(latest.get("Volume", 0)),
                    },
                })
            except Exception as exc:
                LOGGER.warning("%s parse failed: %s", symbol, exc)
    except Exception as exc:
        LOGGER.warning("yfinance download failed: %s", exc)
    write_raw_json("us_markets", "yahoo-finance", {"total": len(out)})
    LOGGER.info("Yahoo Finance: %d tickers processed", len(out))
    return out
