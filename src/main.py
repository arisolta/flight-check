import argparse
import sys
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.config import load_config
from src.solver import find_optimal_routes
from src.google_flights_scraper import (
    generate_google_flights_url,
    generate_kayak_multicity_url,
    GoogleFlightsScraper,
)

console = Console()


def main():
    parser = argparse.ArgumentParser(
        description="Multi-Destination Direct Flight Route Optimizer CLI"
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config.json",
        help="Path to JSON configuration file (default: config.json)",
    )
    parser.add_argument(
        "--scrape-google-flights",
        action="store_true",
        help="Directly scrape Google Flights for the top established routes",
    )
    args = parser.parse_args()

    console.print(
        Panel.fit(
            "[bold cyan]✈️ Multi-Destination Direct Flight Route Optimizer[/bold cyan]\n"
            "[dim]Solving TSP over Direct Flight Circuits with Multi-Objective Optimization[/dim]",
            border_style="cyan",
        )
    )

    # 1. Load Configuration
    try:
        config = load_config(args.config)
        console.print(
            f"[green]✓[/green] Loaded configuration from [bold]{args.config}[/bold]"
        )
        console.print(
            f"  • Origin/Home City: [bold yellow]{config.trip_settings.home_city}[/bold yellow]"
        )
        console.print(
            f"  • Destinations ({len(config.trip_settings.destinations)}): [bold blue]{', '.join(config.trip_settings.destinations)}[/bold blue]"
        )
        console.print(
            f"  • Start Date: {config.trip_settings.start_date}"
        )
        console.print(
            f"  • City Stays: Default [{config.trip_settings.min_stay_days_per_city}-{config.trip_settings.max_stay_days_per_city} days]"
            + (f" | Overrides: {config.trip_settings.city_stay_overrides}" if config.trip_settings.city_stay_overrides else "")
        )
        console.print(
            f"  • Flight Times: Preferred '{config.trip_settings.preferred_departure_window}' (Latest allowed departure: {config.trip_settings.max_departure_hour}:00)"
        )
    except Exception as e:
        console.print(f"[bold red]Configuration Error:[/bold red] {e}")
        sys.exit(1)

    console.print("\n[bold yellow]🔍 Optimizing Flight Routes...[/bold yellow]")

    # 2. Run Solver
    try:
        results = find_optimal_routes(config)
    except Exception as e:
        console.print(f"[bold red]Solver Execution Error:[/bold red] {e}")
        sys.exit(1)

    # 3. Render Summary
    summary_table = Table(title="Optimization & Pruning Summary", box=None)
    summary_table.add_column("Metric", style="cyan", no_wrap=True)
    summary_table.add_column("Value", style="magenta")

    summary_table.add_row("Total Route Permutations", str(results["total_permutations"]))
    summary_table.add_row("Pruned by Static Graph (No Direct Flights)", str(results["pruned_by_static_graph"]))
    summary_table.add_row("Stay Duration Schedules Evaluated", str(results.get("schedules_evaluated", 0)))
    summary_table.add_row("Valid Candidate Circuits Found", str(results["valid_itineraries_count"]))

    console.print(summary_table)
    console.print()

    itineraries = results["itineraries"]
    if not itineraries:
        console.print("[bold red]❌ No valid direct flight circuits found matching all constraints.[/bold red]")
        sys.exit(0)

    # 4. Optional Web Scraping
    if args.scrape_google_flights and itineraries:
        console.print("[bold cyan]🌐 Scraping Google Flights live prices directly...[/bold cyan]")
        scraper = GoogleFlightsScraper()
        top_itin = itineraries[0]
        for leg in top_itin["legs"]:
            scraped_data = scraper.scrape_leg(
                leg["origin_city"], leg["destination_city"], leg["departure_date"]
            )
            if scraped_data.get("price_usd"):
                leg["price_usd"] = scraped_data["price_usd"]
            if scraped_data.get("duration_minutes"):
                leg["duration_minutes"] = scraped_data["duration_minutes"]

    # 5. Display Ranked Candidates
    console.print(f"[bold green]🏆 Top Ranked Valid Direct Circuits ({len(itineraries)} found):[/bold green]\n")

    for rank, itin in enumerate(itineraries[:5], start=1):
        kayak_url = generate_kayak_multicity_url(itin["legs"])

        table = Table(
            title=f"Rank #{rank}: {itin['route_string']} (Score: {itin['total_score']:.4f})",
            header_style="bold underline magenta",
        )
        table.add_column("Leg", style="dim", width=4)
        table.add_column("Date", style="cyan", width=12)
        table.add_column("From -> To", style="bold yellow")
        table.add_column("Airports", style="blue")
        table.add_column("Duration", style="white")
        table.add_column("Est. Price", style="bold green", justify="right")
        table.add_column("Google Flights Link", style="blue")

        for idx, leg in enumerate(itin["legs"], start=1):
            leg_gf_url = generate_google_flights_url(
                leg["origin_city"], leg["destination_city"], leg["departure_date"]
            )
            table.add_row(
                str(idx),
                leg["departure_date"],
                f"{leg['origin_city']} ✈ {leg['destination_city']}",
                f"{leg['origin']} -> {leg['destination']}",
                f"{leg['duration_minutes'] // 60}h {leg['duration_minutes'] % 60}m",
                f"${leg['price_usd']:.2f}",
                f"[link={leg_gf_url}]Open on Google Flights[/link]",
            )

        console.print(table)
        console.print(
            f"   ➡️ [bold]Total Flight Time:[/bold] {itin['total_duration_formatted']} | "
            f"[bold]Total Price:[/bold] [bold green]${itin['total_price_usd']:.2f}[/bold green] | "
            f"[bold]Score:[/bold] {itin['total_score']:.4f}"
        )
        console.print(
            f"   🔗 [bold cyan]1-Click Multi-City Kayak Link:[/bold cyan] [link={kayak_url}]{kayak_url}[/link]\n"
        )


if __name__ == "__main__":
    main()
