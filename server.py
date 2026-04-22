from mcp.server.fastmcp import FastMCP
from entsoe import EntsoePandasClient
import pandas as pd
import os
from datetime import datetime, timedelta
import pytz

# Initialize the MCP server
mcp = FastMCP("ENTSO-E Electricity Prices")

# Initialize the ENTSO-E client using the API token from environment variable
def get_client():
    token = os.environ.get("ENTSOE_API_TOKEN")
    if not token:
        raise ValueError("ENTSOE_API_TOKEN environment variable not set")
    return EntsoePandasClient(api_key=token)

# Map of country codes to ENTSO-E bidding zone codes
COUNTRY_TO_ZONE = {
    "DE": "DE_LU",   # Germany-Luxembourg
    "FR": "FR",       # France
    "GR": "GR",       # Greece
    "IT": "IT_NORD",  # Italy North
    "ES": "ES",       # Spain
    "NL": "NL",       # Netherlands
    "BE": "BE",       # Belgium
    "AT": "AT",       # Austria
    "PL": "PL",       # Poland
    "PT": "PT",       # Portugal
    "DK": "DK_1",     # Denmark West
    "SE": "SE_3",     # Sweden Central
    "NO": "NO_2",     # Norway South
    "FI": "FI",       # Finland
    "CH": "CH",       # Switzerland
    "CZ": "CZ",       # Czech Republic
    "HU": "HU",       # Hungary
    "RO": "RO",       # Romania
    "BG": "BG",       # Bulgaria
    "HR": "HR",       # Croatia
}


@mcp.tool()
def get_day_ahead_prices(country_code: str, date: str) -> str:
    """
    Retrieves hourly day-ahead electricity prices in €/MWh for a specific European country and date.
    
    Use this tool when the user asks about electricity prices for a specific day, tomorrow's prices,
    yesterday's prices, or any named date. Day-ahead prices are the market prices set the previous day
    for each hour of the target date.
    
    Args:
        country_code: Two-letter ISO country code. Supported: DE (Germany), FR (France), GR (Greece),
                      IT (Italy), ES (Spain), NL (Netherlands), BE (Belgium), AT (Austria), PL (Poland),
                      PT (Portugal), DK (Denmark), SE (Sweden), NO (Norway), FI (Finland), CH (Switzerland),
                      CZ (Czech Republic), HU (Hungary), RO (Romania), BG (Bulgaria), HR (Croatia).
        date: The target date in YYYY-MM-DD format (e.g. "2025-04-18"). Use today's date for current 
              day prices, tomorrow's date for next-day prices.
    
    Returns:
        A formatted string listing each hour (00:00–23:00) and its price in €/MWh, plus daily 
        min/max/average summary.
    """
    try:
        client = get_client()
        zone = COUNTRY_TO_ZONE.get(country_code.upper())
        if not zone:
            return f"Unsupported country code: {country_code}. Supported codes: {', '.join(COUNTRY_TO_ZONE.keys())}"
        
        # Parse the date and create UTC timestamps for the full day
        target_date = datetime.strptime(date, "%Y-%m-%d")
        start = pd.Timestamp(target_date, tz="UTC")
        end = start + timedelta(days=1)
        
        prices = client.query_day_ahead_prices(zone, start=start, end=end)
        
        if prices is None or prices.empty:
            return f"No day-ahead price data available for {country_code} on {date}."
        
        # Format the output
        lines = [f"Day-ahead electricity prices for {country_code} on {date}:\n"]
        for timestamp, price in prices.items():
            hour = timestamp.strftime("%H:%M")
            lines.append(f"  {hour}: {price:.2f} €/MWh")
        
        avg = prices.mean()
        min_price = prices.min()
        max_price = prices.max()
        min_hour = prices.idxmin().strftime("%H:%M")
        max_hour = prices.idxmax().strftime("%H:%M")
        
        lines.append(f"\nSummary:")
        lines.append(f"  Average: {avg:.2f} €/MWh")
        lines.append(f"  Cheapest: {min_price:.2f} €/MWh at {min_hour}")
        lines.append(f"  Most expensive: {max_price:.2f} €/MWh at {max_hour}")
        
        return "\n".join(lines)
    
    except Exception as e:
        return f"Error fetching prices for {country_code} on {date}: {str(e)}"


@mcp.tool()
def get_current_price(country_code: str) -> str:
    """
    Returns the electricity price for the current hour in a given European country, in €/MWh.
    
    Use this tool when the user asks "what is the current electricity price in [country]?",
    "how much does electricity cost right now in [country]?", or any question about the 
    present-moment price. This tool automatically determines the current hour and fetches 
    the corresponding day-ahead price.
    
    Args:
        country_code: Two-letter ISO country code (e.g. "DE" for Germany, "GR" for Greece, 
                      "FR" for France). See get_day_ahead_prices for full list.
    
    Returns:
        The current hour's electricity price in €/MWh, plus context about whether it is 
        cheap or expensive relative to today's average.
    """
    try:
        client = get_client()
        zone = COUNTRY_TO_ZONE.get(country_code.upper())
        if not zone:
            return f"Unsupported country code: {country_code}."
        
        now_utc = pd.Timestamp.now(tz="UTC")
        start = now_utc.floor("D")
        end = start + timedelta(days=1)
        
        prices = client.query_day_ahead_prices(zone, start=start, end=end)
        
        if prices is None or prices.empty:
            return f"No price data available for {country_code} right now."
        
        # Find the current hour's price
        current_hour = now_utc.floor("H")
        
        # Get the closest available price
        closest_idx = prices.index.asof(current_hour)
        if pd.isna(closest_idx):
            current_price = prices.iloc[0]
            hour_str = prices.index[0].strftime("%H:%M UTC")
        else:
            current_price = prices[closest_idx]
            hour_str = closest_idx.strftime("%H:%M UTC")
        
        avg = prices.mean()
        comparison = "above" if current_price > avg else "below"
        diff_pct = abs((current_price - avg) / avg * 100)
        
        return (
            f"Current electricity price in {country_code} ({hour_str}): {current_price:.2f} €/MWh\n"
            f"Today's average: {avg:.2f} €/MWh\n"
            f"Current price is {diff_pct:.1f}% {comparison} today's average."
        )
    
    except Exception as e:
        return f"Error fetching current price for {country_code}: {str(e)}"


@mcp.tool()
def get_cheapest_window(country_code: str, duration_hours: int, date: str) -> str:
    """
    Finds the cheapest consecutive time window of a given duration for a European country on a specific date.
    
    Use this tool when the user asks questions like:
    - "When is the best time to charge my EV tonight in Germany?"
    - "What's the cheapest 4-hour window to run my factory in France tomorrow?"
    - "When should I run energy-intensive processes in Spain today?"
    - "Find the cheapest 2-hour slot for Greece on 2025-04-20"
    
    This is ideal for optimising electricity costs for time-shiftable loads like EV charging,
    industrial processes, heat pumps, data centre batch jobs, etc.
    
    Args:
        country_code: Two-letter ISO country code (e.g. "DE", "GR", "FR").
        duration_hours: Length of the desired window in hours (e.g. 2 for a 2-hour window, 
                        4 for four consecutive hours). Must be between 1 and 12.
        date: Target date in YYYY-MM-DD format.
    
    Returns:
        The start and end time of the cheapest window, the average price during that window,
        the total cost per MWh, and how much cheaper it is versus the day's average price.
    """
    try:
        client = get_client()
        zone = COUNTRY_TO_ZONE.get(country_code.upper())
        if not zone:
            return f"Unsupported country code: {country_code}."
        
        if not (1 <= duration_hours <= 12):
            return "duration_hours must be between 1 and 12."
        
        target_date = datetime.strptime(date, "%Y-%m-%d")
        start = pd.Timestamp(target_date, tz="UTC")
        end = start + timedelta(days=1)
        
        prices = client.query_day_ahead_prices(zone, start=start, end=end)
        
        if prices is None or prices.empty:
            return f"No price data available for {country_code} on {date}."
        
        if len(prices) < duration_hours:
            return f"Not enough hourly data points to find a {duration_hours}-hour window."
        
        # Sliding window to find the cheapest consecutive block
        prices_list = list(prices.items())
        best_avg = float("inf")
        best_start_idx = 0
        
        for i in range(len(prices_list) - duration_hours + 1):
            window_prices = [prices_list[i + j][1] for j in range(duration_hours)]
            window_avg = sum(window_prices) / duration_hours
            if window_avg < best_avg:
                best_avg = window_avg
                best_start_idx = i
        
        best_start_time = prices_list[best_start_idx][0]
        best_end_time = prices_list[best_start_idx + duration_hours - 1][0] + timedelta(hours=1)
        day_avg = prices.mean()
        savings_pct = (day_avg - best_avg) / day_avg * 100
        
        return (
            f"Cheapest {duration_hours}-hour window for {country_code} on {date}:\n"
            f"  Start: {best_start_time.strftime('%H:%M UTC')}\n"
            f"  End:   {best_end_time.strftime('%H:%M UTC')}\n"
            f"  Average price: {best_avg:.2f} €/MWh\n"
            f"  Day's average: {day_avg:.2f} €/MWh\n"
            f"  Savings vs average: {savings_pct:.1f}% cheaper\n"
            f"  Tip: Start your process at {best_start_time.strftime('%H:%M UTC')} for maximum savings."
        )
    
    except Exception as e:
        return f"Error finding cheapest window for {country_code}: {str(e)}"
@mcp.tool()
def get_generation_mix(country_code: str) -> str:
    """
    Returns the current electricity generation breakdown by source for a European country.
    
    Use this tool when the user asks questions like:
    - "How much of Germany's electricity is coming from solar right now?"
    - "What is the current energy mix in France?"
    - "How green is the electricity in Spain today?"
    - "What percentage of Greek electricity is renewable right now?"
    - "Is the UK running on wind power today?"
    
    This tool is ideal for ESG/sustainability questions, carbon footprint queries,
    and understanding how clean the current electricity supply is in a given country.
    
    Args:
        country_code: Two-letter ISO country code (e.g. "DE", "GR", "FR"). 
                      See get_day_ahead_prices for full list of supported countries.
    
    Returns:
        A breakdown of electricity generation by source (solar, wind, gas, nuclear, hydro, etc.)
        in MW and as a percentage of total generation, plus a renewable energy percentage summary.
    """
    try:
        client = get_client()
        zone = COUNTRY_TO_ZONE.get(country_code.upper())
        if not zone:
            return f"Unsupported country code: {country_code}."
        
        now_utc = pd.Timestamp.now(tz="UTC")
        start = now_utc.floor("D")
        end = now_utc + timedelta(hours=1)
        
        generation = client.query_generation(zone, start=start, end=end, psr_type=None)
        
        if generation is None or generation.empty:
            return f"No generation data available for {country_code} right now."
        
        # Get the most recent row
        latest = generation.iloc[-1]
        total = latest.sum()
        
        if total == 0:
            return f"No generation data available for {country_code} at this time."
        
        # Sort by contribution descending
        latest_sorted = latest.sort_values(ascending=False)
        
        lines = [f"Current electricity generation mix for {country_code}:\n"]
        
        renewable_sources = ["Solar", "Wind Onshore", "Wind Offshore", "Hydro Run-of-river", 
                           "Hydro Water Reservoir", "Geothermal", "Biomass", "Other renewable"]
        renewable_mw = 0
        
        for source, mw in latest_sorted.items():
            if mw > 0:
                pct = (mw / total) * 100
                lines.append(f"  {source}: {mw:.0f} MW ({pct:.1f}%)")
                if any(r.lower() in str(source).lower() for r in renewable_sources):
                    renewable_mw += mw
        
        renewable_pct = (renewable_mw / total) * 100
        lines.append(f"\nTotal generation: {total:.0f} MW")
        lines.append(f"Renewable share: {renewable_pct:.1f}%")
        lines.append(f"Fossil fuel share: {100 - renewable_pct:.1f}%")
        
        return "\n".join(lines)
    
    except Exception as e:
        return f"Error fetching generation mix for {country_code}: {str(e)}"


@mcp.tool()
def compare_prices(country_codes: str, date: str) -> str:
    """
    Compares day-ahead electricity prices across multiple European countries for a given date.
    
    Use this tool when the user asks questions like:
    - "Which country has the cheapest electricity today, Germany or France?"
    - "Compare electricity prices in Greece, Italy and Spain for tomorrow"
    - "Where in Europe is electricity cheapest right now?"
    - "Show me a price comparison between Nordic and Southern European countries"
    
    This tool is ideal for energy arbitrage analysis, cross-border price comparisons,
    and finding the cheapest country to run energy-intensive operations.
    
    Args:
        country_codes: Comma-separated list of two-letter ISO country codes 
                       (e.g. "DE,FR,GR" or "ES,IT,PT"). Minimum 2, maximum 6 countries.
        date: Target date in YYYY-MM-DD format.
    
    Returns:
        A side-by-side comparison table showing average, minimum, and maximum prices
        for each country, ranked from cheapest to most expensive, with percentage
        differences between the cheapest and most expensive country.
    """
    try:
        client = get_client()
        codes = [c.strip().upper() for c in country_codes.split(",")]
        
        if len(codes) < 2:
            return "Please provide at least 2 country codes separated by commas (e.g. 'DE,FR')."
        if len(codes) > 6:
            return "Maximum 6 countries can be compared at once."
        
        target_date = datetime.strptime(date, "%Y-%m-%d")
        start = pd.Timestamp(target_date, tz="UTC")
        end = start + timedelta(days=1)
        
        results = []
        errors = []
        
        for code in codes:
            zone = COUNTRY_TO_ZONE.get(code)
            if not zone:
                errors.append(f"{code}: unsupported country code")
                continue
            try:
                prices = client.query_day_ahead_prices(zone, start=start, end=end)
                if prices is not None and not prices.empty:
                    results.append({
                        "country": code,
                        "avg": prices.mean(),
                        "min": prices.min(),
                        "max": prices.max(),
                        "min_hour": prices.idxmin().strftime("%H:%M"),
                        "max_hour": prices.idxmax().strftime("%H:%M"),
                    })
                else:
                    errors.append(f"{code}: no data available")
            except Exception as e:
                errors.append(f"{code}: {str(e)}")
        
        if not results:
            return "Could not retrieve price data for any of the requested countries."
        
        # Sort by average price
        results.sort(key=lambda x: x["avg"])
        
        lines = [f"Electricity price comparison for {date}:\n"]
        lines.append(f"{'Country':<10} {'Average':>12} {'Min':>12} {'Max':>12} {'Cheapest hour':>15} {'Priciest hour':>15}")
        lines.append("-" * 80)
        
        for r in results:
            lines.append(
                f"{r['country']:<10} {r['avg']:>10.2f} € {r['min']:>10.2f} € {r['max']:>10.2f} € {r['min_hour']:>15} {r['max_hour']:>15}"
            )
        
        if len(results) > 1:
            cheapest = results[0]
            priciest = results[-1]
            diff_pct = ((priciest["avg"] - cheapest["avg"]) / cheapest["avg"]) * 100
            lines.append(f"\nCheapest: {cheapest['country']} at {cheapest['avg']:.2f} €/MWh average")
            lines.append(f"Priciest: {priciest['country']} at {priciest['avg']:.2f} €/MWh average")
            lines.append(f"Difference: {diff_pct:.1f}% — {priciest['country']} is {diff_pct:.1f}% more expensive than {cheapest['country']}")
        
        if errors:
            lines.append(f"\nNote: Could not retrieve data for: {', '.join(errors)}")
        
        return "\n".join(lines)
    
    except Exception as e:
        return f"Error comparing prices: {str(e)}"

if __name__ == "__main__":
    mcp.run()